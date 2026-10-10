"""Tests the image_stack_utils module"""
import sys
import unittest

from PIL import Image
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QImage, QTransform
from PySide6.QtWidgets import QApplication

from src.image.layers.image_stack import ImageStack
from src.image.layers.image_stack_utils import image_stack_color_at_point, scale_all_layers
from src.undo_stack import UndoStack
from test.base_test_case import IntraPaintTestCase

IMG_SIZE = QSize(512, 512)
GEN_AREA_SIZE = QSize(300, 300)
MIN_GEN_AREA = QSize(8, 8)
MAX_GEN_AREA = QSize(999, 999)
app = QApplication.instance() or QApplication(sys.argv)


class ImageStackUtilsTest(IntraPaintTestCase):
    """Tests the image_stack_utils module"""

    def setUp(self) -> None:
        super().setUp()
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

    def test_color_at_point_outside_canvas(self) -> None:
        """Points outside the canvas sample layer content that extends past it, and are black outside all content."""
        image_stack = ImageStack(QSize(100, 100), QSize(100, 100), MIN_GEN_AREA, MAX_GEN_AREA)
        layer_image = QImage(QSize(300, 300), QImage.Format.Format_ARGB32_Premultiplied)
        layer_image.fill(Qt.GlobalColor.blue)
        layer = image_stack.create_layer('oversized', layer_image)
        layer.set_transform(QTransform.fromTranslate(-100, -100))
        self.assertEqual(image_stack.merged_layer_bounds, QRect(-100, -100, 300, 300))
        blue = QColor(Qt.GlobalColor.blue)
        for point in (QPoint(50, 50), QPoint(-50, -50), QPoint(150, 150), QPoint(-100, -100), QPoint(199, 199),
                      QPoint(-50, 150), QPoint(150, -50)):
            self.assertEqual(image_stack_color_at_point(image_stack, point), blue, f'at {point.toTuple()}')
        black = QColor(0, 0, 0)
        for point in (QPoint(-101, 0), QPoint(0, -101), QPoint(200, 0), QPoint(0, 200), QPoint(250, 250)):
            self.assertEqual(image_stack_color_at_point(image_stack, point), black, f'at {point.toTuple()}')


if __name__ == '__main__':
    unittest.main()
