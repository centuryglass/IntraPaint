"""
A container widget that can be expanded or collapsed.
Originally adapted from https://stackoverflow.com/a/52617714
"""
from typing import Optional, cast

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QWidget, QScrollArea, QToolButton, QHBoxLayout, QVBoxLayout, QSizePolicy, QLayout, \
    QBoxLayout, QScrollBar

from src.ui.layout.bordered_widget import BorderedWidget
from src.ui.widget.label import Label


class CollapsibleBox(BorderedWidget):
    """A container widget that can be expanded or collapsed."""

    box_toggled = Signal(bool)

    def __init__(self,
                 title: str = '',
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
            Whether the box collapses vertically or horizontally.
        """
        super().__init__(parent)
        self._widget_size_max = self.maximumWidth()
        self._orientation = orientation
        self._expanded_size_policy = QSizePolicy.Policy.Preferred
        layout = QVBoxLayout(self) if self._orientation == Qt.Orientation.Vertical else QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self._toggle_button = QToolButton()
        self._toggle_button.setText(title)
        self._toggle_button.setCheckable(True)
        self._toggle_button.setChecked(not start_closed)
        self._toggle_button.setStyleSheet('QToolButton { border: none; }')
        self._button_bar = BorderedWidget()
        layout.addWidget(self._button_bar, stretch=0)
        if self._orientation == Qt.Orientation.Vertical:
            self._toggle_button.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonTextBesideIcon
            )
            self._toggle_label = None
            self._toggle_button.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed))
            self._button_bar.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum))
            self._button_bar_layout = QHBoxLayout(self._button_bar)
            alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            self._button_bar_layout.setAlignment(alignment)
            self._button_bar_layout.addWidget(self._toggle_button, stretch=1)
        else:
            self._toggle_label = Label(title)
            alignment = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
            self._toggle_label.setAlignment(alignment)
            self._toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            self._button_bar.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Expanding))
            self._button_bar_layout = QVBoxLayout(self._button_bar)
            self._button_bar_layout.setAlignment(alignment)
            self._button_bar_layout.addWidget(self._toggle_button)
            self._button_bar_layout.addWidget(self._toggle_label)
            self._button_bar_layout.setContentsMargins(0, 0, 0, 0)
            min_width = self._toggle_label.image_size().width() + 2
            for widget in [self._button_bar, self._toggle_label, self._toggle_button]:
                widget.setMinimumWidth(min_width)
        self._toggle_button.setArrowType(Qt.ArrowType.DownArrow if self._orientation == Qt.Orientation.Vertical
                                         else Qt.ArrowType.RightArrow)
        self._toggle_button.toggled.connect(self.on_pressed)

        if scrolling:
            self.scroll_area = QScrollArea()
            self.content = QWidget(self.scroll_area)
            self.content.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
            self.scroll_area.setWidget(self.content)
            self.scroll_area.setWidgetResizable(True)
        else:
            self.scroll_area = QWidget(self)
            self.content = self.scroll_area
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        if self._orientation == Qt.Orientation.Vertical:
            self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, self._expanded_size_policy)
        else:
            self.setSizePolicy(self._expanded_size_policy, QSizePolicy.Policy.MinimumExpanding)

        layout.addWidget(self.scroll_area, stretch=255)
        self._start_closed = start_closed

    @property
    def scroll_bar(self) -> Optional[QScrollBar]:
        """Access the vertical scroll bar, if one exists."""
        if isinstance(self.scroll_area, QScrollArea):
            return self.scroll_area.verticalScrollBar()
        return None

    # noinspection PyPep8Naming
    def setHorizontalScrollBarPolicy(self, policy: Qt.ScrollBarPolicy) -> None:
        """Expose scroll bar horizontal policy control for the inner scroll area."""
        if isinstance(self.scroll_area, QScrollArea):
            self.scroll_area.setHorizontalScrollBarPolicy(policy)

    @property
    def orientation(self) -> Qt.Orientation:
        """Returns whether the widget opens and closes vertically or horizontally."""
        return self.orientation

    def set_title_label(self, title: str) -> None:
        """Updates the title label."""
        if self._toggle_label is None:
            self._toggle_button.setText(title)
        else:
            self._toggle_label.setText(title)

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
            if self._orientation == Qt.Orientation.Vertical:
                self.setSizePolicy(QSizePolicy.Policy.Expanding, self._expanded_size_policy)
            else:
                self.setSizePolicy(self._expanded_size_policy, QSizePolicy.Policy.Expanding)

    def toggled(self) -> Signal:
        """Returns the internal Signal emitted when the box is expanded or collapsed."""
        return self._toggle_button.toggled

    def show_button_bar(self, show_bar: bool) -> None:
        """Sets whether the box bar with the label and toggle button should be shown or hidden.

        If hidden, the box will be forced into the "expanded" state.
        """
        layout = self.layout()
        if layout is None:
            return
        layout = cast(QBoxLayout, layout)
        layout.setStretch(0, 1 if show_bar else 0)
        button_bar = self._button_bar
        if button_bar is None:
            return
        button_bar.setEnabled(show_bar)
        button_bar.setVisible(show_bar)
        if self._orientation == Qt.Orientation.Vertical:
            button_bar.setMaximumHeight(self.height() if show_bar else 0)
        else:
            button_bar.setMaximumWidth(self.width() if show_bar else 0)
            min_width = 0
            if show_bar and self._toggle_label is not None:
                min_width = self._toggle_label.image_size().width() + 2
            for widget in [button_bar, self._toggle_label, self._toggle_button]:
                if widget is not None and hasattr(widget, 'setMinimumWidth'):
                    widget.setMinimumWidth(min_width)
        if not show_bar:
            self.set_expanded(True)

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Keep toolbar items sized correctly."""
        min_bar_dim = min(self._button_bar.width(), self._button_bar.height(), self._button_bar.sizeHint().width(),
                          self._button_bar.sizeHint().height())
        for widget in self._button_bar_layout.findChildren(QWidget):
            if widget in (self._toggle_button, self._toggle_label):
                continue
            widget.setMaximumHeight(min_bar_dim)
            widget.setMaximumWidth(min_bar_dim)
            widget.setMinimumHeight(min_bar_dim)
            widget.setMinimumWidth(min_bar_dim)

    def add_button_bar_widget(self, widget: QWidget, fixed_widget_size=True) -> None:
        """Adds a widget to the button bar."""
        if fixed_widget_size:
            widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._button_bar_layout.addWidget(widget)
        self.resizeEvent(None)

    def sizeHint(self) -> QSize:
        """Returns ideal box size based on expanded size policy and expansion state."""
        size = super().sizeHint()
        if not self._toggle_button.isChecked():
            if self._orientation == Qt.Orientation.Vertical:
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
            Qt.ArrowType.DownArrow if (checked == (self._orientation == Qt.Orientation.Vertical))
            else Qt.ArrowType.RightArrow)
        if checked:
            layout.addWidget(self.scroll_area, stretch=255)
            self.scroll_area.setVisible(True)
            if self._orientation == Qt.Orientation.Vertical:
                self.setSizePolicy(QSizePolicy.Policy.Expanding, self._expanded_size_policy)
            else:
                self.setSizePolicy(self._expanded_size_policy, QSizePolicy.Policy.Expanding)
            self.box_toggled.emit(True)
        else:
            layout.removeWidget(self.scroll_area)
            self.scroll_area.setVisible(False)
            if self._orientation == Qt.Orientation.Vertical:
                self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
            else:
                self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Expanding)
            self.box_toggled.emit(False)
        self.update()

    def is_expanded(self) -> bool:
        """Returns whether the box is currently expanded."""
        return self._toggle_button.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        """Sets whether the box is in the expanded state."""
        if expanded != self._toggle_button.isChecked():
            self._toggle_button.setChecked(expanded)
