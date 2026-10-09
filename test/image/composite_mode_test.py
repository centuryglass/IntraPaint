"""Tests image compositing functions"""
import sys

from PySide6.QtCore import QPointF, QPoint
from PySide6.QtGui import QImage, QPainter, QPainterPath, QLinearGradient, QGradient
from PySide6.QtWidgets import QApplication

from src.image.composite_mode import CompositeMode
from src.util.visual.image_utils import create_transparent_image
from test.base_test_case import IntraPaintTestCase

INIT_IMAGE = 'test/resources/test_images/source.png'
HUE_TEST_IMAGE = 'test/resources/test_images/hue_test.png'
SATURATION_TEST_IMAGE = 'test/resources/test_images/saturation_test.png'
LUMINANCE_TEST_IMAGE = 'test/resources/test_images/luminance_test.png'
app = QApplication.instance() or QApplication(sys.argv)


class CompositeModeTest(IntraPaintTestCase):
    """Tests image compositing functions"""

    def setUp(self) -> None:
        super().setUp()
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
        self.assert_image_matches_golden(base, HUE_TEST_IMAGE)

    def test_saturation_blend(self) -> None:
        """Test the custom saturation compositing function."""
        base = self._base_image.copy()
        CompositeMode.saturation_composite_blend(self._overlay_image, base)
        self.assert_image_matches_golden(base, SATURATION_TEST_IMAGE)

    def test_luminance_blend(self) -> None:
        """Test the custom luminance compositing function."""
        base = self._base_image.copy()
        CompositeMode.luminosity_composite_blend(self._overlay_image, base)
        self.assert_image_matches_golden(base, LUMINANCE_TEST_IMAGE)
