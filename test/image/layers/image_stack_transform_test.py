"""Tests ImageStack.flip_image and rotate_image: every layer, the selection, context pins and the generation area move
together on a non-square canvas, and one undo step restores all of them."""
from typing import Callable

import numpy as np
from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QImage, QTransform

from src.image.layers.image_stack import ImageStack
from src.image.layers.transform_layer import TransformLayer
from src.undo_stack import UndoStack
from src.util.visual.geometry_utils import map_rect_precise
from src.util.visual.image_utils import image_data_as_numpy_8bit
from test.image.layers.image_stack_state import CANVAS_SIZE, ImageStackOpTestCase, select_rect
from test.render_assertions import full_render

WIDTH = CANVAS_SIZE.width()
HEIGHT = CANVAS_SIZE.height()
OFFSET_LAYER_POS = QPoint(-4, 14)
OFFSET_LAYER_SIZE = QSize(12, 16)
SELECTED_RECT = QRect(3, 2, 14, 9)
GENERATION_AREA = QRect(18, 4, 12, 16)
PINS = [QPoint(1, 20), QPoint(30, 3)]

PixelMap = Callable[[QPoint], QPoint]


def _array_image(array: np.ndarray) -> QImage:
    image = QImage(QSize(array.shape[1], array.shape[0]), QImage.Format.Format_ARGB32_Premultiplied)
    np.copyto(image_data_as_numpy_8bit(image), array)
    return image


def _numpy_transformed(image: QImage, change: Callable[[np.ndarray], np.ndarray]) -> QImage:
    image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    return _array_image(np.ascontiguousarray(change(image_data_as_numpy_8bit(image))))


# Each case: the operation, the same change applied to a pixel array, the pixel coordinate mapping, and the image-space
# transformation it should apply to layer transforms.
CASES: dict[str, tuple[Callable[[ImageStack], None], Callable[[np.ndarray], np.ndarray], PixelMap, QTransform]] = {
    'flip_horizontal': (lambda stack: stack.flip_image(True), lambda a: a[:, ::-1],
                        lambda p: QPoint(WIDTH - 1 - p.x(), p.y()), QTransform(-1, 0, 0, 1, WIDTH, 0)),
    'flip_vertical': (lambda stack: stack.flip_image(False), lambda a: a[::-1, :],
                      lambda p: QPoint(p.x(), HEIGHT - 1 - p.y()), QTransform(1, 0, 0, -1, 0, HEIGHT)),
    'rotate_cw': (lambda stack: stack.rotate_image(90), lambda a: np.rot90(a, -1),
                  lambda p: QPoint(HEIGHT - 1 - p.y(), p.x()), QTransform(0, 1, -1, 0, HEIGHT, 0)),
    'rotate_ccw': (lambda stack: stack.rotate_image(-90), lambda a: np.rot90(a, 1),
                   lambda p: QPoint(p.y(), WIDTH - 1 - p.x()), QTransform(0, -1, 1, 0, 0, WIDTH)),
    'rotate_180': (lambda stack: stack.rotate_image(180), lambda a: np.rot90(a, 2),
                   lambda p: QPoint(WIDTH - 1 - p.x(), HEIGHT - 1 - p.y()), QTransform(-1, 0, 0, -1, WIDTH, HEIGHT)),
}


def _mapped_rect(rect: QRect, pixel_map: PixelMap) -> QRect:
    first = pixel_map(rect.topLeft())
    last = pixel_map(rect.bottomRight())
    return QRect(QPoint(min(first.x(), last.x()), min(first.y(), last.y())),
                 QPoint(max(first.x(), last.x()), max(first.y(), last.y())))


class TransformImageTest(ImageStackOpTestCase):
    """Applies each whole-image flip and rotation to a stack with a translucent canvas layer, a group holding a hidden
    layer and a locked layer, and a layer partly outside the canvas."""

    def setUp(self) -> None:
        super().setUp()
        self.add_layer('top', 1, QSize(10, 6), QPoint(20, 1), min_alpha=90)
        group = self.add_group('group')
        hidden = self.add_layer('hidden', 2, QSize(8, 8), QPoint(2, 2), group)
        hidden.set_visible(False)
        self.locked = self.add_layer('locked', 3, QSize(9, 7), QPoint(5, 12), group, min_alpha=90)
        self.locked.set_locked(True)
        self.offset = self.add_layer('offset', 4, OFFSET_LAYER_SIZE, OFFSET_LAYER_POS, min_alpha=90)
        self.add_layer('full', 5, min_alpha=120)
        select_rect(self.image_stack, SELECTED_RECT)
        self.image_stack.selection_layer.set_context_pins(PINS, False)
        self.image_stack.generation_area = GENERATION_AREA

    def _check(self, name: str) -> None:
        operation, array_change, pixel_map, image_transform = CASES[name]
        stack = self.image_stack
        old_composite = full_render(stack)
        old_selection = stack.selection_layer.image
        layer_transforms = {layer: layer.transform for layer in stack.layers if isinstance(layer, TransformLayer)}
        before, after = self.assert_undo_redo(lambda: operation(stack))

        expected_size = _numpy_transformed(old_composite, array_change).size()
        self.assertEqual(expected_size, after.size)
        self.assert_images_equal(after.composite, _numpy_transformed(old_composite, array_change))
        for layer, last_transform in layer_transforms.items():
            self.assertEqual(last_transform * image_transform, layer.transform, layer.name)
        self.assertEqual(map_rect_precise(QRect(OFFSET_LAYER_POS, OFFSET_LAYER_SIZE), image_transform).toAlignedRect(),
                         self.offset.transformed_bounds)
        self.assertTrue(self.locked.locked)

        selection_layer = stack.selection_layer
        self.assertEqual(QRect(QPoint(), expected_size), selection_layer.transformed_bounds)
        self.assert_images_equal(selection_layer.image, _numpy_transformed(old_selection, array_change))
        self.assertEqual(_mapped_rect(SELECTED_RECT, pixel_map), selection_layer.get_content_bounds())
        self.assertEqual([pixel_map(pin) for pin in PINS], selection_layer.context_pins)
        self.assertEqual(_mapped_rect(GENERATION_AREA, pixel_map), stack.generation_area)

        UndoStack().undo()
        self.assertEqual(before.size, stack.size)
        self.assertEqual(PINS, selection_layer.context_pins)
        self.assertEqual(GENERATION_AREA, stack.generation_area)

    def test_flip_horizontal(self) -> None:
        """Flip horizontally mirrors every layer, the selection, pins and generation area across the canvas."""
        self._check('flip_horizontal')

    def test_flip_vertical(self) -> None:
        """Flip vertically mirrors every layer, the selection, pins and generation area across the canvas."""
        self._check('flip_vertical')

    def test_rotate_cw(self) -> None:
        """Rotating 90 degrees clockwise swaps the canvas width and height and rotates everything with it."""
        self._check('rotate_cw')

    def test_rotate_ccw(self) -> None:
        """Rotating 90 degrees counter-clockwise swaps the canvas width and height and rotates everything with it."""
        self._check('rotate_ccw')

    def test_rotate_180(self) -> None:
        """Rotating 180 degrees keeps the canvas size and turns everything about its center."""
        self._check('rotate_180')

    def test_rotation_rejects_other_angles(self) -> None:
        """Only multiples of 90 degrees are accepted."""
        with self.assertRaises(ValueError):
            self.image_stack.rotate_image(45)
