"""Tests InkStyle overrides that Qt calls with unusual arguments."""
from PySide6.QtWidgets import QApplication, QPushButton, QStyle, QWidgetItem

from src.ui.ink_style import InkStyle
from test.base_test_case import IntraPaintTestCase


class InkStyleTest(IntraPaintTestCase):
    """Covers InkStyle.styleHint."""

    def test_style_hint_accepts_widget_item(self) -> None:
        """Qt's layout code can pass a QWidgetItem as the widget argument."""
        style = QApplication.style()
        self.assertIsInstance(style, InkStyle)
        button = QPushButton()
        hint = QStyle.StyleHint.SH_ToolTip_WakeUpDelay
        expected = style.styleHint(hint, None, button, None)
        self.assertEqual(style.styleHint(hint, None, QWidgetItem(button), None), expected)
