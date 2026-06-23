"""Tests image compositing functions"""
import os
import sys
import unittest

from PySide6.QtCore import QPointF, QPoint
from PySide6.QtGui import QImage, QPainter, QPainterPath, QLinearGradient, QGradient
from PySide6.QtWidgets import QApplication

from src.image.composite_mode import CompositeMode
from src.util.visual.image_utils import create_transparent_image

INIT_IMAGE = 'test/resources/test_images/source.png'
HUE_TEST_IMAGE = 'test/resources/test_images/hue_test.png'
SATURATION_TEST_IMAGE = 'test/resources/test_images/saturation_test.png'
LUMINANCE_TEST_IMAGE = 'test/resources/test_images/luminance_test.png'
app = QApplication.instance() or QApplication(sys.argv)

def save_temporary(name, expected, actual):
    expected.save(f'expected_{name}.png')
    actual.save(f'actual_{name}.png')

def clear_temporary(name):
    for img_path in (f'expected_{name}.png', f'actual_{name}.png'):
        if os.path.isfile(img_path):
            os.remove(img_path)


class CompositeModeTest(unittest.TestCase):
    """Tests timage compositing functions"""

    def setUp(self) -> None:
        while os.path.basename(os.getcwd()) not in ('IntraPaint', ''):
            os.chdir('..')
        assert os.path.basename(os.getcwd()) == 'IntraPaint'
        self._base_image = QImage(INIT_IMAGE).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self._overlay_image = create_transparent_image(self._base_image.size())
        painter = QPainter(self._overlay_image)
        path = QPainterPath()
        path.addEllipse(self._overlay_image.rect().adjusted(20, 20, -20, -20))
        gradient = QGradient(QGradient.Preset.AlchemistLab)
        painter.fillPath(path, gradient)
        painter.end()

    def test_hue_blend(self) -> None:
        """Test the custom hue compositing function."""
        base = self._base_image.copy()
        CompositeMode.hue_composite_blend(self._overlay_image, base)
        expected_image = QImage(HUE_TEST_IMAGE).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        save_temporary('hue_test', expected_image, base)
        self.assertEqual(expected_image, base)
        clear_temporary('hue_test')

    def test_saturation_blend(self) -> None:
        """Test the custom saturation compositing function."""
        base = self._base_image.copy()
        CompositeMode.saturation_composite_blend(self._overlay_image, base)
        expected_image = QImage(SATURATION_TEST_IMAGE).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        save_temporary('saturation_test', expected_image, base)
        self.assertEqual(expected_image, base)
        clear_temporary('saturation_test')

    def test_luminance_blend(self) -> None:
        """Test the custom luminance compositing function."""
        base = self._base_image.copy()
        CompositeMode.luminosity_composite_blend(self._overlay_image, base)
        expected_image = QImage(LUMINANCE_TEST_IMAGE).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        save_temporary('luminance_test', expected_image, base)
        self.assertEqual(expected_image, base)
        clear_temporary('luminance_test')