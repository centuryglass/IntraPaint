"""Tests ImageStack copy, cut, clear and paste of selected content, from image layers, transformed layers and groups.

Pasted content is checked by rendering: with the source hidden, the pasted layer must render the same pixels the
source rendered inside the selection.
"""
import unittest

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPainter, QTransform

from src.image.composite_mode import CompositeMode
from src.image.layers.image_layer import ImageLayer
from src.image.layers.layer import Layer
from src.undo_stack import UndoStack
from test.image.layers.image_stack_state import ImageStackOpTestCase, masked_to_rect, select_rect
from test.render_assertions import full_render

SELECTED = QRect(5, 4, 15, 12)


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
        """A rotated layer's copy keeps its rotation, and renders the same selected pixels."""
        self.top.set_transform(QTransform().rotate(90) * QTransform.fromTranslate(16, 1))
        pasted = self.assert_copy_pastes(self.top)
        self.assertEqual(self.top.transform.m12(), pasted.transform.m12())

    def test_copy_paste_group(self) -> None:
        """A group's copy is its rendered content, with the group's opacity and its children's modes applied."""
        self.group.set_opacity(0.6)
        self.inner_a.set_composition_mode(CompositeMode.DIFFERENCE)
        self.assert_copy_pastes(self.group)

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
