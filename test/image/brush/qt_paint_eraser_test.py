"""Tests QtPaintBrush in eraser mode against golden images, and checks properties that must hold for any erase
   stroke."""
import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QColor, QImage

from src.image.brush.qt_paint_brush import QtPaintBrush
from src.image.layers.image_layer import ImageLayer
from src.undo_stack import UndoStack
from src.util.visual.image_utils import image_data_as_numpy_8bit, create_transparent_image
from test.image.brush.brush_test_case import BrushTestCase, LAYER_SIZE, StrokePoint, brush_test_pattern, \
    opacity_gradient_image, line_points, rect_mask
from test.image.brush.qt_paint_brush_test import zigzag_points

GOLDEN_DIR = 'test/resources/test_images/qt_paint_brush'


def solid_image(color: QColor) -> QImage:
    """Returns a layer-sized ARGB32_Premultiplied image filled with one color."""
    image = QImage(LAYER_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    return image


class QtPaintEraserTest(BrushTestCase):
    """Drives QtPaintBrush with eraser = True directly on an ImageLayer, configured as EraserTool configures it."""

    brush: QtPaintBrush

    def setUp(self) -> None:
        super().setUp()
        self.layer = ImageLayer(brush_test_pattern(), 'eraser test layer')
        self.brush = QtPaintBrush(self.layer)
        self.brush.eraser = True
        self.brush.brush_size = 16
        self.brush.opacity = 1.0
        self.brush.hardness = 1.0
        self.brush.antialiasing = False
        self.brush.pressure_size = True
        self.brush.pressure_opacity = False
        self.brush.pressure_hardness = False

    def assert_stroke_matches_golden(self, image: QImage, golden_name: str) -> None:
        """Checks that a stroke left only valid premultiplied pixels, then compares it with its golden image."""
        self.assert_valid_premultiplied(image)
        self.assert_image_matches_golden(image, f'{GOLDEN_DIR}/{golden_name}.png')

    def assert_only_alpha_reduced(self, image: QImage, initial_image: QImage) -> None:
        """Asserts that no pixel gained alpha, and that every pixel left visible keeps its unpremultiplied color
           within the rounding error of 8-bit premultiplied storage."""
        self.assert_valid_premultiplied(image)
        np_image = image_data_as_numpy_8bit(image).astype(np.int32)
        np_initial = image_data_as_numpy_8bit(initial_image).astype(np.int32)
        alpha = np_image[:, :, 3]
        initial_alpha = np_initial[:, :, 3]
        raised = alpha > initial_alpha
        self.assertFalse(np.any(raised), f'{np.count_nonzero(raised)} pixels gained alpha')
        visible = alpha > 0
        # Unpremultiplying a channel stored at alpha a can be off by up to 255 / a from each premultiplied rounding:
        color = np_image[visible, :3] * 255.0 / alpha[visible, np.newaxis]
        initial_color = np_initial[visible, :3] * 255.0 / initial_alpha[visible, np.newaxis]
        tolerance = 255.0 / alpha[visible, np.newaxis] + 255.0 / initial_alpha[visible, np.newaxis]
        shifted = np.any(np.abs(color - initial_color) > tolerance, axis=1)
        self.assertFalse(np.any(shifted), f'{np.count_nonzero(shifted)} pixels changed color beyond rounding')

    def test_hard_aliased_erase(self) -> None:
        """A hard, opaque eraser without antialiasing clears the pixels it covers."""
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'eraser_hard_aliased')
        self.assert_only_alpha_reduced(image, brush_test_pattern())

    def test_hard_antialiased_translucent_erase(self) -> None:
        """A hard, antialiased eraser at partial opacity, crossing itself."""
        self.brush.brush_size = 20
        self.brush.opacity = 0.6
        self.brush.antialiasing = True
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'eraser_hard_antialiased_translucent')
        self.assert_only_alpha_reduced(image, brush_test_pattern())

    def test_soft_erase(self) -> None:
        """A soft, antialiased eraser at partial opacity, crossing itself."""
        self.brush.brush_size = 30
        self.brush.opacity = 0.8
        self.brush.hardness = 0.3
        self.brush.antialiasing = True
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'eraser_soft')
        self.assert_only_alpha_reduced(image, brush_test_pattern())

    def test_pressure_controls_size_opacity_and_hardness(self) -> None:
        """Rising pressure scales eraser size, opacity and hardness along the stroke."""
        self.brush.brush_size = 40
        self.brush.pressure_opacity = True
        self.brush.pressure_hardness = True
        self.brush.antialiasing = True
        line = line_points(QPoint(15, 90), QPoint(175, 30), 8)
        points: list[StrokePoint] = [(x, y, 0.2 + 0.8 * i / (len(line) - 1)) for i, (x, y, *_) in enumerate(line)]
        image = self.stroke(points)
        self.assert_stroke_matches_golden(image, 'eraser_pressure')
        self.assert_only_alpha_reduced(image, brush_test_pattern())

    def test_erase_across_opacity_gradient(self) -> None:
        """Soft erase strokes at partial opacity across pixels that are already partly transparent."""
        initial_image = opacity_gradient_image()
        self.use_layer(initial_image)
        self.brush.brush_size = 30
        self.brush.opacity = 0.6
        self.brush.hardness = 0.4
        self.brush.antialiasing = True
        self.stroke(line_points(QPoint(180, 30), QPoint(10, 30), 7))
        self.brush.opacity = 0.35
        image = self.stroke(line_points(QPoint(20, 120), QPoint(170, 75), 7))
        self.assert_stroke_matches_golden(image, 'eraser_opacity_gradient')
        self.assert_only_alpha_reduced(image, initial_image)

    def test_erase_leaves_color_of_remaining_pixels(self) -> None:
        """Partial erasing over a translucent solid color lowers alpha in proportion to opacity, and leaves the color
           of what remains."""
        initial_image = solid_image(QColor(200, 120, 40, 160))
        self.use_layer(initial_image)
        self.brush.brush_size = 24
        self.brush.opacity = 0.5
        image = self.stroke(line_points(QPoint(20, 64), QPoint(170, 64), 6))
        self.assert_only_alpha_reduced(image, initial_image)
        self.assertAlmostEqual(int(image_data_as_numpy_8bit(image)[64, 90, 3]), 80, delta=1)

    def test_erase_over_transparent_pixels_changes_nothing(self) -> None:
        """Erasing a fully transparent layer leaves every pixel at zero."""
        self.use_layer(create_transparent_image(LAYER_SIZE))
        self.brush.brush_size = 30
        self.brush.opacity = 0.7
        self.brush.hardness = 0.4
        self.brush.antialiasing = True
        image = self.stroke(zigzag_points())
        self.assertFalse(np.any(image_data_as_numpy_8bit(image)), 'erasing a transparent layer changed pixels')

    def test_input_mask_restricts_changes(self) -> None:
        """Erasing stays inside the input mask."""
        initial_image = self.layer.image
        selected = QRect(40, 20, 80, 50)
        self.brush.set_input_mask(rect_mask(selected))
        self.brush.brush_size = 24
        self.brush.hardness = 0.4
        self.brush.opacity = 0.9
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'eraser_input_mask')
        self.assert_changes_inside(image, initial_image, selected)

    def test_overlapping_segments_do_not_build_up(self) -> None:
        """Within one stroke, overlapping segments don't erase more than the eraser opacity."""
        self.use_layer(solid_image(QColor(30, 90, 200)))
        self.brush.brush_size = 20
        self.brush.opacity = 0.5
        self.brush.hardness = 0.5
        self.brush.antialiasing = True
        image = self.stroke(zigzag_points())
        alpha = image_data_as_numpy_8bit(image)[:, :, 3]
        self.assertAlmostEqual(int(alpha.min()), 255 * 0.5, delta=1)

    def test_second_stroke_erases_more(self) -> None:
        """Overlap limiting applies within a stroke only: a second stroke over the first erases further."""
        self.use_layer(solid_image(QColor(30, 90, 200)))
        self.brush.opacity = 0.5
        self.stroke(line_points(QPoint(20, 64), QPoint(170, 64), 10))
        first_alpha = int(image_data_as_numpy_8bit(self.layer.image)[64, 90, 3])
        image = self.stroke(line_points(QPoint(90, 10), QPoint(90, 120), 10))
        self.assertLess(int(image_data_as_numpy_8bit(image)[64, 90, 3]), first_alpha)

    def test_mid_stroke_draws_match_one_draw_at_end(self) -> None:
        """Erasing buffered input partway through a stroke doesn't change the result."""
        self.brush.brush_size = 26
        self.brush.opacity = 0.7
        self.brush.hardness = 0.4
        self.brush.antialiasing = True
        self.brush.pressure_opacity = True
        points: list[StrokePoint] = [(x, y, 0.3 + 0.7 * ((i % 5) / 4))
                                     for i, (x, y, *_) in enumerate(zigzag_points())]
        buffered_image = self.stroke(points)
        UndoStack().undo()
        self.assert_images_equal(self.layer.image, brush_test_pattern())
        flushed_image = self.stroke(points, flush_after_each_point=True)
        self.assert_images_equal(flushed_image, buffered_image)

    def configure_alpha_locked_erase(self) -> QImage:
        """Puts an alpha-locked opacity gradient on the test layer, sets up a soft translucent eraser, and returns the
           layer's initial image."""
        initial_image = opacity_gradient_image()
        self.use_layer(initial_image)
        self.layer.alpha_locked = True
        self.brush.brush_size = 30
        self.brush.opacity = 0.6
        self.brush.hardness = 0.4
        self.brush.antialiasing = True
        return initial_image

    def test_alpha_locked_layer(self) -> None:
        """Erasing an alpha-locked layer leaves its alpha unchanged."""
        initial_image = self.configure_alpha_locked_erase()
        image = self.stroke(zigzag_points())
        self.assert_images_equal(image.convertToFormat(QImage.Format.Format_Alpha8),
                                 initial_image.convertToFormat(QImage.Format.Format_Alpha8))
        self.assert_stroke_matches_golden(image, 'eraser_alpha_locked')

    @pytest.mark.xfail(strict=True, reason='https://github.com/centuryglass/IntraPaint/issues/154')
    def test_repeated_erasing_on_alpha_locked_layer_keeps_color(self) -> None:
        """Erase strokes on an alpha-locked layer don't shift its color, however many are repeated."""
        initial_image = self.configure_alpha_locked_erase()
        for _ in range(10):
            self.stroke(zigzag_points())
        self.assert_only_alpha_reduced(self.layer.image, initial_image)

    def test_undo_restores_layer(self) -> None:
        """Each erase stroke is one undo step, and undoing it restores the layer."""
        UndoStack().clear()
        image = self.stroke(zigzag_points())
        self.assertNotEqual(image, brush_test_pattern())
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assert_images_equal(self.layer.image, brush_test_pattern())
