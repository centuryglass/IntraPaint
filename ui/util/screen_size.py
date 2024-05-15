"""
Utility function for getting the active screen dimensions.
"""
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QSize

def screen_size(window=None):
    """Returns the size of the display a window is in, or the size of the primary display if window is None."""
    display = None
    if window is not None:
        display = QApplication.instance().screenAt(window.pos())
    if display is None:
        display = QApplication.primaryScreen()
    if display is None:
        return QSize(0, 0)
    return display.size()
