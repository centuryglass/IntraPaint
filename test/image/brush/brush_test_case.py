"""Shared test images, stroke helpers and a base test case for brushes that draw on an ImageLayer."""
from typing import Optional, Sequence

import numpy as np
from PySide6.QtCore import QPoint, QSize, QRect, Qt
from PySide6.QtGui import QImage

from src.image.brush.layer_brush import LayerBrush
from src.image.layers.image_layer import ImageLayer
from src.util.visual.image_utils import image_data_as_numpy_8bit, create_transparent_image
from test.base_test_case import IntraPaintTestCase

LAYER_SIZE = QSize(192, 128)

# Stroke points as (x, y) or (x, y, pressure):
StrokePoint = tuple[float, float] | tuple[float, float, float]


def brush_test_pattern(size: QSize = LAYER_SIZE) -> QImage:
    """Returns a deterministic ARGB32_Premultiplied test image with color gradients, a checkerboard, a fully
       transparent band and a half-transparent band, so brush output depends on every channel."""
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


def opacity_gradient_image(size: QSize = LAYER_SIZE, color: Optional[tuple[int, int, int]] = None) -> QImage:
    """Returns an ARGB32_Premultiplied image whose opacity rises from 0 at the left edge to 255 at the right edge.
       With no color, red and green vary along y and blue is a checkerboard. With a color, every pixel has that color
       before premultiplying."""
    width, height = size.width(), size.height()
    y, x = np.mgrid[0:height, 0:width]
    image = QImage(size, QImage.Format.Format_ARGB32)
    np_image = image_data_as_numpy_8bit(image)
    if color is None:
        np_image[:, :, 2] = (y * 255) // (height - 1)  # red
        np_image[:, :, 1] = 255 - (y * 255) // (height - 1)  # green
        np_image[:, :, 0] = ((x // 8 + y // 8) % 2) * 255  # blue
    else:
        np_image[:, :, 2], np_image[:, :, 1], np_image[:, :, 0] = color
    np_image[:, :, 3] = (x * 255) // (width - 1)
    return image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)


def rect_mask(selected: QRect, size: QSize = LAYER_SIZE) -> QImage:
    """Returns an input mask image that is opaque inside `selected` and transparent elsewhere."""
    mask = create_transparent_image(size)
    mask.fill(Qt.GlobalColor.transparent)
    np_mask = image_data_as_numpy_8bit(mask)
    np_mask[selected.y():selected.y() + selected.height(), selected.x():selected.x() + selected.width(), :] = 255
    return mask


def line_points(start: QPoint, end: QPoint, step: int) -> list[StrokePoint]:
    """Returns points from start to end inclusive, spaced `step` pixels apart along the longer axis."""
    dx = end.x() - start.x()
    dy = end.y() - start.y()
    count = max(abs(dx), abs(dy)) // step
    points: list[StrokePoint] = [(start.x() + dx * i // count, start.y() + dy * i // count) for i in range(count)]
    points.append((end.x(), end.y()))
    return points


class BrushTestCase(IntraPaintTestCase):
    """Base for tests that drive a LayerBrush directly on an ImageLayer. Subclasses set `self.layer` and `self.brush`
       in setUp.

    Nothing here waits for a brush's buffer timer: end_stroke draws any buffered input.
    """

    layer: ImageLayer
    brush: LayerBrush

    def use_layer(self, image: QImage) -> None:
        """Replaces the test layer with a new layer holding `image`, and connects the brush to it."""
        self.layer = ImageLayer(image, 'brush test layer')
        self.brush.connect_to_layer(self.layer)

    def stroke(self, points: Sequence[StrokePoint], flush_after_each_point: bool = False) -> QImage:
        """Draws one stroke through the given points and returns the resulting layer image. With
           flush_after_each_point, buffered input is drawn after every point, as if the buffer timer fired."""
        self.brush.start_stroke()
        for point in points:
            pressure: Optional[float] = point[2] if len(point) > 2 else None  # type: ignore[misc]
            self.brush.stroke_to(point[0], point[1], pressure, None, None)
            if flush_after_each_point:
                self.brush._draw_buffered_events()  # type: ignore[attr-defined]  # pylint: disable=protected-access
        self.brush.end_stroke()
        return self.layer.image

    def assert_valid_premultiplied(self, image: QImage) -> None:
        """Asserts that no color channel exceeds alpha, which no valid premultiplied pixel can do."""
        np_image = image_data_as_numpy_8bit(image)
        invalid = np_image[:, :, :3].max(axis=2) > np_image[:, :, 3]
        self.assertFalse(np.any(invalid), f'{np.count_nonzero(invalid)} pixels have color above alpha')

    def assert_changes_inside(self, image: QImage, initial_image: QImage, allowed: QRect) -> None:
        """Asserts that every pixel that differs between `image` and `initial_image` is inside `allowed`."""
        changed = np.any(image_data_as_numpy_8bit(image) != image_data_as_numpy_8bit(initial_image), axis=2)
        changed[allowed.y():allowed.y() + allowed.height(), allowed.x():allowed.x() + allowed.width()] = False
        self.assertFalse(np.any(changed), f'{np.count_nonzero(changed)} pixels changed outside {allowed}')
