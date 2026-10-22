"""Tests the LayerGroup class"""
import sys
import unittest
from typing import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QTransform
from PySide6.QtWidgets import QApplication

from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer_group import LayerGroup
from src.undo_stack import UndoStack
from src.util.visual.image_utils import image_data_as_numpy_8bit_readonly, image_is_fully_transparent
from test.base_test_case import IntraPaintTestCase

IMG_SIZE = QSize(512, 512)
GEN_AREA_SIZE = QSize(300, 300)
MIN_GEN_AREA = QSize(8, 8)
MAX_GEN_AREA = QSize(999, 999)
app = QApplication.instance() or QApplication(sys.argv)


class LayerGroupTest(IntraPaintTestCase):
    """Tests the LayerGroup class"""

    def setUp(self) -> None:
        super().setUp()
        UndoStack().clear()
        self.image_stack = ImageStack(IMG_SIZE, GEN_AREA_SIZE, MIN_GEN_AREA, MAX_GEN_AREA)
        self.group = self.image_stack.create_layer_group('group')
        self.layers = [self.image_stack.create_layer(f'layer {i}', layer_parent=self.group, layer_index=i)
                       for i in range(2)]
        self.layers[1].transform = QTransform.fromTranslate(100, 50)
        UndoStack().clear()

    def assert_one_undo_step(self, flip: Callable[[], None]) -> None:
        """Asserts that a flip changes every layer, and that one undo reverts all of them."""
        initial_transforms = [layer.transform for layer in self.layers]
        flip()
        for layer, initial_transform in zip(self.layers, initial_transforms):
            self.assertNotEqual(layer.transform, initial_transform)
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assertEqual([layer.transform for layer in self.layers], initial_transforms)

    def test_flip_horizontal_is_one_undo_step(self) -> None:
        """Flipping a group horizontally is undone in one step."""
        self.assert_one_undo_step(self.group.flip_horizontal)

    def test_flip_vertical_is_one_undo_step(self) -> None:
        """Flipping a group vertically is undone in one step."""
        self.assert_one_undo_step(self.group.flip_vertical)

    def test_visibility_toggles_ignore_locks(self) -> None:
        """Locking a group or its child never blocks showing or hiding either."""
        child = self.layers[0]
        self.group.set_locked(True)
        child.visible = False
        self.assertFalse(child.visible)
        child.visible = True
        self.assertTrue(child.visible)
        self.group.visible = False
        self.assertFalse(self.group.visible)
        self.group.visible = True
        self.assertTrue(self.group.visible)

    def test_canvas_resize_undo_keeps_child_visibility_in_hidden_group(self) -> None:
        """Undoing a canvas resize restores each child's own visibility, not the hidden group's."""
        text_layer = self.image_stack.create_text_layer(layer_parent=self.group)
        self.layers[1].visible = False
        self.group.visible = False
        self.image_stack.resize_canvas(QSize(600, 600), 10, 10)
        UndoStack().undo()
        self.group.visible = True
        self.assertEqual([layer.visible for layer in (*self.layers, text_layer)], [True, False, True])

    def test_copies_in_hidden_group_keep_own_visibility(self) -> None:
        """Copying a layer or group inside a hidden group keeps the copy's own visibility."""
        nested = self.image_stack.create_layer_group('nested', layer_parent=self.group)
        self.image_stack.create_layer('nested child', layer_parent=nested)
        text_layer = self.image_stack.create_text_layer(layer_parent=self.group)
        self.group.visible = False
        copies = [layer.copy() for layer in (self.layers[0], nested, text_layer)]
        copies.append(text_layer.copy_as_image_layer())
        self.assertTrue(all(copy.visible for copy in copies))
        self.assertTrue(copies[1].get_layer_by_index(0).visible)

    def _nested_group(self) -> tuple[LayerGroup, ImageLayer]:
        """Adds a nested group holding one layer inside `self.group`, and returns both."""
        nested = self.image_stack.create_layer_group('nested', layer_parent=self.group)
        child = self.image_stack.create_layer('nested child', layer_parent=nested)
        UndoStack().clear()
        return nested, child

    def test_visibility_toggle_changes_only_its_layer(self) -> None:
        """Showing or hiding a layer inside hidden groups changes no other layer, and one undo reverts it."""
        nested, child = self._nested_group()
        self.group.visible = False
        everything = [self.group, nested, child, *self.layers]
        before = [layer.visible for layer in everything]
        child.visible = False
        self.assertEqual([layer.visible for layer in everything], [False, True, False, True, True])
        child.visible = True
        self.assertEqual([layer.visible for layer in everything], before)
        UndoStack().undo()
        self.assertFalse(child.visible)
        UndoStack().undo()
        self.assertEqual([layer.visible for layer in everything], before)

    def test_shown_and_hidden_parent(self) -> None:
        """A layer is shown only when it and every group it is in are visible, and its nearest hidden group is
        reported."""
        nested, child = self._nested_group()
        self.assertEqual((child.shown, child.parent_hidden, child.hidden_parent), (True, False, None))
        self.group.visible = False
        self.assertEqual((child.shown, child.hidden_parent), (False, self.group))
        nested.visible = False
        self.assertEqual((child.shown, child.hidden_parent, nested.hidden_parent), (False, nested, self.group))
        self.group.visible = True
        nested.visible = True
        child.visible = False
        self.assertEqual((child.shown, child.parent_hidden), (False, False))

    def test_hiding_a_group_notifies_the_layers_inside(self) -> None:
        """Hiding a group sends visibility_changed from every layer inside it, with the group as the sender."""
        nested, child = self._nested_group()
        received = []
        for layer in (nested, child):
            layer.visibility_changed.connect(lambda source, visible: received.append((source, visible)))
        self.group.visible = False
        self.assertEqual(received, [(self.group, False), (self.group, False)])

    def test_nested_group_renders_while_its_parent_is_hidden(self) -> None:
        """A nested group's own image doesn't depend on the visibility of the groups it is in."""
        nested, child = self._nested_group()
        self.group.visible = False
        filled = QImage(child.size, QImage.Format.Format_ARGB32_Premultiplied)
        filled.fill(Qt.GlobalColor.red)
        child.image = filled
        self.image_stack.flush_render()
        self.assertFalse(image_is_fully_transparent(image_data_as_numpy_8bit_readonly(nested.get_qimage())))


if __name__ == '__main__':
    unittest.main()
