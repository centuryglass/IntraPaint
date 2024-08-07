"""Collapsible container widget that displays tab content."""

from typing import Optional

from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QSizePolicy

from src.ui.widget.bordered_widget import BorderedWidget
from src.ui.widget.draggable_tabs.tab import Tab
from src.ui.widget.draggable_tabs.tab_bar import TabBar
from src.util.shared_constants import MAX_WIDGET_SIZE


class TabBox(BorderedWidget):
    """Collapsible container widget that displays tab content."""

    box_toggled = pyqtSignal(bool)

    def __init__(self, orientation: Qt.Orientation, at_parent_start: bool) -> None:
        super().__init__()
        self._orientation = orientation
        self._at_parent_start = at_parent_start
        self._layout = QHBoxLayout(self) if orientation == Qt.Orientation.Vertical else QVBoxLayout(self)
        self._tab_bar = TabBar(orientation, at_parent_start)
        self._active_tab: Optional[Tab] = None
        self._open_tab_widget: Optional[QWidget] = None
        self._layout.addWidget(self._tab_bar)
        self._tab_bar.toggled.connect(self._box_opened_slot)
        self._tab_bar.tab_clicked.connect(self._tab_clicked_slot)
        self._tab_bar.active_tab_content_replaced.connect(self._update_tab_slot)
        self._tab_bar.max_size_changed.connect(self._update_max_size)
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self._update_max_size()
        if orientation == Qt.Orientation.Horizontal:
            self._layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignVCenter)
        else:
            self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignHCenter)

    def add_widget(self, widget: QWidget, index: int = -1) -> None:
        """Add or insert a widget into the tab bar."""
        self._tab_bar.add_widget(widget, index)

    def remove_widget(self, widget: QWidget) -> None:
        """Remove a widget from the tab bar."""
        self._tab_bar.remove_widget(widget)

    def contains_widget(self, widget: QWidget) -> bool:
        """Returns whether a widget is in the tab bar."""
        return widget.parent() == self._tab_bar

    @property
    def is_open(self) -> bool:
        """Return true if tab content is open (or would be open if the tab is non-empty)."""
        return self._tab_bar.is_open

    @is_open.setter
    def is_open(self, is_open: bool) -> None:
        self._tab_bar.is_open = is_open

    def set_active_tab(self, tab: Optional[Tab]) -> None:
        """Add the active tab's widget to the box."""
        self._active_tab = tab
        new_tab_widget = None if tab is None else tab.content_widget
        if tab is not None:
            assert new_tab_widget is not None
        if new_tab_widget == self._open_tab_widget:
            return
        if self._open_tab_widget is not None:
            self._layout.removeWidget(self._open_tab_widget)
            self._open_tab_widget.setVisible(False)
        if new_tab_widget is not None:
            content_index = 0 if self._at_parent_start else 1
            self._layout.insertWidget(content_index, new_tab_widget)
            new_tab_widget.setVisible(self.is_open)
            if self.is_open:
                new_tab_widget.show()
            self._layout.setStretch(content_index, 1 if self.is_open else 0)
        self._open_tab_widget = new_tab_widget
        if self.is_open and self._open_tab_widget is None:
            self.is_open = False
        self._update_max_size()

    def sizeHint(self) -> QSize:
        """Calculate size based on whether content is expanded."""
        return super().sizeHint() if self.is_open else self._tab_bar.sizeHint()

    def _tab_clicked_slot(self, tab: QWidget) -> None:
        assert tab is None or isinstance(tab, Tab)
        self.set_active_tab(tab)

    def _update_tab_slot(self, new_tab_content: QWidget) -> None:
        assert self._active_tab is not None and new_tab_content == self._active_tab.content_widget
        self.set_active_tab(self._active_tab)

    def _update_max_size(self, _=None) -> None:
        if not self.is_open or self._open_tab_widget is None:
            self.setMaximumSize(self._tab_bar.maximumSize())
        else:
            self.setMaximumSize(MAX_WIDGET_SIZE, MAX_WIDGET_SIZE)
        if self._orientation == Qt.Orientation.Horizontal:
            min_height = self._tab_bar.minimumHeight()
            if self.is_open and self._open_tab_widget is not None:
                min_height += self._open_tab_widget.sizeHint().height()
            self.setMinimumHeight(min_height)
        else:
            min_width = self._tab_bar.minimumWidth()
            if self.is_open and self._open_tab_widget is not None:
                min_width += self._open_tab_widget.sizeHint().width()
            self.setMinimumWidth(min_width)
        tab_widget = self._open_tab_widget
        if tab_widget is None:
            return
        if self._orientation == Qt.Orientation.Horizontal:
            tab_widget.setMaximumHeight(MAX_WIDGET_SIZE if self.is_open else 0)
            tab_widget.setMaximumWidth(MAX_WIDGET_SIZE)
            tab_widget.setMinimumHeight(50 if self.is_open else 0)
        else:
            tab_widget.setMaximumWidth(MAX_WIDGET_SIZE if self.is_open else 0)
            tab_widget.setMaximumHeight(MAX_WIDGET_SIZE)
            tab_widget.setMinimumWidth(50 if self.is_open else 0)

    def _box_opened_slot(self, is_open: bool) -> None:
        tab_widget = self._open_tab_widget
        if tab_widget is None:
            return
        content_index = 0 if self._at_parent_start else 1
        tab_widget.setVisible(is_open)
        if is_open:
            tab_widget.show()
        self._layout.setStretch(content_index, 1 if is_open else 0)
        self._update_max_size()
