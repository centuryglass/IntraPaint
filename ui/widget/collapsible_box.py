"""
A container widget that can be expanded or collapsed.
Originally adapted from https://stackoverflow.com/a/52617714
"""
from typing import Optional
from PyQt5.QtWidgets import QWidget, QScrollArea, QToolButton, QHBoxLayout, QVBoxLayout, QSizePolicy, QLayout, \
         QBoxLayout
from PyQt5.QtCore import Qt, QSize, pyqtBoundSignal

from ui.widget.bordered_widget import BorderedWidget
from ui.widget.label import Label


class CollapsibleBox(BorderedWidget):
    """A container widget that can be expanded or collapsed."""


    def __init__(self,
            title: str = "",
            parent: Optional[QWidget] = None,
            start_closed: bool = False,
            scrolling: bool = True,
            orientation: Qt.Orientation = Qt.Orientation.Vertical):
        """Initializes the widget, optionally adding it to a parent widget.

        Parameters
        ----------
        title : str
            Title label string
        parent : QWidget, default=None
            Optional parent widget.
        start_closed : bool, default=False
            If true, the widget should initially be in the closed state with contents hidden.
        scrolling : bool, default=True
            If true, use scroll bars if box content exceeds the ideal widget bounds
        orientation : Qt.Orientation, default=Vertical
            Whether the box collapses to a vertically or horizontally.
        """
        super().__init__(parent)
        self._widgetsize_max = self.maximumWidth()
        self._is_vertical = orientation == Qt.Orientation.Vertical
        self._expanded_size_policy = QSizePolicy.Preferred
        layout = QVBoxLayout(self) if self._is_vertical else QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)


        self._toggle_button = QToolButton(text=title, checkable=True, checked=not start_closed)
        self._toggle_button.setStyleSheet("QToolButton { border: none; }")
        if self._is_vertical:
            self._toggle_button.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonTextBesideIcon
            )
            layout.addWidget(self._toggle_button, stretch=1)
            self._toggle_button.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding))
        else:
            self._toggle_label = Label(title)
            self._toggle_label.setAlignment(Qt.AlignmentFlag.AlignTop)
            self._toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            button_bar = QWidget()
            button_bar_layout = QVBoxLayout()
            button_bar_layout.addWidget(self._toggle_button, alignment=Qt.AlignmentFlag.AlignTop)
            button_bar_layout.addWidget(self._toggle_label, alignment=Qt.AlignmentFlag.AlignTop)
            button_bar_layout.addStretch(255)
            button_bar_layout.setContentsMargins(0,0,0,0)
            button_bar.setLayout(button_bar_layout)
            button_bar.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed))
            min_width = self._toggle_label.image_size().width() + 2
            for widget in [button_bar, self._toggle_label, self._toggle_button]:
                widget.setMinimumWidth(min_width)
            layout.addWidget(button_bar, stretch=1)
        self._toggle_button.setArrowType(Qt.ArrowType.DownArrow if self._is_vertical else Qt.ArrowType.RightArrow)
        self._toggle_button.toggled.connect(self.on_pressed)

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
        self._start_closed = start_closed


    def set_content_layout(self, layout: QLayout) -> None:
        """Adds a layout to the widget.

        Items should be added to the box by adding them to this layout.

        Parameters
        ----------
        layout : QLayout
            Any type of pyQt5 layout object.
        """
        self.content.setLayout(layout)
        if self._start_closed:
            self.on_pressed()

    def set_expanded_size_policy(self, policy: QSizePolicy.Policy) -> None:
        """Sets the size policy applied to widget content along the expansion axis when expanded.

        Parameters
        ----------
        policy : QSizePolicy flag
            Policy applied to width when expanded and horizontal, or height when expanded and vertical.
        """
        if policy == self._expanded_size_policy:
            return
        self._expanded_size_policy = policy
        if self.is_expanded():
            if self._is_vertical:
                self.setSizePolicy(QSizePolicy.Expanding, self._expanded_size_policy)
            else:
                self.setSizePolicy(self._expanded_size_policy, QSizePolicy.Expanding)


    def toggled(self) -> pyqtBoundSignal:
        """Returns the internal pyqtSignal emitted when the box is expanded or collapsed."""
        return self._toggle_button.toggled


    def show_button_bar(self, show_bar: bool) -> None:
        """Sets whether the box bar with the label and toggle button should be shown or hidden.

        If hidden, the box will be forced into the "expanded" state.
        """
        layout = self.layout()
        if layout is None:
            return
        assert isinstance(layout, QBoxLayout)
        layout.setStretch(0, 1 if show_bar else 0)
        layout_item = layout.itemAt(0)
        if layout_item is None:
            return
        button_bar = layout_item.widget()
        if button_bar is None:
            return
        button_bar.setEnabled(show_bar)
        button_bar.setVisible(show_bar)
        if self._is_vertical:
            button_bar.setMaximumHeight(self.height() if show_bar else 0)
        else:
            button_bar.setMaximumWidth(self.width() if show_bar else 0)
            min_width = (self._toggle_label.image_size().width() + 2) if show_bar else 0
            for widget in [button_bar, self._toggle_label, self._toggle_button]:
                widget.setMinimumWidth(min_width)
        if not show_bar:
            self.set_expanded(True)


    def sizeHint(self) -> QSize:
        """Returns ideal box size based on expanded size policy and expansion state."""
        size = super().sizeHint()
        if not self._toggle_button.isChecked():
            if self._is_vertical:
                size.setWidth(self._toggle_button.sizeHint().width())
            else:
                size.setHeight(self._toggle_button.sizeHint().height())
        return size


    def on_pressed(self) -> None:
        """When clicked, show or hide box content."""
        layout = self.layout()
        if layout is None:
            return
        assert isinstance(layout, QBoxLayout)
        checked = self._toggle_button.isChecked()
        self._toggle_button.setArrowType(
            Qt.ArrowType.DownArrow if (checked == self._is_vertical) else Qt.ArrowType.RightArrow)
        if checked:
            layout.addWidget(self.scroll_area, stretch=255)
            self.scroll_area.setVisible(True)
            if self._is_vertical:
                self.setSizePolicy(QSizePolicy.Expanding, self._expanded_size_policy)
            else:
                self.setSizePolicy(self._expanded_size_policy, QSizePolicy.Expanding)
        else:
            layout.removeWidget(self.scroll_area)
            self.scroll_area.setVisible(False)
            if self._is_vertical:
                self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
            else:
                self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Expanding)
        self.update()


    def is_expanded(self) -> bool:
        """Returns whether the box is currently expanded."""
        return self._toggle_button.isChecked()


    def set_expanded(self, expanded: bool) -> None:
        """Sets whether the box is in the expanded state."""
        if expanded != self._toggle_button.isChecked():
            self._toggle_button.setChecked(expanded)
