"""Tests SmudgeBrush output against golden images, and checks properties that must hold for any smudge stroke."""
from unittest.mock import patch

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QImage

from src.image.brush.smudge_brush import SmudgeBrush
from src.image.layers.image_layer import ImageLayer
from src.undo_stack import UndoStack
from src.util.visual.image_utils import image_data_as_numpy_8bit
from test.image.brush.brush_test_case import BrushTestCase, LAYER_SIZE, StrokePoint, brush_test_pattern, \
    opacity_gradient_image, line_points, rect_mask

GOLDEN_DIR = 'test/resources/test_images/smudge'

# Unpremultiplied color for the single-color opacity gradient tests:
GRADIENT_COLOR = (200, 80, 30)
# Largest per-channel color error that 8-bit premultiplied storage alone causes at alpha >= 64:
GRADIENT_COLOR_TOLERANCE = 4
# Lowest alpha whose 8-bit premultiplied pixels keep GRADIENT_COLOR closely enough for the tolerance to hold after
# smudging builds them up to visible opacity:
GRADIENT_MIN_SOURCE_ALPHA = 32


class SmudgeBrushTest(BrushTestCase):
    """Drives SmudgeBrush directly on an ImageLayer."""

    def setUp(self) -> None:
        super().setUp()
        self.layer = ImageLayer(brush_test_pattern(), 'smudge test layer')
        self.brush = SmudgeBrush(self.layer)
        self.brush.brush_size = 24
        self.brush.opacity = 0.5
        self.brush.hardness = 1.0
        self.brush.antialiasing = True
        self.brush.pressure_size = True
        self.brush.pressure_opacity = False
        self.brush.pressure_hardness = False

    def test_default_settings_horizontal_stroke(self) -> None:
        """A hard, half-opacity, antialiased brush on a horizontal stroke."""
        image = self.stroke(line_points(QPoint(20, 40), QPoint(170, 40), 10))
        self.assert_image_matches_golden(image, f'{GOLDEN_DIR}/horizontal_default.png')

    def test_soft_aliased_diagonal_stroke(self) -> None:
        """A soft, fully opaque brush without antialiasing on a diagonal stroke."""
        self.brush.brush_size = 30
        self.brush.opacity = 1.0
        self.brush.hardness = 0.25
        self.brush.antialiasing = False
        image = self.stroke(line_points(QPoint(10, 10), QPoint(180, 115), 7))
        self.assert_image_matches_golden(image, f'{GOLDEN_DIR}/diagonal_soft_aliased.png')

    def test_single_pixel_steps(self) -> None:
        """Input points one pixel apart, which skip interpolation."""
        self.brush.brush_size = 16
        self.brush.opacity = 0.8
        self.brush.hardness = 0.6
        points: list[StrokePoint] = []
        for i in range(60):
            points.append((30 + i, 60 + (i // 3) % 2))
        image = self.stroke(points)
        self.assert_image_matches_golden(image, f'{GOLDEN_DIR}/single_pixel_steps.png')

    def test_pressure_controls_size_opacity_and_hardness(self) -> None:
        """Rising pressure scales size, opacity and hardness along the stroke."""
        self.brush.brush_size = 40
        self.brush.opacity = 1.0
        self.brush.hardness = 1.0
        self.brush.pressure_opacity = True
        self.brush.pressure_hardness = True
        line = line_points(QPoint(15, 90), QPoint(175, 30), 8)
        points: list[StrokePoint] = [(x, y, 0.2 + 0.8 * i / (len(line) - 1)) for i, (x, y, *_) in enumerate(line)]
        image = self.stroke(points)
        self.assert_image_matches_golden(image, f'{GOLDEN_DIR}/pressure.png')

    def test_input_mask_restricts_changes(self) -> None:
        """Changes stay inside the input mask."""
        initial_image = self.layer.image
        selected = QRect(40, 20, 80, 50)
        self.brush.set_input_mask(rect_mask(selected))
        self.brush.opacity = 1.0
        image = self.stroke(line_points(QPoint(10, 45), QPoint(180, 45), 6))
        self.assert_image_matches_golden(image, f'{GOLDEN_DIR}/input_mask.png')
        self.assert_changes_inside(image, initial_image, selected)

    def test_stroke_crossing_layer_edges(self) -> None:
        """A stroke that leaves the layer and comes back, sampling partly outside it."""
        self.brush.brush_size = 36
        self.brush.opacity = 0.9
        points = (line_points(QPoint(60, 64), QPoint(-20, 64), 5)
                  + line_points(QPoint(-20, 64), QPoint(100, -15), 5)[1:]
                  + line_points(QPoint(100, -15), QPoint(210, 120), 5)[1:])
        image = self.stroke(points)
        self.assert_image_matches_golden(image, f'{GOLDEN_DIR}/crossing_edges.png')

    def test_mid_stroke_draws_match_one_draw_at_end(self) -> None:
        """Drawing buffered input partway through a stroke doesn't change the result."""
        points = line_points(QPoint(20, 20), QPoint(170, 100), 9)
        self.brush.hardness = 0.5
        buffered_image = self.stroke(points)
        UndoStack().undo()
        self.assert_images_equal(self.layer.image, brush_test_pattern())
        flushed_image = self.stroke(points, flush_after_each_point=True)
        self.assert_images_equal(flushed_image, buffered_image)

    def test_mid_stroke_draw_defers_points_past_time_limit(self) -> None:
        """A mid-stroke draw that runs past MAX_DRAW_SECONDS leaves the remaining points buffered and schedules
           another draw, and the finished stroke matches one drawn all at once."""
        # pylint: disable=protected-access
        points = line_points(QPoint(10, 64), QPoint(180, 64), 85)
        expected_image = self.stroke(points)
        UndoStack().undo()
        with patch('src.image.brush.layer_brush.MAX_DRAW_SECONDS', 0.0):
            self.brush.start_stroke()
            for x, y, *_ in points:
                self.brush.stroke_to(x, y, None, None, None)
            buffered_count = len(self.brush._input_buffer)
            self.brush._draw_buffered_events()
            remaining_count = len(self.brush._input_buffer)
            self.assertGreater(remaining_count, 0)
            self.assertLess(remaining_count, buffered_count)
            self.assertTrue(self.brush._buffer_timer.isActive())
            self.brush._draw_buffered_events()
            self.assertEqual(len(self.brush._input_buffer), remaining_count - 1)
            self.brush.end_stroke()
        self.assertEqual(len(self.brush._input_buffer), 0)
        self.assert_images_equal(self.layer.image, expected_image)

    def gradient_strokes(self) -> QImage:
        """Smudges from opaque into transparent, from transparent into opaque, then diagonally across the
           gradient, and returns the layer image."""
        self.stroke(line_points(QPoint(180, 30), QPoint(10, 30), 7))
        self.stroke(line_points(QPoint(10, 64), QPoint(180, 64), 7))
        return self.stroke(line_points(QPoint(20, 120), QPoint(170, 95), 7))

    def test_strokes_across_opacity_gradient(self) -> None:
        """Strokes across an opacity gradient in both directions with a soft brush."""
        self.use_layer(opacity_gradient_image())
        self.brush.brush_size = 30
        self.brush.opacity = 0.8
        self.brush.hardness = 0.4
        image = self.gradient_strokes()
        self.assert_valid_premultiplied(image)
        self.assert_image_matches_golden(image, f'{GOLDEN_DIR}/opacity_gradient.png')

    def gradient_color_error(self, image: QImage, min_source_alpha: int) -> int:
        """Returns the largest per-channel difference from GRADIENT_COLOR among pixels that end up at least 25%
           opaque and started with alpha of at least min_source_alpha."""
        np_image = image_data_as_numpy_8bit(image.convertToFormat(QImage.Format.Format_ARGB32)).astype(int)
        source_alpha = image_data_as_numpy_8bit(opacity_gradient_image(color=GRADIENT_COLOR))[:, :, 3]
        checked = (np_image[:, :, 3] >= 64) & (source_alpha >= min_source_alpha)
        expected_bgr = np.array(GRADIENT_COLOR[::-1])
        return int(np.abs(np_image[:, :, :3] - expected_bgr).max(axis=2)[checked].max())

    def test_smudge_keeps_color_on_opacity_gradient(self) -> None:
        """Smudging a single color with varying opacity changes opacity but not color, wherever 8-bit storage holds
           the color."""
        self.use_layer(opacity_gradient_image(color=GRADIENT_COLOR))
        self.brush.brush_size = 40
        image = self.gradient_strokes()
        self.assert_valid_premultiplied(image)
        self.assertLessEqual(self.gradient_color_error(image, GRADIENT_MIN_SOURCE_ALPHA), GRADIENT_COLOR_TOLERANCE)

    @pytest.mark.xfail(strict=True, reason='https://github.com/centuryglass/IntraPaint/issues/203: smudging '
                                          'builds alpha from nearly transparent pixels whose 8-bit color is lost')
    def test_smudge_keeps_color_built_from_nearly_transparent_pixels(self) -> None:
        """Smudging a single color doesn't change it where the stroke builds opacity from nearly transparent
           pixels."""
        self.use_layer(opacity_gradient_image(color=GRADIENT_COLOR))
        self.brush.brush_size = 40
        image = self.gradient_strokes()
        self.assertLessEqual(self.gradient_color_error(image, 0), GRADIENT_COLOR_TOLERANCE)

    def test_stroke_inside_transparent_area_changes_nothing(self) -> None:
        """Smudging within fully transparent pixels leaves them transparent."""
        self.brush.brush_size = 10
        self.brush.opacity = 1.0
        band_center = LAYER_SIZE.width() * 11 // 16  # Center of brush_test_pattern's transparent band
        image = self.stroke(line_points(QPoint(band_center, 10), QPoint(band_center, 80), 5))
        self.assert_images_equal(image, brush_test_pattern())

    def test_click_without_movement_changes_nothing(self) -> None:
        """A single point samples the layer but draws nothing."""
        image = self.stroke([(50, 50)])
        self.assert_images_equal(image, brush_test_pattern())

    def test_undo_restores_layer(self) -> None:
        """A stroke is one undo step, and undoing it restores the layer."""
        UndoStack().clear()
        image = self.stroke(line_points(QPoint(20, 40), QPoint(170, 40), 10))
        self.assertNotEqual(image, brush_test_pattern())
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assert_images_equal(self.layer.image, brush_test_pattern())
