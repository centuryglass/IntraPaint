"""Tests ImageViewer's context pin markers."""
import sys

from PySide6.QtCore import QPoint, QSize
from PySide6.QtWidgets import QApplication

from src.image.layers.image_stack import ImageStack
from src.ui.graphics_items.context_pin_item import marker_size_for_view, DEFAULT_MARKER_SIZE, MIN_MARKER_SIZE, \
    MAX_MARKER_SIZE, MARKER_REFERENCE_VIEW_SIDE
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

    def test_marker_size_follows_view_size(self) -> None:
        """Resizing the view rescales existing markers, within the size limits."""
        self.selection_layer.set_context_pins([QPoint(5, 5)])
        viewer = ImageViewer(None, self.image_stack, use_keybindings=False)
        viewer.resize(MARKER_REFERENCE_VIEW_SIDE * 2, MARKER_REFERENCE_VIEW_SIDE)
        viewer.resizeEvent(None)
        self.assertEqual(viewer.context_pin_marker_size, DEFAULT_MARKER_SIZE)
        viewer.resize(100, 100)
        viewer.resizeEvent(None)
        self.assertEqual(viewer.context_pin_marker_size, MIN_MARKER_SIZE)
        self.assertEqual(viewer._context_pin_items[0].marker_size, MIN_MARKER_SIZE)  # pylint: disable=protected-access


class MarkerSizeForViewTest(IntraPaintTestCase):
    """Tests marker_size_for_view's scaling and limits."""

    def test_scales_with_shorter_side(self) -> None:
        """The marker size scales with the view's shorter side."""
        self.assertEqual(marker_size_for_view(QSize(3000, MARKER_REFERENCE_VIEW_SIDE)), DEFAULT_MARKER_SIZE)
        self.assertEqual(marker_size_for_view(QSize(MARKER_REFERENCE_VIEW_SIDE * 3 // 2, 3000)),
                         DEFAULT_MARKER_SIZE * 3 // 2)

    def test_clamped(self) -> None:
        """Tiny and huge views stay within the marker size limits."""
        self.assertEqual(marker_size_for_view(QSize(10, 10)), MIN_MARKER_SIZE)
        self.assertEqual(marker_size_for_view(QSize(10000, 10000)), MAX_MARKER_SIZE)
