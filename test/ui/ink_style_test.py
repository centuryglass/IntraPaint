"""Tests InkStyle overrides that Qt calls with unusual arguments."""
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QPushButton, QStyle, QWidgetItem

from src.ui.ink_style import InkStyle
from test.base_test_case import IntraPaintTestCase


class _StaleItem(QWidgetItem):
    """Stands in for the stale wrapper PySide returns when a freed layout item's address is reused by a widget."""

    def widget(self):  # pylint: disable=invalid-name
        raise AssertionError('a stale wrapper was dereferenced')


class InkStyleTest(IntraPaintTestCase):
    """Covers the InkStyle overrides that guard against stale widget wrappers."""

    def test_style_hint_ignores_non_widget(self) -> None:
        """A stale wrapper in the widget slot is never dereferenced: the hint is the one for no widget."""
        style = QApplication.style()
        self.assertIsInstance(style, InkStyle)
        button = QPushButton()
        item = _StaleItem(button)
        hint = QStyle.StyleHint.SH_ToolTip_WakeUpDelay
        expected = style.styleHint(hint, None, None, None)
        with self.assertLogs('src.ui.ink_style', level='WARNING'):
            self.assertEqual(style.styleHint(hint, None, item, None), expected)

    def test_size_from_contents_ignores_non_widget(self) -> None:
        """A stale wrapper in the widget slot is never dereferenced: the size is the one for no widget."""
        style = QApplication.style()
        self.assertIsInstance(style, InkStyle)
        button = QPushButton()
        item = _StaleItem(button)
        content_type = QStyle.ContentsType.CT_ScrollBar
        size = QSize(11, 22)
        expected = style.sizeFromContents(content_type, None, size, None)
        with self.assertLogs('src.ui.ink_style', level='WARNING'):
            self.assertEqual(style.sizeFromContents(content_type, None, size, item), expected)
