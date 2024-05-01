from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QSize

def screenSize(window=None):
    display = None
    if window is not None:
        display = QApplication.instance().screenAt(window.pos())
    if display is None:
        display = QApplication.primaryScreen()
    if display is None:
        return QSize(0, 0)
    return display.size()

