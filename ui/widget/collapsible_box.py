# Adapted from https://stackoverflow.com/a/52617714, but without animations, and a few other minor adjustments.
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QStackedWidget, QWidget, QScrollArea
from PyQt5.QtCore import QSize, pyqtSignal

from ui.widget.bordered_widget import BorderedWidget


class CollapsibleBox(BorderedWidget):

    def __init__(self, title="", parent=None, startClosed=False, maxHeightFraction=1, maxHeightPx=None):
        super(CollapsibleBox, self).__init__(parent)

        self.toggle_button = QtWidgets.QToolButton(
            text=title, checkable=True, checked=not startClosed
        )
        self.toggle_button.setStyleSheet("QToolButton { border: none; }")
        self.toggle_button.setToolButtonStyle(
            QtCore.Qt.ToolButtonTextBesideIcon
        )
        self.toggle_button.setArrowType(QtCore.Qt.DownArrow)
        self.toggle_button.toggled.connect(lambda: self.on_pressed())

        self.scroll_area = QScrollArea()
        self.content = QWidget(self.scroll_area)
        self.scroll_area.setWidget(self.content)
        self.scroll_area.setWidgetResizable(True)
        
        lay = QtWidgets.QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.scroll_area)
        self._startClosed = startClosed
        self._maxHeightFraction = maxHeightFraction
        self._maxHeightPx = maxHeightPx

    def _refreshScrollHeight(self, contentHeight):
        window = self
        while window.parentWidget():
            window = window.parentWidget()
        maxHeight = int(window.height() * self._maxHeightFraction)
        if self._maxHeightPx is not None:
            maxHeight = min(maxHeight, self._maxHeightPx)
        self.scroll_area.setMinimumHeight(min(maxHeight, contentHeight + 5))
        self.scroll_area.setMaximumHeight(min(maxHeight, contentHeight + 5))

    def refreshLayout(self):
        if self.content.layout() is not None:
            height = 0
            layout = self.content.layout()
            if self.toggle_button.isChecked():
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if item.widget():
                        height += item.widget().height()
                    elif item.layout():
                        height += item.layout().totalSizeHint().height()
            self.content.setMinimumHeight(height)
            self.content.setMaximumHeight(height)
            self._refreshScrollHeight(height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        checked = self.toggle_button.isChecked()
        height = self.content.layout().totalSizeHint().height() if checked else 0
        if height != self.content.minimumHeight() or height != self.content.maximumHeight():
            self.content.setMinimumHeight(height)
            self.content.setMaximumHeight(height)
            self._refreshScrollHeight(height)

    def on_pressed(self):
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(
            QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow)
        height = self.content.layout().totalSizeHint().height() if checked else 0
        self.content.setMinimumHeight(height)
        self.content.setMaximumHeight(height)
        self._refreshScrollHeight(height)

    def setContentLayout(self, layout):
        self.content.setLayout(layout)
        if self._startClosed:
            self.on_pressed()
