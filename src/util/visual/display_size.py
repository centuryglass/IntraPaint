"""Utility functions for display text management."""
import logging
from typing import Optional, cast

from PySide6.QtCore import QSize, QRect
from PySide6.QtWidgets import QApplication, QMainWindow

logger = logging.getLogger(__name__)


def get_screen_bounds(window: Optional[QMainWindow] = None, default_to_primary: bool = True,
                      alt_test_bounds: Optional[QRect] = None) -> QRect:
    """Returns the bounds of the display a window is in, or the bounds of the primary display if window is None."""
    app = cast(QApplication, QApplication.instance())
    assert app is not None, 'Application instance must be created to get screen size'
    screen = None
    if window is not None or alt_test_bounds is not None:
        if window is not None:
            window_bounds = window.geometry()
        else:
            assert alt_test_bounds is not None
            window_bounds = alt_test_bounds
        window_area = window_bounds.width() * window_bounds.height()
        best_screen_area = 0.0
        for test_screen in app.screens():
            screen_bounds = test_screen.geometry()
            intersect = screen_bounds.intersected(window_bounds)
            if not intersect.isEmpty():
                intersect_percent = (intersect.width() * intersect.height()) / window_area
                if intersect_percent > best_screen_area:
                    screen = test_screen
                    best_screen_area = intersect_percent
    if screen is None and default_to_primary:
        screen = app.primaryScreen()
    if screen is None:
        return QRect()
    return screen.availableGeometry()


def get_screen_size(window: Optional[QMainWindow] = None, default_to_primary: bool = True) -> QSize:
    """Returns the size of the display a window is in, or the size of the primary display if window is None."""
    return get_screen_bounds(window, default_to_primary).size()


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
