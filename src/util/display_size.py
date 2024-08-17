"""Utility functions for display text management."""
import logging
from typing import Optional, cast

from PySide6.QtCore import QSize
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication, QMainWindow

MAX_FONT_PT = 240
logger = logging.getLogger(__name__)


def _find_line_size(font: QFont, text: str) -> QSize:
    metric = QFontMetrics(font)
    line_size = metric.boundingRect(text).size()
    max_height = metric.ascent() + metric.descent()
    line_size.setHeight(max(line_size.height(), max_height) + 2)
    line_size.setWidth(line_size.width() + 2)
    return line_size


def find_text_size(text: str, font: Optional[QFont] = None, multiline=True) -> QSize:
    """Returns the size in pixels required to render the text with the given font."""
    if font is None:  # Use application default
        app = cast(QApplication, QApplication.instance())
        assert app is not None
        font = app.font()
    if not multiline:
        return _find_line_size(font, text)
    lines = text.split('\n')
    size = QSize()
    for line in lines:
        if len(line) == 0:
            line = ' '
        line_size = _find_line_size(font, line)
        size.setWidth(max(size.width(), line_size.width()))
        size.setHeight(size.height() + line_size.height())
    return size


def max_font_size(text: str, font: QFont, bounds: QSize) -> int:
    """Returns the largest font size that will fit within the given bounds."""
    if len(text) == 0:
        return MAX_FONT_PT
    max_pt = 0
    test_size = QSize(0, 0)
    test_font = QFont(font)
    while max_pt < MAX_FONT_PT and test_size.width() < bounds.width() and test_size.height() < bounds.height():
        max_pt += 1
        test_font.setPointSize(max_pt)
        test_size = find_text_size(text, test_font)
    max_pt -= 1
    logger.debug(f'"{text}" fits in {bounds} at size {max_pt}')
    return max_pt


def get_screen_size(window: Optional[QMainWindow] = None, default_to_primary: bool = True) -> QSize:
    """Returns the size of the display a window is in, or the size of the primary display if window is None."""
    display = None
    app = cast(QApplication, QApplication.instance())
    assert app is not None, 'Application instance must be created to get screen size'
    if window is not None:
        display = app.screenAt(window.pos())
    if display is None and default_to_primary:
        display = app.primaryScreen()
    if display is None:
        return QSize(0, 0)
    return display.size()


def get_window_size() -> QSize:
    """Returns the size of the largest open window."""
    app = cast(QApplication, QApplication.instance())
    assert app is not None, 'Application instance must be created to get window size'
    max_area = 0
    largest = None
    for window in app.topLevelWidgets():
        area = window.width() * window.height()
        if area > max_area:
            max_area = area
            largest = window
    if largest is None:
        return QSize()
    return largest.size()
