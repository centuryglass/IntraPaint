"""Tests InkStyle overrides that Qt calls with unusual arguments."""
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QPushButton, QStyle, QStyleOptionSlider, QWidgetItem

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

    def test_pixel_metric_ignores_non_widget(self) -> None:
        """A stale wrapper in the widget slot is never dereferenced: the metric is the one for no widget."""
        style = QApplication.style()
        self.assertIsInstance(style, InkStyle)
        item = _StaleItem(QPushButton())
        metric = QStyle.PixelMetric.PM_DefaultFrameWidth
        expected = style.pixelMetric(metric, None, None)
        with self.assertLogs('src.ui.ink_style', level='WARNING'):
            self.assertEqual(style.pixelMetric(metric, None, item), expected)

    def test_polish_skips_non_widget(self) -> None:
        """A stale wrapper of any other type, here a style option, is skipped instead of reaching the base style."""
        style = QApplication.style()
        self.assertIsInstance(style, InkStyle)
        for method in (style.polish, style.unpolish):
            with self.assertLogs('src.ui.ink_style', level='WARNING'):
                method(QStyleOptionSlider())

    def test_polish_accepts_widget_and_palette(self) -> None:
        """Widgets and palettes still reach the base style without a warning."""
        style = QApplication.style()
        self.assertIsInstance(style, InkStyle)
        button = QPushButton()
        with self.assertNoLogs('src.ui.ink_style', level='WARNING'):
            style.polish(button)
            style.unpolish(button)
            style.polish(QApplication.palette())
