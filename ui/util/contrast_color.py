from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

def contrastColor(widget): 
    return widget.palette().color(widget.foregroundRole())
