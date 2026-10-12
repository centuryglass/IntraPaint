"""Tests that GeneratedImageSelector carries manual pan and zoom between options only while it still applies."""
import sys

from PySide6.QtCore import QPointF, QSize
from PySide6.QtWidgets import QApplication

from src.image.layers.image_stack import ImageStack
from src.ui.generated_image_selector import GeneratedImageSelector
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

# pylint: disable=protected-access


class GeneratedImageSelectorTest(IntraPaintTestCase):
    """Tests view carry-over when stepping between options."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(QSize(64, 64), QSize(64, 64), QSize(8, 8), QSize(64, 64))
        self.selector = GeneratedImageSelector(self.image_stack, lambda: None)
        self.selector.resize(400, 300)
        self.selector._zoom_to_option(0, True)

    def _manual_zoom(self, scale_ratio: float, offset: QPointF) -> None:
        """Applies a manual zoom and pan the way the view's own input handling does."""
        view = self.selector._view
        view.offset = view.offset + offset
        view.scale_without_fixed_scene_point(view.scene_scale * scale_ratio)

    def _scale_ratio(self) -> float:
        return self.selector._view.scene_scale / self.selector._base_option_scale

    def test_step_keeps_zoom_ratio_and_pan(self) -> None:
        """Stepping to the next option keeps the manual zoom ratio and pan."""
        self._manual_zoom(2.0, QPointF(3.0, -2.0))
        self.selector._zoom_to_option(1, True)
        self.assertAlmostEqual(self._scale_ratio(), 2.0, places=3)
        self.assertEqual(self.selector._view.offset - self.selector._base_option_offset, QPointF(3.0, -2.0))

    def test_zoom_ratio_survives_base_scale_change(self) -> None:
        """A change in the fitted scale keeps the chosen zoom ratio, not the scale difference."""
        self._manual_zoom(2.0, QPointF(0.0, 0.0))
        self.selector.resize(800, 600)
        self.selector._zoom_to_option(1, True)
        self.assertAlmostEqual(self._scale_ratio(), 2.0, places=3)

    def test_zoom_to_changes_drops_manual_view(self) -> None:
        """Toggling 'zoom to changes' returns to the fitted view."""
        self._manual_zoom(2.0, QPointF(3.0, -2.0))
        self.selector.zoom_to_changes(not self.selector._zoom_to_changes)
        self.assertAlmostEqual(self._scale_ratio(), 1.0, places=3)
        self.assertEqual(self.selector._view.offset, self.selector._base_option_offset)

    def test_reset_drops_manual_view(self) -> None:
        """A new batch starts without the old manual view."""
        self._manual_zoom(2.0, QPointF(3.0, -2.0))
        self.selector.reset()
        self.selector._zoom_to_option(0, True)
        self.assertAlmostEqual(self._scale_ratio(), 1.0, places=3)
        self.assertEqual(self.selector._view.offset, self.selector._base_option_offset)
