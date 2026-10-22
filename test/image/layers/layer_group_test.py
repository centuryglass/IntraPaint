"""Tests the LayerGroup class"""
import sys
import unittest
from typing import Callable

from PySide6.QtCore import QSize
from PySide6.QtGui import QTransform
from PySide6.QtWidgets import QApplication

from src.image.layers.image_stack import ImageStack
from src.undo_stack import UndoStack
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


if __name__ == '__main__':
    unittest.main()
