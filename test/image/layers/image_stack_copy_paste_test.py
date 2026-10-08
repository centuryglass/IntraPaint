"""Tests ImageStack copy, cut, clear and paste of selected content, from image layers, transformed layers and groups.

Pasted content is checked by rendering: with the source hidden, the pasted layer must render the same pixels the
source rendered inside the selection.
"""
import unittest
from unittest.mock import patch

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QImage, QPainter, QTransform

from src.image.composite_mode import CompositeMode
from src.image.layers.image_layer import ImageLayer
from src.image.layers.layer import Layer
from src.image.layers.text_layer import TextLayer
from src.image.text_rect import TextRect
from src.undo_stack import UndoStack
from test.image.layers.image_stack_state import ImageStackOpTestCase, masked_to_rect, select_rect
from test.render_assertions import full_render

SELECTED = QRect(5, 4, 15, 12)
CONFIRM_RENDER_TEXT = 'src.image.layers.text_layer.request_confirmation'


class CopyPasteTest(ImageStackOpTestCase):
    """Builds [top, group [inner a, inner b], bottom] with a rectangular selection."""

    def setUp(self) -> None:
        super().setUp()
        self.top, self.group, self.inner_a, self.inner_b, self.bottom = self.add_nested_layers()
        self.stack = self.image_stack.layer_stack
        select_rect(self.image_stack, SELECTED)

    def render_alone(self, layer: Layer) -> QImage:
        """Returns the canvas render with every other top-level layer hidden."""
        hidden = [other for other in self.stack.child_layers if other is not layer and other.visible]
        for other in hidden:
            other.set_visible(False)
        image = full_render(self.image_stack)
        for other in hidden:
            other.set_visible(True)
        return image

    def paste(self) -> ImageLayer:
        """Pastes as one undo step, checked with undo and redo, and returns the pasted layer."""
        _, after = self.assert_undo_redo(self.image_stack.paste)
        pasted = after.active_layer
        assert isinstance(pasted, ImageLayer)
        self.assertEqual('Paste layer', pasted.name)
        return pasted

    def assert_copy_pastes(self, source: Layer) -> ImageLayer:
        """Copies source's selected content and pastes it above the top layer, checking the pasted layer renders the
        pixels source rendered inside the selection."""
        expected = masked_to_rect(self.render_alone(source), SELECTED)
        UndoStack().clear()
        before = self.capture()
        self.image_stack.copy_selected(source)
        self.capture().assert_matches(before, 'copy')
        self.image_stack.active_layer = self.top
        pasted = self.paste()
        self.assertEqual(0, self.stack.get_layer_index(pasted))
        self.assert_images_equal(self.render_alone(pasted), expected)
        return pasted

    def test_copy_paste_image_layer(self) -> None:
        """Pasting a layer's selected content adds a layer above it, cropped to the copied content."""
        pasted = self.assert_copy_pastes(self.top)
        self.assertEqual(SELECTED.intersected(self.top.transformed_bounds), pasted.transformed_bounds)

    def test_copy_paste_transformed_layer(self) -> None:
        """A rotated, translucent layer's copy keeps its rotation and opacity, and renders the same selected pixels."""
        self.top.set_transform(QTransform().rotate(90) * QTransform.fromTranslate(16, 1))
        self.top.set_opacity(0.7)
        pasted = self.assert_copy_pastes(self.top)
        self.assertEqual(self.top.transform.m12(), pasted.transform.m12())
        self.assertEqual(0.7, pasted.opacity)

    def test_copy_paste_keeps_opacity_and_mode(self) -> None:
        """A pasted layer keeps the copied layer's opacity and composite mode, in every mode."""
        for mode in CompositeMode:
            with self.subTest(mode=mode.name):
                UndoStack().clear()
                self.setUp()
                self.top.set_opacity(0.5)
                self.top.set_composition_mode(mode)
                pasted = self.assert_copy_pastes(self.top)
                self.assertEqual((0.5, mode), (pasted.opacity, pasted.composition_mode))

    def test_cut_paste_translucent_blended_layer(self) -> None:
        """Cutting and pasting a translucent layer in a non-Normal mode restores the composite exactly."""
        self.top.set_opacity(0.4)
        self.top.set_composition_mode(CompositeMode.MULTIPLY)
        self.image_stack.active_layer = self.top
        original = full_render(self.image_stack)
        self.assert_undo_redo(lambda: self.image_stack.cut_selected(self.top))
        pasted = self.paste()
        self.assertEqual((0.4, CompositeMode.MULTIPLY), (pasted.opacity, pasted.composition_mode))
        self.assert_images_equal(full_render(self.image_stack), original)

    def test_copy_paste_group(self) -> None:
        """A group's copy is its rendered content, with the group's opacity and its children's modes applied."""
        self.group.set_opacity(0.6)
        self.inner_a.set_composition_mode(CompositeMode.DIFFERENCE)
        self.group.set_composition_mode(CompositeMode.SCREEN)
        pasted = self.assert_copy_pastes(self.group)
        # The group's opacity and mode are already in the rendered pixels:
        self.assertEqual((1.0, CompositeMode.NORMAL), (pasted.opacity, pasted.composition_mode))

    def test_paste_into_group_above_active_layer(self) -> None:
        """Pasting while a layer in a group is active puts the pasted layer above it in the group."""
        self.image_stack.copy_selected(self.top)
        self.image_stack.active_layer = self.inner_b
        pasted = self.paste()
        self.assertEqual([self.inner_a, pasted, self.inner_b], self.group.child_layers)

    def test_paste_nothing_copied(self) -> None:
        """Paste does nothing before anything is copied."""
        UndoStack().clear()
        before = self.capture()
        self.image_stack.paste()
        self.capture().assert_matches(before, 'paste')
        self.assertEqual(0, UndoStack().undo_count())

    def test_cut_paste_image_layer(self) -> None:
        """Cutting clears the selected pixels in one undo step, and pasting the cut content restores the composite."""
        original = full_render(self.image_stack)
        before_top = self.render_alone(self.top)
        self.image_stack.active_layer = self.top
        self.assert_undo_redo(lambda: self.image_stack.cut_selected(self.top))
        self.assert_images_equal(self.render_alone(self.top), self._cleared(before_top, SELECTED))
        self.paste()
        self.assert_images_equal(full_render(self.image_stack), original)

    def test_cut_paste_group(self) -> None:
        """Cutting from a group clears the selection from every child, and pasting puts the group's pixels back."""
        self.group.set_opacity(0.6)
        self.inner_a.set_composition_mode(CompositeMode.MULTIPLY)
        self.top.set_visible(False)
        self.bottom.set_visible(False)
        original = full_render(self.image_stack)
        self.assert_undo_redo(lambda: self.image_stack.cut_selected(self.group))
        self.assert_images_equal(full_render(self.image_stack), self._cleared(original, SELECTED))
        self.image_stack.active_layer = self.top
        self.paste()
        self.assert_images_equal(full_render(self.image_stack), original)

    def test_clear_selected_rotated_child(self) -> None:
        """Clearing from a group clears a rotated child's pixels inside the selection only."""
        self.inner_b.set_transform(QTransform().rotate(90) * QTransform.fromTranslate(24, 2))
        before_group = self.render_alone(self.group)
        self.assert_undo_redo(lambda: self.image_stack.clear_selected(self.group))
        self.assert_images_equal(self.render_alone(self.group), self._cleared(before_group, SELECTED))

    def test_copy_with_mask(self) -> None:
        """copy_selected with an explicit mask copies the masked pixels instead of the selection."""
        mask_rect = QRect(1, 1, 6, 4)
        mask = QImage(self.top.size, QImage.Format.Format_ARGB32_Premultiplied)
        mask.fill(Qt.GlobalColor.transparent)
        painter = QPainter(mask)
        painter.fillRect(mask_rect, Qt.GlobalColor.black)
        painter.end()
        copied = self.image_stack.copy_selected(self.top, mask)
        assert copied is not None
        self.assert_images_equal(copied, self.top.image.copy(mask_rect))
        pasted = self.paste()
        self.assertEqual(mask_rect.translated(self.top.transformed_bounds.topLeft()), pasted.transformed_bounds)

    def _add_text_layer(self) -> TextLayer:
        text_data = TextRect()
        text_data.text = 'text'
        text_data.size = QSize(24, 16)
        return self.image_stack.create_text_layer(text_data, self.stack, 0)

    @patch(CONFIRM_RENDER_TEXT, return_value=True)
    def test_cut_paste_text_layer(self, _) -> None:
        """Cutting from a text layer converts it to an image layer in one undo step, and pasting the cut content
        restores the composite."""
        text_layer = self._add_text_layer()
        original = full_render(self.image_stack)
        self.assert_undo_redo(lambda: self.image_stack.cut_selected(text_layer))
        self.assertEqual([], self.image_stack.text_layers)
        self.image_stack.active_layer = self.stack.child_layers[0]
        self.paste()
        self.assert_images_equal(full_render(self.image_stack), original)

    @patch(CONFIRM_RENDER_TEXT, return_value=False)
    def test_cut_text_layer_declined(self, _) -> None:
        """Declining to convert a text layer cancels the cut, and keeps the earlier copy for paste."""
        text_layer = self._add_text_layer()
        self.image_stack.copy_selected(self.top)
        UndoStack().clear()
        before = self.capture()
        self.image_stack.cut_selected(text_layer)
        self.capture().assert_matches(before, 'declined cut')
        self.assertEqual(0, UndoStack().undo_count())
        self.image_stack.active_layer = self.top
        pasted = self.paste()
        self.assertEqual(SELECTED.intersected(self.top.transformed_bounds), pasted.transformed_bounds)

    @staticmethod
    def _cleared(image: QImage, rect: QRect) -> QImage:
        cleared = image.copy()
        painter = QPainter(cleared)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(rect, Qt.GlobalColor.transparent)
        painter.end()
        return cleared


if __name__ == '__main__':
    unittest.main()
