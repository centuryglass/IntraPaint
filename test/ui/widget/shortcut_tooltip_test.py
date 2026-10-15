"""Tests that tooltips show their key binding and follow changes to it."""
import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QToolButton

from src.config.key_config import KeyConfig
from src.ui.widget.shortcut_tooltip import (set_shortcut_tooltip, set_step_shortcut_tooltip, shortcut_tooltip_text,
                                            rich_shortcut_tooltip_text)
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class ShortcutTooltipTest(IntraPaintTestCase):
    """Checks tooltip text for bound, unbound and rebound keys."""

    def test_text_appends_formatted_keys(self) -> None:
        """The binding follows the text in parentheses, formatted like the key hints."""
        self.assertEqual(shortcut_tooltip_text('Merge down', 'Ctrl+Shift+M'), 'Merge down (Ctrl+Shift+M)')

    def test_text_without_keys(self) -> None:
        """An empty binding leaves the text unchanged."""
        self.assertEqual(shortcut_tooltip_text('Merge down', ''), 'Merge down')

    def test_no_config_key(self) -> None:
        """A widget with no config key just gets the text."""
        button = QToolButton()
        set_shortcut_tooltip(button, 'Plain', None)
        self.assertEqual(button.toolTip(), 'Plain')
        set_shortcut_tooltip(button, 'Plain', None, rich_text=False)
        self.assertEqual(button.toolTip(), 'Plain')

    def test_tooltip_follows_binding(self) -> None:
        """Rebinding the key updates the tooltip, and clearing it removes the suffix."""
        key = KeyConfig.MERGE_LAYER_DOWN_SHORTCUT
        button = QToolButton()
        set_shortcut_tooltip(button, 'Merge down', key, rich_text=False)
        self.assertEqual(button.toolTip(), shortcut_tooltip_text('Merge down', KeyConfig().get(key)))
        KeyConfig().set(key, 'Ctrl+Alt+K')
        self.assertEqual(button.toolTip(), 'Merge down (Ctrl+Alt+K)')
        KeyConfig().set(key, '')
        self.assertEqual(button.toolTip(), 'Merge down')

    def test_step_keys_tooltip(self) -> None:
        """A stepped input shows a keycap for each bound step key, drops an unbound one, and follows rebinding."""
        decrease, increase = KeyConfig.PAN_LEFT, KeyConfig.PAN_RIGHT
        button = QToolButton()
        set_step_shortcut_tooltip(button, 'Size', decrease, increase)
        self.assertTrue(button.toolTip().startswith('<b>Size</b>'))
        both = button.toolTip().count('<img')
        self.assertGreaterEqual(both, 2)
        KeyConfig().set(increase, '')
        self.assertLess(button.toolTip().count('<img'), both)
        KeyConfig().set(decrease, '')
        self.assertEqual(button.toolTip(), 'Size')
        set_step_shortcut_tooltip(button, 'Plain', None, None)
        self.assertEqual(button.toolTip(), 'Plain')


class RichShortcutTooltipTest(IntraPaintTestCase):
    """Checks the keycap form of tooltips."""

    def test_one_keycap_per_key(self) -> None:
        """Each key of a chord gets its own image."""
        text = rich_shortcut_tooltip_text('Merge down', 'Ctrl+Shift+M')
        self.assertEqual(text.count('<img'), 3)
        self.assertTrue(text.startswith('<b>Merge down</b>'))

    def test_sequence_and_plus_key(self) -> None:
        """Chords of a sequence and a bound plus key are each drawn."""
        self.assertEqual(rich_shortcut_tooltip_text('T', 'A, B').count('<img'), 2)
        self.assertEqual(rich_shortcut_tooltip_text('T', 'Ctrl++').count('<img'), 2)

    def test_description(self) -> None:
        """The description follows the title, and the text is escaped."""
        text = rich_shortcut_tooltip_text('A & B', '', 'Does <it>.')
        self.assertIn('A &amp; B', text)
        self.assertIn('Does &lt;it&gt;.', text)
        self.assertLess(text.index('A &amp; B'), text.index('Does'))
        self.assertEqual(text.count('<img'), 0)

    def test_only_title(self) -> None:
        """With nothing to add, the tooltip is the title."""
        self.assertEqual(rich_shortcut_tooltip_text('Plain', ''), 'Plain')

    def test_follows_binding(self) -> None:
        """Rebinding changes the keycaps, and clearing the binding removes them."""
        key = KeyConfig.MERGE_LAYER_DOWN_SHORTCUT
        button = QToolButton()
        set_shortcut_tooltip(button, 'Merge down', key, description='Merge layers.')
        self.assertEqual(button.toolTip(), rich_shortcut_tooltip_text('Merge down', KeyConfig().get(key),
                                                                       'Merge layers.'))
        KeyConfig().set(key, 'Ctrl+Alt+K')
        self.assertEqual(button.toolTip().count('<img'), 3)
        KeyConfig().set(key, '')
        self.assertEqual(button.toolTip().count('<img'), 0)
        self.assertIn('Merge layers.', button.toolTip())

    def test_keycap_image_follows_theme(self) -> None:
        """Keycaps drawn under a different palette use a different image."""
        before = rich_shortcut_tooltip_text('T', 'K')
        palette = QApplication.palette()
        original = QPalette(palette)
        try:
            palette.setColor(QPalette.ColorRole.Button, QColor('#123456'))
            QApplication.setPalette(palette)
            self.assertNotEqual(rich_shortcut_tooltip_text('T', 'K'), before)
        finally:
            QApplication.setPalette(original)


class RichTooltipRenderTest(IntraPaintTestCase):
    """Compares a rendered rich tooltip with a golden image."""

    def test_tooltip_render(self) -> None:
        """A tooltip with a description and a three-key binding matches the golden image."""
        text = rich_shortcut_tooltip_text('Merge down', 'Ctrl+Shift+E', 'Combine this layer with the one below it.')
        label = QLabel(text)
        palette = label.palette()
        palette.setColor(QPalette.ColorRole.Window, palette.color(QPalette.ColorRole.ToolTipBase))
        palette.setColor(QPalette.ColorRole.WindowText, palette.color(QPalette.ColorRole.ToolTipText))
        label.setPalette(palette)
        label.setAutoFillBackground(True)
        label.setMargin(8)
        label.resize(label.sizeHint())
        self.assert_image_matches_golden(label.grab().toImage(), 'test/resources/tooltips/rich_tooltip.png')
