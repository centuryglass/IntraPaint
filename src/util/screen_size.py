"""
Utility function for getting the active screen dimensions.
"""
import sys
from typing import Optional
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QSize


def get_screen_size(window: Optional[QMainWindow] = None) -> QSize:
    """Returns the size of the display a window is in, or the size of the primary display if window is None."""
    args = sys.argv
    if '--window_size' in args:
        # When using a fixed window size, treat that as the screen size.
        # Would be better to connect this to the arg parser, but it's just for debugging anyway.
        idx = args.index('--window_size')
        width, height = args[idx + 1].split("x")
        return QSize(int(width), int(height))
    display = None
    app = QApplication.instance()
    assert app is not None
    if window is not None:
        display = app.screenAt(window.pos())
    if display is None:
        display = app.primaryScreen()
    if display is None:
        return QSize(0, 0)
    return display.size()
