# Adapted from https://stackoverflow.com/a/52617714
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QStackedWidget, QWidget, QScrollArea
from inpainting.ui.layout_utils import BorderedWidget


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
        self.content_area.setMinimumHeight(self.content_area.layout().totalSizeHint().height() if checked else 0)
        self.content_area.setMaximumHeight(self.content_area.layout().totalSizeHint().height() if checked else 0)

    def on_pressed(self):
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(
            QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow)
        self.content_area.setMinimumHeight(self.content_area.layout().totalSizeHint().height() if checked else 0)
        self.content_area.setMaximumHeight(self.content_area.layout().totalSizeHint().height() if checked else 0)


    def setContentLayout(self, layout):
        self.content_area.setLayout(layout)
