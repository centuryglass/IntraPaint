# Adapted from https://stackoverflow.com/a/52617714, but without animations, and a few other minor adjustments.
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QStackedWidget, QWidget, QScrollArea, QToolButton, QHBoxLayout, QVBoxLayout, QSizePolicy
from PyQt5.QtCore import QSize, pyqtSignal

from ui.widget.bordered_widget import BorderedWidget
from ui.widget.label import Label


class CollapsibleBox(BorderedWidget):

    def __init__(self,
            title="",
            parent=None,
            startClosed=False,
            scrolling=True,
            orientation=Qt.Orientation.Vertical):
        super(CollapsibleBox, self).__init__(parent)
        self._widgetsize_max = self.maximumWidth()
        self._isVertical = (orientation == Qt.Orientation.Vertical)
        self._expandedSizePolicy = QSizePolicy.Preferred
        layout = QVBoxLayout(self) if self._isVertical else QHBoxLayout(self)
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
            layout.addWidget(self.toggle_button, stretch=1)
            self.toggle_button.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding))
        else:
            self.toggleLabel = Label(title)
            self.toggleLabel.setAlignment(Qt.AlignTop)
            self.toggle_button.setToolButtonStyle(
                QtCore.Qt.ToolButtonIconOnly
            )
            buttonBar = QWidget()
            buttonBarLayout = QVBoxLayout()
            buttonBarLayout.addWidget(self.toggle_button, alignment=Qt.AlignTop)
            buttonBarLayout.addWidget(self.toggleLabel, alignment=Qt.AlignTop)
            buttonBarLayout.addStretch(255)
            buttonBarLayout.setContentsMargins(0,0,0,0)
            buttonBar.setLayout(buttonBarLayout)
            buttonBar.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed))
            minWidth = self.toggleLabel.imageSize().width() + 2
            for widget in [buttonBar, self.toggleLabel, self.toggle_button]:
                widget.setMinimumWidth(minWidth)
            layout.addWidget(buttonBar, stretch=1)
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
        self.scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        if self._isVertical:
            self.setSizePolicy(QSizePolicy.Expanding, self._expandedSizePolicy)
        else:
            self.setSizePolicy(self._expandedSizePolicy, QSizePolicy.Expanding)
        
        layout.addWidget(self.scroll_area, stretch=255)
        self._startClosed = startClosed

    def setExpandedSizePolicy(self, policy):
        if policy == self._expandedSizePolicy:
            return
        self._expandedSizePolicy = policy
        if self.isExpanded():
            if self._isVertical:
                self.setSizePolicy(QSizePolicy.Expanding, self._expandedSizePolicy)
            else:
                self.setSizePolicy(self._expandedSizePolicy, QSizePolicy.Expanding)

    def toggled(self):
        return self.toggle_button.toggled

    def showButtonBar(self, showBar):
        self.layout().setStretch(0, 1 if showBar else 0)
        buttonBar = self.layout().itemAt(0).widget()
        buttonBar.setEnabled(showBar)
        buttonBar.setVisible(showBar)
        if self._isVertical:
            buttonBar.setMaximumHeight(self.height() if showBar else 0)
        else:
            buttonBar.setMaximumWidth(self.width() if showBar else 0)
            minWidth = (self.toggleLabel.imageSize().width() + 2) if showBar else 0
            for widget in [buttonBar, self.toggleLabel, self.toggle_button]:
                widget.setMinimumWidth(minWidth)
        if not showBar:
            self.setExpanded(True)

    def sizeHint(self):
        size = super().sizeHint()
        if not self.toggle_button.isChecked():
            if self._isVertical:
                size.setWidth(self.toggle_button.sizeHint().width())
            else:
                size.setHeight(self.toggle_button.sizeHint().height())
        return size

    def on_pressed(self):
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(
            QtCore.Qt.DownArrow if (checked == self._isVertical) else QtCore.Qt.RightArrow)
        if checked:
            self.layout().addWidget(self.scroll_area, stretch=255)
            self.scroll_area.setVisible(True)
            if self._isVertical:
                self.setSizePolicy(QSizePolicy.Expanding, self._expandedSizePolicy)
            else:
                self.setSizePolicy(self._expandedSizePolicy, QSizePolicy.Expanding)
        else:
            self.layout().removeWidget(self.scroll_area)
            self.scroll_area.setVisible(False)
            if self._isVertical:
                self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
            else:
                self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Expanding)
        self.update()

    def isExpanded(self):
        return self.toggle_button.isChecked()

    def setExpanded(self, isExpanded):
        if isExpanded != self.toggle_button.isChecked():
            self.toggle_button.setChecked(isExpanded)

    def setContentLayout(self, layout):
        self.content.setLayout(layout)
        if self._startClosed:
            self.on_pressed()
