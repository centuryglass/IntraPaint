"""Tests the LayerGroup class"""
import sys
import unittest
from typing import Callable

from PySide6.QtCore import QSize
from PySide6.QtGui import QTransform
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.undo_stack import UndoStack

IMG_SIZE = QSize(512, 512)
GEN_AREA_SIZE = QSize(300, 300)
MIN_GEN_AREA = QSize(8, 8)
MAX_GEN_AREA = QSize(999, 999)
app = QApplication.instance() or QApplication(sys.argv)


class LayerGroupTest(unittest.TestCase):
    """Tests the LayerGroup class"""

    def setUp(self) -> None:
        AppConfig()._reset()
        KeyConfig()._reset()
        Cache()._reset()
        # Without time-based merging, only explicit grouping can combine actions in the undo history:
        AppConfig().set(AppConfig.UNDO_MERGE_INTERVAL, 0.0)
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


if __name__ == '__main__':
    unittest.main()
