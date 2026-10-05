"""Tests ImageFilter.apply_filter with "selection only" on, using the invert filter."""
import sys
from unittest.mock import patch

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from src.image.filter.invert import InvertFilter
from src.image.layers.image_stack import ImageStack
from src.util.async_task import AsyncTask
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

IMAGE_SIZE = QSize(256, 256)
SELECTED_REGIONS = (QRect(10, 10, 20, 20), QRect(200, 200, 20, 20))
UNSELECTED_POINT = QPoint(100, 100)


class FilterSelectionOnlyTest(IntraPaintTestCase):
    """Applies a filter to selected areas of a single white layer."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(IMAGE_SIZE, IMAGE_SIZE, QSize(8, 8), QSize(1024, 1024))
        image = QImage(IMAGE_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.white)
        self.layer = self.image_stack.create_layer(None, image)
        self.image_stack.active_layer = self.layer
        self.filter = InvertFilter(self.image_stack)
        self.filter.selection_only = True
        self.filter.active_layer_only = True

    def _select(self, bounds: QRect) -> None:
        with self.image_stack.selection_layer.borrow_image() as mask_image:
            painter = QPainter(mask_image)
            painter.fillRect(bounds, Qt.GlobalColor.black)
            painter.end()

    def _apply_filter(self) -> None:
        """Runs apply_filter with its background task on the calling thread."""
        with patch.object(AsyncTask, 'start', AsyncTask.run):
            self.filter.apply_filter([])

    def test_filter_changes_every_selected_region(self) -> None:
        """Each region of a multi-region selection is filtered, and unselected pixels are left alone."""
        for region in SELECTED_REGIONS:
            self._select(region)
        self._apply_filter()
        image = self.layer.image
        for region in SELECTED_REGIONS:
            for point in (region.topLeft(), region.bottomRight()):
                self.assertEqual(image.pixelColor(point), QColor(Qt.GlobalColor.black), f'{point} not filtered')
        self.assertEqual(image.pixelColor(UNSELECTED_POINT), QColor(Qt.GlobalColor.white))
