# Adapted from https://stackoverflow.com/a/52617714, but without animations, and a few other minor adjustments.
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QStackedWidget, QWidget, QScrollArea, QToolButton, QHBoxLayout, QVBoxLayout
from PyQt5.QtCore import QSize, pyqtSignal

from ui.widget.bordered_widget import BorderedWidget
from ui.widget.vertical_label import VerticalLabel


class CollapsibleBox(BorderedWidget):

    def __init__(self,
            title="",
            parent=None,
            startClosed=False,
            maxSizeFraction=1,
            maxSizePx=None,
            scrolling=True,
            orientation=Qt.Orientation.Vertical):
        super(CollapsibleBox, self).__init__(parent)
        self._widgetsize_max = self.maximumWidth()
        self._isVertical = (orientation == Qt.Orientation.Vertical)
        layout = QVBoxLayout(self) if self._isVertical else QHBoxLayout(self)
        self._outerLayout = layout
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)


        self.toggle_button = QToolButton(
            text=title, checkable=True, checked=not startClosed
        )
        self.toggle_button.setStyleSheet("QToolButton { border: none; }")
        if self._isVertical:
            self.toggle_button.setToolButtonStyle(
                QtCore.Qt.ToolButtonTextBesideIcon
            )
            layout.addWidget(self.toggle_button)
        else:
            self.toggleLabel = VerticalLabel(title)
            self.toggleLabel.setAlignment(Qt.AlignTop)
            self.toggle_button.setToolButtonStyle(
                QtCore.Qt.ToolButtonIconOnly
            )
            buttonBar = QWidget()
            buttonBarLayout = QVBoxLayout()
            buttonBarLayout.addWidget(self.toggle_button, alignment=Qt.AlignTop)
            buttonBarLayout.addWidget(self.toggleLabel, alignment=Qt.AlignTop)
            buttonBar.setLayout(buttonBarLayout)
            layout.addWidget(buttonBar)
        self.toggle_button.setArrowType(QtCore.Qt.DownArrow if self._isVertical else QtCore.Qt.RightArrow)
        self.toggle_button.toggled.connect(lambda: self.on_pressed())

        if scrolling:
            self.scroll_area = QScrollArea()
            self.content = QWidget(self.scroll_area)
            self.scroll_area.setWidget(self.content)
            self.scroll_area.setWidgetResizable(True)
        else:
            self.scroll_area = QWidget()
            self.content = self.scroll_area
        
        layout.addWidget(self.scroll_area, stretch=255)
        self._startClosed = startClosed
        self._maxSizeFraction = maxSizeFraction
        self._maxSizePx = maxSizePx

    def toggled(self):
        return self.toggle_button.toggled

    def showButtonBar(self, showBar):
        self._outerLayout.setStretch(1, 1 if showBar else 0)
        buttonBar = self._outerLayout.itemAt(0).widget()
        buttonBar.setEnabled(showBar)
        if self._isVertical:
            buttonBar.setMaximumHeight(self.height() if showBar else 0)
        else:
            buttonBar.setMaximumWidth(self.width() if showBar else 0)
            buttonBar.setMinimumWidth(self.toggleLabel.imageSize().width() if showBar else 0)
        if not showBar:
            self.setExpanded(True)

    def _refreshScrollSize(self, contentSize):
        if self.scroll_area == self.content:
            return
        window = self
        while window.parentWidget():
            window = window.parentWidget()
        maxSize = int((window.height() if self._isVertical else window.width()) * self._maxSizeFraction)
        if self._maxSizePx is not None:
            maxSize = min(maxSize, self._maxSizePx)
        if self._isVertical:
            self.scroll_area.setMinimumHeight(min(maxSize, contentSize))
            self.scroll_area.setMaximumHeight(min(maxSize, contentSize))
        else:
            self.scroll_area.setMinimumWidth(min(maxSize, contentSize))
            self.scroll_area.setMaximumWidth(self._widgetsize_max)  #min(maxSize, contentSize + 5))

    def refreshLayout(self):
        if self.content.layout() is not None:
            if self._isVertical:
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
                self._refreshScrollSize(height)
            else:
                width = 0
                layout = self.content.layout()
                if self.toggle_button.isChecked():
                    for i in range(layout.count()):
                        item = layout.itemAt(i)
                        if item.widget():
                            width = max(width, item.widget().width())
                        elif item.layout():
                            width = max(width, item.layout().totalSizeHint().width())
                window = self
                while window.parentWidget():
                    window = window.parentWidget()
                self.content.setMinimumWidth(window.width())
                self.content.setMaximumWidth(self._widgetsize_max)
                self._refreshScrollSize(width)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        checked = self.toggle_button.isChecked()
        if self._isVertical:
            height = self.content.layout().totalSizeHint().height() if checked else 0
            if height != self.content.minimumHeight() or height != self.content.maximumHeight():
                self.content.setMinimumHeight(height)
                self.content.setMaximumHeight(height)
                self._refreshScrollSize(height)
        #else:
        #    self.refreshLayout()
        #    width = self.content.layout().totalSizeHint().width() if checked else 0
        #    if width != self.content.minimumWidth() or width != self.content.maximumWidth():
        #        self.content.setMinimumWidth(width)
        #        self.content.setMaximumWidth(width)
        #        self._refreshScrollSize(width)

    def on_pressed(self):
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(
            QtCore.Qt.DownArrow if (checked == self._isVertical) else QtCore.Qt.RightArrow)
        if self._isVertical:
            height = self.content.layout().totalSizeHint().height() if checked else 0
            self.content.setMinimumHeight(height)
            self.content.setMaximumHeight(height)
            self._refreshScrollSize(height)
        else:
            width = self.content.layout().totalSizeHint().width() if checked else 0
            self.content.setMinimumWidth(width)
            self.content.setMaximumWidth(width if width==0 else self._widgetsize_max)
            self._refreshScrollSize(width)

    def isExpanded(self):
        return self.toggle_button.isChecked()

    def setExpanded(self, isExpanded):
        if isExpanded != self.toggle_button.isChecked():
            self.toggle_button.setChecked(isExpanded)

    def setContentLayout(self, layout):
        self.content.setLayout(layout)
        if self._startClosed:
            self.on_pressed()
