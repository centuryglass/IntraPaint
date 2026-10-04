"""Tests SelectionPanel's clear context pins button."""
import sys
from unittest.mock import MagicMock

from PySide6.QtCore import QPoint, QSize
from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.image.layers.image_stack import ImageStack
from src.ui.panel.tool_control_panels.selection_panel import SelectionPanel
from src.util.shared_constants import EDIT_MODE_INPAINT, EDIT_MODE_IMG2IMG
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class SelectionPanelTest(IntraPaintTestCase):
    """Tests when the clear context pins button shows and what it does."""

    def setUp(self) -> None:
        super().setUp()
        cache = Cache()
        cache.restore_default_options(Cache.EDIT_MODE)
        cache.set(Cache.INPAINT_OPTIONS_AVAILABLE, True)
        cache.set(Cache.EDIT_MODE, EDIT_MODE_INPAINT)
        self.image_stack = ImageStack(QSize(256, 256), QSize(128, 128), QSize(8, 8), QSize(1024, 1024))
        self.selection_layer = self.image_stack.selection_layer
        self.panel = SelectionPanel(self.selection_layer, MagicMock())
        self.button = self.panel._clear_pins_button  # pylint: disable=protected-access

    def test_shown_only_while_inpainting(self) -> None:
        """The button shows in inpainting mode, and hides in other modes or without inpainting support."""
        cache = Cache()
        self.assertFalse(self.button.isHidden())
        cache.set(Cache.EDIT_MODE, EDIT_MODE_IMG2IMG)
        self.assertTrue(self.button.isHidden())
        cache.set(Cache.EDIT_MODE, EDIT_MODE_INPAINT)
        self.assertFalse(self.button.isHidden())
        cache.set(Cache.INPAINT_OPTIONS_AVAILABLE, False)
        self.assertTrue(self.button.isHidden())

    def test_enabled_only_with_pins(self) -> None:
        """The button is disabled until there's a pin to clear."""
        self.assertFalse(self.button.isEnabled())
        self.selection_layer.add_context_pin(QPoint(10, 10))
        self.assertTrue(self.button.isEnabled())

    def test_click_clears_pins(self) -> None:
        """Clicking the button removes every pin."""
        self.selection_layer.set_context_pins([QPoint(10, 10), QPoint(20, 20)])
        self.button.click()
        self.assertEqual(self.selection_layer.context_pins, [])
        self.assertFalse(self.button.isEnabled())
