"""Tests ColorButton."""
from unittest.mock import patch

from PySide6.QtGui import QColor

from src.config.cache import Cache
from src.ui.widget.color_button import ColorButton
from test.base_test_case import IntraPaintTestCase

DIALOG_PATH = 'src.ui.widget.color_button.ColorDialog.show_color_dialog'


class ColorButtonTest(IntraPaintTestCase):
    """Tests ColorButton."""

    def test_unbound_button_leaves_config_alone(self) -> None:
        """A button with no config key doesn't write the brush color when its color changes."""
        brush_color = Cache().get(Cache.LAST_BRUSH_COLOR)
        button = ColorButton(config_key=None)
        button.color = QColor('#ff00ff00')
        self.assertEqual(button.color, QColor('#ff00ff00'))
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), brush_color)

    def test_unbound_select_color_updates_color_and_icon(self) -> None:
        """Choosing a color in an unbound button's dialog changes its color and icon, but not the brush color."""
        brush_color = Cache().get(Cache.LAST_BRUSH_COLOR)
        button = ColorButton(config_key=None)
        icon_before = button.icon().pixmap(button.iconSize()).toImage()
        selection = QColor('#ff0000ff')
        with patch(DIALOG_PATH, return_value=selection):
            button.select_color()
        self.assertEqual(button.color, selection)
        self.assertEqual(button.icon().pixmap(button.iconSize()).toImage().pixelColor(2, 2), selection)
        self.assertNotEqual(icon_before.pixelColor(2, 2), selection)
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), brush_color)

    def test_bound_select_color_writes_config(self) -> None:
        """Choosing a color in a bound button's dialog writes the config value."""
        button = ColorButton()
        with patch(DIALOG_PATH, return_value=QColor('#ff0000ff')):
            button.select_color()
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), '#ff0000ff')
        self.assertEqual(button.color, QColor('#ff0000ff'))
