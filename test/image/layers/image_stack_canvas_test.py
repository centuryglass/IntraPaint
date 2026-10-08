"""Tests ImageStack.resize_canvas and layer_to_image_size: expanding and cropping the canvas with each
LayerResizeMode, and fitting single layers and groups to it, with undo and redo."""
import unittest
from unittest.mock import patch

import pytest

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QTransform

from src.config.application_config import AppConfig
from src.image.layers.image_layer import ImageLayer
from src.image.layers.layer_resize_mode import LayerResizeMode
from src.image.layers.text_layer import TextLayer
from src.image.text_rect import TextRect
from src.undo_stack import UndoStack
from src.util.visual.image_utils import create_transparent_image


def _text_data() -> TextRect:
    text_data = TextRect()
    text_data.text = 'text'
    text_data.size = QSize(24, 16)
    return text_data
from test.image.layers.image_stack_state import CANVAS_SIZE, ImageStackOpTestCase, masked_to_rect, select_rect
from test.render_assertions import full_render

ERROR_DIALOG = 'src.image.layers.image_stack.show_error_dialog'
CONFIRM_RENDER_TEXT = 'src.image.layers.text_layer.request_confirmation'

ISSUE_ROTATED_EXPAND = ('https://github.com/centuryglass/IntraPaint/issues/236: expanding a layer rotated by a'
                        ' non-right angle changes its edge pixels')

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
        text_layer = self.image_stack.create_text_layer(_text_data(), self.image_stack.layer_stack, 0)
        self.assert_undo_redo(lambda: self.image_stack.resize_canvas(
            CROP_RECT.size(), -CROP_RECT.x(), -CROP_RECT.y(), LayerResizeMode.RESIZE_NONE, True))
        self.assertFalse(self.image_stack.layer_stack.contains_recursive(text_layer))
        self.assertEqual([], self.image_stack.text_layers)
        UndoStack().undo()
        self.assertIsInstance(self.image_stack.layer_stack.child_layers[0], TextLayer)
        self.assertIs(text_layer, self.image_stack.layer_stack.child_layers[0])

    def test_expand_right_angle_rotated_layer(self) -> None:
        """RESIZE_ALL grows a layer rotated by 90 degrees to the new canvas without changing its pixels."""
        rotated = self.add_layer('rotated', 3, QSize(12, 20), min_alpha=60)
        rotated.set_transform(QTransform().rotate(90) * QTransform.fromTranslate(26, 2))
        self.image_stack.move_layer(rotated, self.image_stack.layer_stack, 0)
        self._expanded(LayerResizeMode.RESIZE_ALL)
        self.assertEqual(QRect(QPoint(), EXPANDED_SIZE), rotated.transformed_bounds)

    @pytest.mark.xfail(strict=True, reason=ISSUE_ROTATED_EXPAND)
    def test_expand_rotated_layer(self) -> None:
        """RESIZE_ALL grows a layer rotated by 30 degrees to the new canvas without changing its pixels."""
        rotated = self.add_layer('rotated', 3, QSize(10, 10))
        rotated.set_transform(QTransform().rotate(30) * QTransform.fromTranslate(16, 4))
        self.image_stack.move_layer(rotated, self.image_stack.layer_stack, 0)
        self._expanded(LayerResizeMode.RESIZE_ALL)

    def test_crop_rotated_layer(self) -> None:
        """Cropping through a layer rotated by 45 degrees bakes its rotation into its pixels, leaving the cropped
        composite unchanged."""
        rotated = self.add_layer('rotated', 3, QSize(10, 10), min_alpha=60)
        rotated.set_transform(QTransform().rotate(45) * QTransform.fromTranslate(16, 4))
        self.image_stack.move_layer(rotated, self.image_stack.layer_stack, 0)
        old_composite = full_render(self.image_stack)
        _, after = self.assert_undo_redo(lambda: self.image_stack.resize_canvas(
            CROP_RECT.size(), -CROP_RECT.x(), -CROP_RECT.y(), LayerResizeMode.RESIZE_NONE, True))
        self.assert_images_equal(after.composite, old_composite.copy(CROP_RECT))
        self.assertEqual(QTransform.fromTranslate(rotated.transform.dx(), rotated.transform.dy()), rotated.transform)

    def test_crop_moves_selection_and_context_pins(self) -> None:
        """Cropping moves the selection's pixels with the canvas, drops context pins left outside it, and undo
        restores both."""
        selection_layer = self.image_stack.selection_layer
        old_selection = masked_to_rect(selection_layer.image, CROP_RECT).copy(CROP_RECT)
        selection_layer.set_context_pins([QPoint(8, 8), QPoint(30, 20)], False)
        self.assert_undo_redo(lambda: self.image_stack.resize_canvas(
            CROP_RECT.size(), -CROP_RECT.x(), -CROP_RECT.y(), LayerResizeMode.RESIZE_NONE, True))
        self.assert_images_equal(selection_layer.image, old_selection)
        self.assertEqual([QPoint(2, 4)], selection_layer.context_pins)
        UndoStack().undo()
        self.assertEqual([QPoint(8, 8), QPoint(30, 20)], selection_layer.context_pins)


class LayerToImageSizeTest(ImageStackOpTestCase):
    """Tests ImageStack.layer_to_image_size on image, transformed and text layers, and on groups."""

    def setUp(self) -> None:
        super().setUp()
        self.group = self.add_group('group')
        self.small = self.add_layer('small', 1, QSize(10, 8), QPoint(3, 5), self.group, min_alpha=60)
        self.overflow = self.add_layer('overflow', 2, QSize(20, 20), QPoint(20, 12), self.group, min_alpha=60)
        self.full = self.add_layer('full', 3, min_alpha=60)

    def assert_fits_canvas(self, layer) -> None:
        """Resizes layer as one undo step, checking that the composite is unchanged and the layer fills the canvas
        with no transform."""
        self.assert_composite_kept(lambda: self.image_stack.layer_to_image_size(layer))
        self.assertEqual(QRect(QPoint(), CANVAS_SIZE), layer.bounds)
        self.assertTrue(layer.transform.isIdentity())

    def assert_composite_kept(self, operation) -> None:
        """Checks operation with assert_undo_redo, and that it leaves the composite unchanged."""
        before, after = self.assert_undo_redo(operation)
        self.assert_images_equal(after.composite, before.composite, 'composite changed')

    def assert_no_change(self, operation) -> None:
        """Checks that operation adds no undo step and changes nothing."""
        UndoStack().clear()
        before = self.capture()
        operation()
        self.capture().assert_matches(before, 'unchanged')
        self.assertEqual(0, UndoStack().undo_count())

    def test_grow_layer(self) -> None:
        """A small offset layer grows to the canvas, keeping its pixels in place."""
        self.assert_fits_canvas(self.small)

    def test_crop_layer(self) -> None:
        """A layer extending past the canvas loses its content outside the canvas."""
        self.assert_fits_canvas(self.overflow)

    def test_rotated_layer(self) -> None:
        """A rotated layer's rotation is baked into its pixels, which render the same as before."""
        self.small.set_transform(QTransform().rotate(30) * QTransform.fromTranslate(16, 4))
        self.assert_fits_canvas(self.small)

    def test_canvas_sized_layer_does_nothing(self) -> None:
        """A layer that already fills the canvas is left alone, with no error."""
        with patch(ERROR_DIALOG) as error_dialog:
            self.assert_no_change(lambda: self.image_stack.layer_to_image_size(self.full))
        error_dialog.assert_not_called()

    @patch(ERROR_DIALOG)
    def test_locked_layer_blocked(self, error_dialog) -> None:
        """A locked layer shows an error and changes nothing."""
        self.small.set_locked(True)
        self.assert_no_change(lambda: self.image_stack.layer_to_image_size(self.small))
        error_dialog.assert_called_once()

    @patch(ERROR_DIALOG)
    def test_group(self, error_dialog) -> None:
        """A group resizes each unlocked image layer it holds in one undo step, skipping locked and canvas-sized
        layers."""
        self.full.set_transform(QTransform())
        self.image_stack.move_layer(self.full, self.group, 0)
        locked = self.add_layer('locked', 4, QSize(6, 6), QPoint(1, 1), self.group)
        locked.set_locked(True)
        self.assert_composite_kept(lambda: self.image_stack.layer_to_image_size(self.group))
        error_dialog.assert_not_called()
        canvas = QRect(QPoint(), CANVAS_SIZE)
        self.assertEqual([canvas, canvas, canvas, QRect(1, 1, 6, 6)],
                         [layer.transformed_bounds for layer in self.group.child_layers])

    @patch(CONFIRM_RENDER_TEXT, return_value=True)
    def test_text_layer_outside_canvas(self, _) -> None:
        """A text layer reaching past the canvas converts to an image layer, which undo turns back into text."""
        text_layer = self.image_stack.create_text_layer(_text_data(), self.image_stack.layer_stack, 0)
        text_layer.set_transform(QTransform.fromTranslate(16, 12))
        self.assert_composite_kept(lambda: self.image_stack.layer_to_image_size(text_layer))
        converted = self.image_stack.layer_stack.child_layers[0]
        self.assertIsInstance(converted, ImageLayer)
        self.assertEqual(QRect(QPoint(), CANVAS_SIZE), converted.transformed_bounds)
        UndoStack().undo()
        self.assertIs(text_layer, self.image_stack.layer_stack.child_layers[0])

    @patch(CONFIRM_RENDER_TEXT, return_value=False)
    def test_text_layer_conversion_declined(self, _) -> None:
        """Declining to convert a text layer leaves it unchanged."""
        text_layer = self.image_stack.create_text_layer(_text_data(), self.image_stack.layer_stack, 0)
        text_layer.set_transform(QTransform.fromTranslate(16, 12))
        self.assert_no_change(lambda: self.image_stack.layer_to_image_size(text_layer))

    @patch(CONFIRM_RENDER_TEXT)
    def test_text_layer_inside_canvas(self, confirm) -> None:
        """A text layer inside the canvas is left alone without asking to convert it."""
        text_layer = self.image_stack.create_text_layer(_text_data(), self.image_stack.layer_stack, 0)
        self.assert_no_change(lambda: self.image_stack.layer_to_image_size(text_layer))
        confirm.assert_not_called()


if __name__ == '__main__':
    unittest.main()
