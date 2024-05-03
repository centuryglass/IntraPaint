"""
A container widget that can be expanded or collapsed.
Originally adapted from https://stackoverflow.com/a/52617714
"""
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
            start_closed=False,
            scrolling=True,
            orientation=Qt.Orientation.Vertical):
        super(CollapsibleBox, self).__init__(parent)
        self._widgetsize_max = self.maximumWidth()
        self._is_vertical = (orientation == Qt.Orientation.Vertical)
        self._expanded_size_policy = QSizePolicy.Preferred
        layout = QVBoxLayout(self) if self._is_vertical else QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)


        self._toggle_button = QToolButton(
            text=title, checkable=True, checked=not start_closed
        )
        self._toggle_button.setStyleSheet("QToolButton { border: none; }")
        if self._is_vertical:
            self._toggle_button.setToolButtonStyle(
                QtCore.Qt.ToolButtonTextBesideIcon
            )
            layout.addWidget(self._toggle_button, stretch=1)
            self._toggle_button.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding))
        else:
            self._toggle_label = Label(title)
            self._toggle_label.setAlignment(Qt.AlignTop)
            self._toggle_button.setToolButtonStyle(
                QtCore.Qt.ToolButtonIconOnly
            )
            button_bar = QWidget()
            button_bar_layout = QVBoxLayout()
            button_bar_layout.addWidget(self._toggle_button, alignment=Qt.AlignTop)
            button_bar_layout.addWidget(self._toggle_label, alignment=Qt.AlignTop)
            button_bar_layout.addStretch(255)
            button_bar_layout.setContentsMargins(0,0,0,0)
            button_bar.setLayout(button_bar_layout)
            button_bar.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed))
            min_width = self._toggle_label.image_size().width() + 2
            for widget in [button_bar, self._toggle_label, self._toggle_button]:
                widget.setMinimumWidth(min_width)
            layout.addWidget(button_bar, stretch=1)
        self._toggle_button.setArrowType(QtCore.Qt.DownArrow if self._is_vertical else QtCore.Qt.RightArrow)
        self._toggle_button.toggled.connect(lambda: self.on_pressed())

        if scrolling:
            self.scroll_area = QScrollArea()
            self.content = QWidget(self.scroll_area)
            self.scroll_area.setWidget(self.content)
            self.scroll_area.setWidgetResizable(True)
        else:
            self.scroll_area = QWidget()
            self.content = self.scroll_area
        self.scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        if self._is_vertical:
            self.setSizePolicy(QSizePolicy.Expanding, self._expanded_size_policy)
        else:
            self.setSizePolicy(self._expanded_size_policy, QSizePolicy.Expanding)
        
        layout.addWidget(self.scroll_area, stretch=255)
        self._startClosed = start_closed

    def set_expanded_size_policy(self, policy):
        if policy == self._expanded_size_policy:
            return
        self._expanded_size_policy = policy
        if self.is_expanded():
            if self._is_vertical:
                self.setSizePolicy(QSizePolicy.Expanding, self._expanded_size_policy)
            else:
                self.setSizePolicy(self._expanded_size_policy, QSizePolicy.Expanding)

    def toggled(self):
        return self._toggle_button.toggled

    def show_button_bar(self, showBar):
        self.layout().setStretch(0, 1 if showBar else 0)
        button_bar = self.layout().itemAt(0).widget()
        button_bar.setEnabled(showBar)
        button_bar.setVisible(showBar)
        if self._is_vertical:
            button_bar.setMaximumHeight(self.height() if showBar else 0)
        else:
            button_bar.setMaximumWidth(self.width() if showBar else 0)
            minWidth = (self._toggle_label.image_size().width() + 2) if showBar else 0
            for widget in [button_bar, self._toggle_label, self._toggle_button]:
                widget.setMinimumWidth(minWidth)
        if not showBar:
            self.set_expanded(True)

    def sizeHint(self):
        size = super().sizeHint()
        if not self._toggle_button.isChecked():
            if self._is_vertical:
                size.setWidth(self._toggle_button.sizeHint().width())
            else:
                size.setHeight(self._toggle_button.sizeHint().height())
        return size

    def on_pressed(self):
        checked = self._toggle_button.isChecked()
        self._toggle_button.setArrowType(
            QtCore.Qt.DownArrow if (checked == self._is_vertical) else QtCore.Qt.RightArrow)
        if checked:
            self.layout().addWidget(self.scroll_area, stretch=255)
            self.scroll_area.setVisible(True)
            if self._is_vertical:
                self.setSizePolicy(QSizePolicy.Expanding, self._expanded_size_policy)
            else:
                self.setSizePolicy(self._expanded_size_policy, QSizePolicy.Expanding)
        else:
            self.layout().removeWidget(self.scroll_area)
            self.scroll_area.setVisible(False)
            if self._is_vertical:
                self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
            else:
                self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Expanding)
        self.update()

    def is_expanded(self):
        return self._toggle_button.isChecked()

    def set_expanded(self, expanded):
        if expanded != self._toggle_button.isChecked():
            self._toggle_button.setChecked(expanded)

    def set_content_layout(self, layout):
        self.content.setLayout(layout)
        if self._startClosed:
            self.on_pressed()
