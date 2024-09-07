"""Utility functions for display text management."""
import logging
from typing import Optional, cast

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QMainWindow

logger = logging.getLogger(__name__)


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
