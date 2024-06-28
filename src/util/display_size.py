"""Utility functions for display text management."""
import logging
import sys
from typing import Optional

from PyQt5.QtCore import QSize
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtWidgets import QApplication, QMainWindow

MAX_FONT_PT = 240
logger = logging.getLogger(__name__)


def find_text_size(text: str, font: Optional[QFont] = None) -> QSize:
    """Returns the size in pixels required to render the text with the given font."""
    if font is None:  # Use application default
        app = QApplication.instance()
        assert app is not None
        font = app.font()
    return QFontMetrics(font).boundingRect(text).size()


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


def get_screen_size(window: Optional[QMainWindow] = None) -> QSize:
    """Returns the size of the display a window is in, or the size of the primary display if window is None."""
    display = None
    app = QApplication.instance()
    assert app is not None, 'Application instance must be created to get screen size'
    if window is not None:
        display = app.screenAt(window.pos())
    if display is None:
        display = app.primaryScreen()
    if display is None:
        return QSize(0, 0)
    return display.size()


def get_window_size() -> QSize:
    """Returns the size of the largest open window."""
    app = QApplication.instance()
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