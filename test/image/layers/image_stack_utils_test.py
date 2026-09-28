"""Tests the image_stack_utils module"""
import sys
import unittest

from PIL import Image
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.image.layers.image_stack_utils import scale_all_layers
from src.undo_stack import UndoStack

IMG_SIZE = QSize(512, 512)
GEN_AREA_SIZE = QSize(300, 300)
MIN_GEN_AREA = QSize(8, 8)
MAX_GEN_AREA = QSize(999, 999)
app = QApplication.instance() or QApplication(sys.argv)


class ImageStackUtilsTest(unittest.TestCase):
    """Tests the image_stack_utils module"""

    def setUp(self) -> None:
        AppConfig()._reset()
        KeyConfig()._reset()
        Cache()._reset()
        # Without time-based merging, only explicit grouping can combine actions in the undo history. Scaling a large
        # image takes long enough per layer that time-based merging doesn't combine the steps either.
        AppConfig().set(AppConfig.UNDO_MERGE_INTERVAL, 0.0)
        UndoStack().clear()
        self.image_stack = ImageStack(IMG_SIZE, GEN_AREA_SIZE, MIN_GEN_AREA, MAX_GEN_AREA)
        layer_image = QImage(IMG_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
        layer_image.fill(Qt.GlobalColor.red)
        self.layers = [self.image_stack.create_layer(f'layer {i}', layer_image) for i in range(2)]
        UndoStack().clear()

    def test_scale_all_layers_is_one_undo_step(self) -> None:
        """Scaling the image is undone in one step, restoring the image size and every layer's content."""
        initial_images = [layer.image for layer in self.layers]
        scale_all_layers(self.image_stack, 256, 128, Image.Resampling.NEAREST)
        self.assertEqual(self.image_stack.size, QSize(256, 128))
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assertEqual(self.image_stack.size, IMG_SIZE)
        self.assertEqual([layer.image for layer in self.layers], initial_images)


if __name__ == '__main__':
    unittest.main()
