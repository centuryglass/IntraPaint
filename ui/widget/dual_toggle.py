"""
A fancier Qt toggle button implementation that allows selecting between two options.
"""
from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QFrame, QSizePolicy
from PyQt5.QtGui import QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QPoint, QSize, QRect, pyqtSignal

from ui.widget.label import Label

class DualToggle(QWidget):
    value_changed = pyqtSignal(str)

    def __init__(self, parent, option1, option2, config=None, orientation=Qt.Orientation.Horizontal):
        super().__init__(parent)
        self._bg_color = parent.palette().color(parent.backgroundRole())
        self._fg_color = parent.palette().color(parent.foregroundRole())
        self.option1 = option1
        self.option2 = option2
        self._orientation = None
        self._selected = None
        self.icon1 = None
        self.icon2 = None
        self.label1 = Label(option1, config, self, bg_color = self._bg_color, orientation = orientation)
        self.label1.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.label1.set_inverted(True)
        self.label2 = Label(option2, config, self, bg_color = self._bg_color, orientation = orientation)
        self.label2.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.set_orientation(orientation)

    def set_orientation(self, orientation):
        if self._orientation == orientation:
            return
        self._orientation = orientation
        self.label1.set_orientation(orientation)
        self.label2.set_orientation(orientation)
        if orientation == Qt.Orientation.Vertical:
            self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding))
        else:
            self.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))
        self.update()

    def sizeHint(self):
        if self._orientation == Qt.Orientation.Vertical:
            return QSize(self.label1.sizeHint().width(), self.label1.sizeHint().height() + self.label2.sizeHint().height() + 2)
        else:
            return QSize(self.label1.sizeHint().width() + self.label2.sizeHint().width() + 2, self.label1.sizeHint().height())

    def resizeEvent(self, event):
        if self._orientation == Qt.Orientation.Vertical:
            self.label1.setGeometry(0, 0, self.width(), (self.height() // 2) - 1)
            self.label2.setGeometry(0, (self.height() // 2) + 1, self.width(), (self.height() // 2) - 1)
        else:
            self.label1.setGeometry(0, 0, (self.width() // 2) - 1, self.height())
            self.label2.setGeometry((self.width() // 2) + 1, 0, (self.width() // 2) - 1, self.height())
    
    def toggle(self):
        if self._selected == self.option1:
            self.set_selected(self.option2)
        elif self._selected == self.option2:
            self.set_selected(self.option1)

    def selected(self):
        return self._selected

    def set_selected(self, selection):
        if selection == self._selected:
            return
        if selection != self.option1 and selection != self.option2 and selection is not None:
            raise Exception(f"invalid option {selection}")
        self._selected = selection
        for label in (self.label1, self.label2):
            label.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
            label.set_inverted(False)
        if selection is not None:
            label = self.label1 if selection == self.option1 else self.label2
            label.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
            label.set_inverted(True)
        self.value_changed.emit(selection)

    def setIcons(self, icon1, icon2):
        self.label1.setIcon(icon1)
        self.label2.setIcon(icon2)

    def setToolTips(self, text1, text2):
        self.label1.setToolTip(text1)
        self.label2.setToolTip(text1)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pt = event.pos()
            if self._orientation == Qt.Orientation.Vertical:
                self.set_selected(self.option1 if pt.y() < (self.height() // 2) else self.option2)
            else:
                self.set_selected(self.option1 if pt.x() < (self.width() // 2) else self.option2)

