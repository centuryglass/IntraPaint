from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtCore import Qt, QPoint, QRect, QSize, QMargins

def getEqualMargins(size):
    """Returns a QMargins object that is equally spaced on all sides."""
    return QMargins(size, size, size, size)
