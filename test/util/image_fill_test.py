"""Test image fill functions."""
import sys

from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication

from src.util.visual.image_fill import flood_fill
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

TEST_ARGB_IMAGE_PATH = 'test/resources/test_images/png-with-transparency.png'
TEST_ARGB_FLOODFILL_PATH = 'test/resources/test_images/png-with-transparency-floodfill.png'


class TestImageUtils(IntraPaintTestCase):
    """Test image utility functions."""

    def setUp(self) -> None:
        super().setUp()
        self.qimage_argb = QImage(TEST_ARGB_IMAGE_PATH).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)

    def test_flood_fill(self) -> None:
        """Test that the flood fill algorithm handles image updates and LAB thresholds correctly."""
        fill_points: list[QPoint] = [
            QPoint(375, 441),
            QPoint(493, 363),
            QPoint(691, 331)
        ]

        fill_colors: list[QColor] = [
            QColor(254, 74, 100, 225),
            QColor(26, 244, 253, 245),
            QColor(18, 0, 255, 255)
        ]

        thresholds: list[float] = [
            50.0,
            15.0,
            5.0
        ]

        for i in range(3):
            mask = flood_fill(self.qimage_argb, fill_points[i], fill_colors[i], thresholds[i], False)
            assert mask is not None
            flood_fill(self.qimage_argb, fill_points[i], fill_colors[i], thresholds[i], True)
        self.assert_image_matches_golden(self.qimage_argb, TEST_ARGB_FLOODFILL_PATH)
