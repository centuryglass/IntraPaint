# Adapted from https://stackoverflow.com/a/52617714, but without animations, and a few other minor adjustments.
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QStackedWidget, QWidget, QScrollArea
from PyQt5.QtCore import pyqtSignal

from ui.widget.bordered_widget import BorderedWidget


class CollapsibleBox(BorderedWidget):

    def __init__(self, title="", parent=None):
        super(CollapsibleBox, self).__init__(parent)

        self.toggle_button = QtWidgets.QToolButton(
            text=title, checkable=True, checked=True
        )
        self.toggle_button.setStyleSheet("QToolButton { border: none; }")
        self.toggle_button.setToolButtonStyle(
            QtCore.Qt.ToolButtonTextBesideIcon
        )
        self.toggle_button.setArrowType(QtCore.Qt.DownArrow)
        self.toggle_button.toggled.connect(lambda: self.on_pressed())


        self.content_area = QScrollArea()
        
        lay = QtWidgets.QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        checked = self.toggle_button.isChecked()
        height = self.content_area.layout().totalSizeHint().height() if checked else 0
        if height != self.content_area.minimumHeight() or height != self.content_area.maximumHeight():
            self.content_area.setMinimumHeight(height)
            self.content_area.setMaximumHeight(height)

    def on_pressed(self):
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(
            QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow)
        height = self.content_area.layout().totalSizeHint().height() if checked else 0
        self.content_area.setMinimumHeight(height)
        self.content_area.setMaximumHeight(height)

    def setContentLayout(self, layout):
        self.content_area.setLayout(layout)
