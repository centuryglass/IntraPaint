"""Tests ImageViewer's context pin markers."""
import sys

from PySide6.QtCore import QPoint, QSize
from PySide6.QtWidgets import QApplication

from src.image.layers.image_stack import ImageStack
from src.ui.image_viewer import ImageViewer
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class ImageViewerContextPinTest(IntraPaintTestCase):
    """Tests that viewers draw one marker per context pin."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(QSize(64, 64), QSize(64, 64), QSize(8, 8), QSize(64, 64))
        self.selection_layer = self.image_stack.selection_layer

    @staticmethod
    def _marker_count(viewer: ImageViewer) -> int:
        return len(viewer._context_pin_items)  # pylint: disable=protected-access

    def test_viewer_created_after_pins_draws_them(self) -> None:
        """A viewer created while pins exist, like a navigation panel opened later, draws markers for them."""
        self.selection_layer.set_context_pins([QPoint(5, 5), QPoint(20, 40)])
        viewer = ImageViewer(None, self.image_stack, use_keybindings=False)
        self.assertEqual(self._marker_count(viewer), 2)

    def test_markers_follow_pin_changes(self) -> None:
        """Markers are added and removed as pins change."""
        viewer = ImageViewer(None, self.image_stack, use_keybindings=False)
        self.assertEqual(self._marker_count(viewer), 0)
        self.selection_layer.add_context_pin(QPoint(5, 5))
        self.assertEqual(self._marker_count(viewer), 1)
        self.selection_layer.clear_context_pins()
        self.assertEqual(self._marker_count(viewer), 0)
