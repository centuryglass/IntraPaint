"""Tests ImageStack.resize_canvas: expanding and cropping the canvas, with each LayerResizeMode, and undo and redo."""
import unittest
from unittest.mock import patch

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QTransform

from src.config.application_config import AppConfig
from src.image.layers.layer_resize_mode import LayerResizeMode
from src.image.layers.text_layer import TextLayer
from src.image.text_rect import TextRect
from src.undo_stack import UndoStack
from src.util.visual.image_utils import create_transparent_image
from test.image.layers.image_stack_state import CANVAS_SIZE, ImageStackOpTestCase, select_rect
from test.render_assertions import full_render

ERROR_DIALOG = 'src.image.layers.image_stack.show_error_dialog'
CONFIRM_RENDER_TEXT = 'src.image.layers.text_layer.request_confirmation'

EXPANDED_SIZE = QSize(40, 30)
EXPAND_OFFSET = QPoint(4, 2)
CROP_RECT = QRect(6, 4, 16, 12)


class ResizeCanvasTest(ImageStackOpTestCase):
    """Tests ImageStack.resize_canvas on a canvas-sized layer, and a smaller layer inside a group."""

    def setUp(self) -> None:
        super().setUp()
        self.full = self.add_layer('full', 1, min_alpha=120)
        self.group = self.add_group('group')
        self.small = self.add_layer('small', 2, QSize(10, 8), QPoint(3, 5), self.group)
        select_rect(self.image_stack, QRect(2, 2, 12, 10))

    def _expanded(self, mode: LayerResizeMode) -> None:
        old_composite = full_render(self.image_stack)
        old_selection_bounds = self.image_stack.selection_layer.get_content_bounds()
        _, after = self.assert_undo_redo(lambda: self.image_stack.resize_canvas(
            EXPANDED_SIZE, EXPAND_OFFSET.x(), EXPAND_OFFSET.y(), mode, False))
        self.assertEqual(EXPANDED_SIZE, after.size)
        expected = create_transparent_image(EXPANDED_SIZE)
        painter = QPainter(expected)
        painter.drawImage(EXPAND_OFFSET, old_composite)
        painter.end()
        self.assert_images_equal(after.composite, expected)
        self.assertEqual(QRect(QPoint(), EXPANDED_SIZE), self.image_stack.selection_layer.transformed_bounds)
        self.assertEqual(old_selection_bounds.translated(EXPAND_OFFSET),
                         self.image_stack.selection_layer.get_content_bounds())

    def test_expand_resize_all(self) -> None:
        """RESIZE_ALL grows every image layer to the new canvas, keeping content at the offset."""
        self._expanded(LayerResizeMode.RESIZE_ALL)
        canvas = QRect(QPoint(), EXPANDED_SIZE)
        self.assertEqual(canvas, self.full.transformed_bounds)
        self.assertEqual(canvas, self.small.transformed_bounds)

    def test_expand_full_image_layers_only(self) -> None:
        """FULL_IMAGE_LAYERS_ONLY grows only layers that covered the old canvas, and moves the rest."""
        self._expanded(LayerResizeMode.FULL_IMAGE_LAYERS_ONLY)
        self.assertEqual(QRect(QPoint(), EXPANDED_SIZE), self.full.transformed_bounds)
        self.assertEqual(QRect(QPoint(3, 5) + EXPAND_OFFSET, QSize(10, 8)), self.small.transformed_bounds)

    def test_expand_resize_none(self) -> None:
        """RESIZE_NONE moves every layer by the offset without resizing it."""
        self._expanded(LayerResizeMode.RESIZE_NONE)
        self.assertEqual(QRect(EXPAND_OFFSET, CANVAS_SIZE), self.full.transformed_bounds)
        self.assertEqual(QRect(QPoint(3, 5) + EXPAND_OFFSET, QSize(10, 8)), self.small.transformed_bounds)

    def test_crop_layers(self) -> None:
        """Cropping with crop_layers cuts every layer to the new canvas, and the composite to the crop rectangle."""
        old_composite = full_render(self.image_stack)
        _, after = self.assert_undo_redo(lambda: self.image_stack.resize_canvas(
            CROP_RECT.size(), -CROP_RECT.x(), -CROP_RECT.y(), LayerResizeMode.RESIZE_NONE, True))
        self.assert_images_equal(after.composite, old_composite.copy(CROP_RECT))
        canvas = QRect(QPoint(), CROP_RECT.size())
        self.assertEqual(canvas, self.full.transformed_bounds)
        self.assertEqual(QRect(3, 5, 10, 8).translated(-CROP_RECT.topLeft()).intersected(canvas),
                         self.small.transformed_bounds)
        self.assertEqual(QRect(QPoint(), CROP_RECT.size()), self.image_stack.selection_layer.transformed_bounds)
        self.assertEqual(QRect(2, 2, 12, 10).translated(-CROP_RECT.topLeft()).intersected(canvas),
                         self.image_stack.selection_layer.get_content_bounds())

    def test_crop_without_cropping_layers(self) -> None:
        """Without crop_layers, layers keep their content outside the new canvas."""
        _, after = self.assert_undo_redo(lambda: self.image_stack.resize_canvas(
            CROP_RECT.size(), -CROP_RECT.x(), -CROP_RECT.y(), LayerResizeMode.RESIZE_NONE, False))
        self.assertEqual(QRect(-CROP_RECT.topLeft(), CANVAS_SIZE), self.full.transformed_bounds)
        self.assertEqual(CANVAS_SIZE, self.full.size)
        self.assertEqual(CROP_RECT.size(), after.size)

    def test_crop_transformed_layer(self) -> None:
        """A layer rotated by a multiple of 90 degrees is cropped in place, keeping its rotation."""
        rotated = self.add_layer('rotated', 3, QSize(12, 20))
        rotated.set_transform(QTransform().rotate(90) * QTransform.fromTranslate(26, 2))
        self.assertEqual(QRect(6, 2, 20, 12), rotated.transformed_bounds)
        old_composite = full_render(self.image_stack)
        _, after = self.assert_undo_redo(lambda: self.image_stack.resize_canvas(
            CROP_RECT.size(), -CROP_RECT.x(), -CROP_RECT.y(), LayerResizeMode.RESIZE_NONE, True))
        self.assert_images_equal(after.composite, old_composite.copy(CROP_RECT))
        self.assertEqual(QRect(0, 0, 16, 10), rotated.transformed_bounds)
        self.assertEqual((0.0, 1.0, -1.0, 0.0), (rotated.transform.m11(), rotated.transform.m12(),
                                                 rotated.transform.m21(), rotated.transform.m22()))

    def test_crop_deletes_layer_outside_canvas(self) -> None:
        """Cropping deletes a layer left with no area, and undo puts it back connected to the stack."""
        AppConfig().set(AppConfig.WARN_WHEN_CROP_DELETES_LAYERS, False)
        outside = self.add_layer('outside', 4, QSize(4, 4), QPoint(26, 18))
        self.image_stack.move_layer(outside, self.image_stack.layer_stack, 0)
        before, _ = self.assert_undo_redo(lambda: self.image_stack.resize_canvas(
            CROP_RECT.size(), -CROP_RECT.x(), -CROP_RECT.y(), LayerResizeMode.RESIZE_NONE, True))
        self.assertFalse(self.image_stack.layer_stack.contains_recursive(outside))
        UndoStack().undo()
        self.capture().assert_matches(before, 'undo')
        # The restored layer's edits must still reach the composite:
        with outside.borrow_image() as image:
            assert image is not None
            image.fill(Qt.GlobalColor.blue)
        self.image_stack.flush_render()
        self.assertEqual(QColor(Qt.GlobalColor.blue), self.image_stack.qimage().pixelColor(27, 19))

    @patch(ERROR_DIALOG)
    def test_crop_blocked_by_locked_layer(self, error_dialog) -> None:
        """Cropping a locked layer shows an error and changes nothing."""
        self.small.set_locked(True)
        UndoStack().clear()
        before = self.capture()
        self.image_stack.resize_canvas(CROP_RECT.size(), -CROP_RECT.x(), -CROP_RECT.y(),
                                       LayerResizeMode.RESIZE_NONE, True)
        error_dialog.assert_called_once()
        self.capture().assert_matches(before, 'blocked crop')
        self.assertEqual(0, UndoStack().undo_count())

    @patch(CONFIRM_RENDER_TEXT, return_value=True)
    def test_crop_converts_text_layer(self, _) -> None:
        """Cropping through a text layer converts it to an image layer, which undo turns back into the text layer."""
        text_data = TextRect()
        text_data.text = 'text'
        text_data.size = QSize(24, 16)
        text_layer = self.image_stack.create_text_layer(text_data, self.image_stack.layer_stack, 0)
        self.assert_undo_redo(lambda: self.image_stack.resize_canvas(
            CROP_RECT.size(), -CROP_RECT.x(), -CROP_RECT.y(), LayerResizeMode.RESIZE_NONE, True))
        self.assertFalse(self.image_stack.layer_stack.contains_recursive(text_layer))
        self.assertEqual([], self.image_stack.text_layers)
        UndoStack().undo()
        self.assertIsInstance(self.image_stack.layer_stack.child_layers[0], TextLayer)
        self.assertIs(text_layer, self.image_stack.layer_stack.child_layers[0])


if __name__ == '__main__':
    unittest.main()
