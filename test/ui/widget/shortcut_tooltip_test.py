"""Tests that tooltips show their key binding and follow changes to it."""
import sys

from PySide6.QtWidgets import QApplication, QToolButton

from src.config.key_config import KeyConfig
from src.ui.widget.shortcut_tooltip import set_shortcut_tooltip, shortcut_tooltip_text
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class ShortcutTooltipTest(IntraPaintTestCase):
    """Checks tooltip text for bound, unbound and rebound keys."""

    def test_text_appends_formatted_keys(self) -> None:
        """The binding follows the text in parentheses, formatted like the key hints."""
        self.assertEqual(shortcut_tooltip_text('Merge down', 'Ctrl+Shift+M'), 'Merge down (⌃⇧M)')

    def test_text_without_keys(self) -> None:
        """An empty binding leaves the text unchanged."""
        self.assertEqual(shortcut_tooltip_text('Merge down', ''), 'Merge down')

    def test_no_config_key(self) -> None:
        """A widget with no config key just gets the text."""
        button = QToolButton()
        set_shortcut_tooltip(button, 'Plain', None)
        self.assertEqual(button.toolTip(), 'Plain')

    def test_tooltip_follows_binding(self) -> None:
        """Rebinding the key updates the tooltip, and clearing it removes the suffix."""
        key = KeyConfig.MERGE_LAYER_DOWN_SHORTCUT
        button = QToolButton()
        set_shortcut_tooltip(button, 'Merge down', key)
        self.assertEqual(button.toolTip(), shortcut_tooltip_text('Merge down', KeyConfig().get(key)))
        KeyConfig().set(key, 'Ctrl+Alt+K')
        self.assertEqual(button.toolTip(), 'Merge down (⌃⎇K)')
        KeyConfig().set(key, '')
        self.assertEqual(button.toolTip(), 'Merge down')
