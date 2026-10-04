"""Tests SmudgeBrush output against golden images, and checks properties that must hold for any smudge stroke."""
from typing import Optional, Sequence

import numpy as np
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QImage

from src.image.brush.smudge_brush import SmudgeBrush
from src.image.layers.image_layer import ImageLayer
from src.undo_stack import UndoStack
from src.util.visual.image_utils import create_transparent_image, image_data_as_numpy_8bit
from test.base_test_case import IntraPaintTestCase

GOLDEN_DIR = 'test/resources/test_images/smudge'
LAYER_SIZE = QSize(192, 128)

# Stroke points as (x, y) or (x, y, pressure):
StrokePoint = tuple[float, float] | tuple[float, float, float]


def smudge_test_pattern(size: QSize = LAYER_SIZE) -> QImage:
    """Returns a deterministic ARGB32_Premultiplied test image with color gradients, a checkerboard, a fully
       transparent band and a half-transparent band, so smudge output depends on every channel."""
    width, height = size.width(), size.height()
    y, x = np.mgrid[0:height, 0:width]
    image = QImage(size, QImage.Format.Format_ARGB32)
    np_image = image_data_as_numpy_8bit(image)
    np_image[:, :, 2] = (x * 7) % 256  # red
    np_image[:, :, 1] = (y * 5) % 256  # green
    np_image[:, :, 0] = ((x // 8 + y // 8) % 2) * 255  # blue
    alpha = np.full((height, width), 255)
    alpha[(x >= width * 5 // 8) & (x < width * 3 // 4)] = 0
    alpha[(y >= height * 3 // 4) & (y < height * 7 // 8)] = 128
    np_image[:, :, 3] = alpha
    return image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)


def line_points(start: QPoint, end: QPoint, step: int) -> list[StrokePoint]:
    """Returns points from start to end inclusive, spaced `step` pixels apart along the longer axis."""
    dx = end.x() - start.x()
    dy = end.y() - start.y()
    count = max(abs(dx), abs(dy)) // step
    points: list[StrokePoint] = [(start.x() + dx * i // count, start.y() + dy * i // count) for i in range(count)]
    points.append((end.x(), end.y()))
    return points


class SmudgeBrushTest(IntraPaintTestCase):
    """Drives SmudgeBrush directly on an ImageLayer. Nothing here waits for the brush's buffer timer: end_stroke
       draws any buffered input."""

    def setUp(self) -> None:
        super().setUp()
        self.layer = ImageLayer(smudge_test_pattern(), 'smudge test layer')
        self.brush = SmudgeBrush(self.layer)
        self.brush.brush_size = 24
        self.brush.opacity = 0.5
        self.brush.hardness = 1.0
        self.brush.antialiasing = True
        self.brush.pressure_size = True
        self.brush.pressure_opacity = False
        self.brush.pressure_hardness = False

    def stroke(self, points: Sequence[StrokePoint], flush_after_each_point: bool = False) -> QImage:
        """Draws one stroke through the given points and returns the resulting layer image. With
           flush_after_each_point, buffered input is drawn after every point, as if the buffer timer fired."""
        self.brush.start_stroke()
        for point in points:
            pressure: Optional[float] = point[2] if len(point) > 2 else None  # type: ignore[misc]
            self.brush.stroke_to(point[0], point[1], pressure, None, None)
            if flush_after_each_point:
                self.brush._draw_buffered_events()  # pylint: disable=protected-access
        self.brush.end_stroke()
        return self.layer.image

    def test_default_settings_horizontal_stroke(self) -> None:
        image = self.stroke(line_points(QPoint(20, 40), QPoint(170, 40), 10))
        self.assert_image_matches_golden(image, f'{GOLDEN_DIR}/horizontal_default.png')

    def test_soft_aliased_diagonal_stroke(self) -> None:
        self.brush.brush_size = 30
        self.brush.opacity = 1.0
        self.brush.hardness = 0.25
        self.brush.antialiasing = False
        image = self.stroke(line_points(QPoint(10, 10), QPoint(180, 115), 7))
        self.assert_image_matches_golden(image, f'{GOLDEN_DIR}/diagonal_soft_aliased.png')

    def test_single_pixel_steps(self) -> None:
        self.brush.brush_size = 16
        self.brush.opacity = 0.8
        self.brush.hardness = 0.6
        points: list[StrokePoint] = []
        for i in range(60):
            points.append((30 + i, 60 + (i // 3) % 2))
        image = self.stroke(points)
        self.assert_image_matches_golden(image, f'{GOLDEN_DIR}/single_pixel_steps.png')

    def test_pressure_controls_size_opacity_and_hardness(self) -> None:
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
        initial_image = self.layer.image
        mask = create_transparent_image(LAYER_SIZE)
        selected = QRect(40, 20, 80, 50)
        mask.fill(Qt.GlobalColor.transparent)
        np_mask = image_data_as_numpy_8bit(mask)
        np_mask[selected.y():selected.y() + selected.height(), selected.x():selected.x() + selected.width(), :] = 255
        self.brush.set_input_mask(mask)
        self.brush.opacity = 1.0
        image = self.stroke(line_points(QPoint(10, 45), QPoint(180, 45), 6))
        self.assert_image_matches_golden(image, f'{GOLDEN_DIR}/input_mask.png')

        changed = np.any(image_data_as_numpy_8bit(image) != image_data_as_numpy_8bit(initial_image), axis=2)
        changed[selected.y():selected.y() + selected.height(), selected.x():selected.x() + selected.width()] = False
        self.assertFalse(np.any(changed), 'smudge changed pixels outside the input mask')

    def test_stroke_crossing_layer_edges(self) -> None:
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
        self.assert_images_equal(self.layer.image, smudge_test_pattern())
        flushed_image = self.stroke(points, flush_after_each_point=True)
        self.assert_images_equal(flushed_image, buffered_image)

    def test_click_without_movement_changes_nothing(self) -> None:
        image = self.stroke([(50, 50)])
        self.assert_images_equal(image, smudge_test_pattern())

    def test_undo_restores_layer(self) -> None:
        UndoStack().clear()
        image = self.stroke(line_points(QPoint(20, 40), QPoint(170, 40), 10))
        self.assertNotEqual(image, smudge_test_pattern())
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assert_images_equal(self.layer.image, smudge_test_pattern())
