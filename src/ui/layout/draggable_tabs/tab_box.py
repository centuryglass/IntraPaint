"""
Collapsible container widget that displays tab content.

The sole responsibility of the TabBox is to create, display and provide access to a TabBar, and to show an extra
content widget if the TabBar is in the open state.
"""

from typing import Optional, List

from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QSizePolicy, QBoxLayout

from src.ui.layout.bordered_widget import BorderedWidget
from src.ui.layout.draggable_tabs.tab import Tab
from src.ui.layout.draggable_tabs.tab_bar import TabBar
from src.util.layout import extract_layout_item

EMPTY_MARGIN = 0
NONEMPTY_MARGIN = 2


class TabBox(BorderedWidget):
    """Collapsible container widget that displays tab content."""

    box_toggled = Signal(bool)
    box_will_open = Signal(QWidget)
    tab_added = Signal(Tab)
    tab_removed = Signal(Tab)

    def __init__(self, orientation: Qt.Orientation, at_parent_start: bool, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # Setup layout and orientation:
        self._orientation = orientation
        self._at_parent_start = at_parent_start
        self._layout = QHBoxLayout(self) if orientation == Qt.Orientation.Vertical else QVBoxLayout(self)
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(1, 1, 1, 1)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        if orientation == Qt.Orientation.Horizontal:
            if at_parent_start:
                self._layout.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignVCenter)
            else:
                self._layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignVCenter)
        else:
            if at_parent_start:
                self._layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignHCenter)
            else:
                self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignHCenter)

        # Initialize tab bar and connect tab bar signals:
        self._tab_bar = TabBar(orientation, at_parent_start, parent=self)
        self._active_tab: Optional[Tab] = None
        self._open_tab_widget: Optional[QWidget] = None
        self._layout.addWidget(self._tab_bar)
        self._tab_bar.toggled.connect(self._box_opened_slot)
        self._tab_bar.active_tab_changed.connect(self._active_tab_change_slot)
        self._tab_bar.active_tab_content_replaced.connect(self._update_tab_content_slot)
        self._tab_bar.tab_added.connect(self.tab_added)
        self._tab_bar.tab_removed.connect(self.tab_removed)
        self._tab_bar.tab_bar_will_open.connect(lambda: self.box_will_open.emit(self))
        self._tab_bar.toggled.connect(self.box_toggled)
        self._tab_bar.toggled.connect(self._update_stretch_on_toggle)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self._default_border_color = self.frame_color
        self._empty_border_color = self._default_border_color
        self._empty_border_color.setAlphaF(0.5)
        self.frame_color = self._empty_border_color

    @property
    def active_tab_content(self) -> Optional[QWidget]:
        """Access the active tab's content widget, or None if no tab is present"""
        if self._active_tab is not None:
            return self._active_tab.content_widget
        return None

    @property
    def minimum_active_size(self) -> QSize:
        """Returns the minimum size of the TabBox when opened, or when closed if it contains no tabs."""
        if self.is_open:
            assert self._open_tab_widget is not None and self._open_tab_widget.parentWidget() == self
            return self.minimumSizeHint()
        own_minimum = self.minimumSizeHint()
        if self._active_tab is None:
            return own_minimum
        tab_content = self._active_tab.content_widget
        assert tab_content is not None
        content_minimum = tab_content.minimumSizeHint()
        if self._orientation == Qt.Orientation.Horizontal:
            return QSize(max(own_minimum.width(), content_minimum.width()),
                         own_minimum.height() + content_minimum.height())
        return QSize(own_minimum.width() + content_minimum.width(),
                     max(own_minimum.height(), content_minimum.height()))

    def add_widget(self, widget: QWidget, index: int = -1) -> None:
        """Add or insert a widget into the tab bar."""
        self._tab_bar.add_widget(widget, index)
        if len(self.tabs) > 0:
            self.frame_color = self._default_border_color
            self.setContentsMargins(NONEMPTY_MARGIN, NONEMPTY_MARGIN, NONEMPTY_MARGIN, NONEMPTY_MARGIN)

    def remove_widget(self, widget: QWidget) -> None:
        """Remove a widget from the tab bar."""
        self._tab_bar.remove_widget(widget)
        if len(self.tabs) == 0:
            self.frame_color = self._empty_border_color
            self.setContentsMargins(EMPTY_MARGIN, EMPTY_MARGIN, EMPTY_MARGIN, EMPTY_MARGIN)

    def contains_widget(self, widget: QWidget) -> bool:
        """Returns whether a widget is in the tab bar."""
        return widget.parent() == self._tab_bar

    @property
    def tabs(self) -> List[Tab]:
        """Returns all tabs in this tab box."""
        return self._tab_bar.tabs

    @property
    def count(self) -> int:
        """Returns the number of tabs in the box."""
        return len(self.tabs)

    def add_tab_bar_action(self, action: QAction) -> None:
        """Adds a right-click menu option to the tab bar."""
        self._tab_bar.addAction(action)

    @property
    def is_open(self) -> bool:
        """Return true if tab content is open (or would be open if the tab is non-empty)."""
        return self._tab_bar.is_open

    @is_open.setter
    def is_open(self, is_open: bool) -> None:
        self._tab_bar.is_open = is_open
        if self._open_tab_widget is not None:
            self._open_tab_widget.setVisible(is_open)

    def set_active_tab(self, tab: Optional[Tab]) -> None:
        """Add the active tab's widget to the box."""
        self._active_tab = tab
        new_tab_widget = None if tab is None else tab.content_widget
        if new_tab_widget == self._open_tab_widget:
            return
        if self._open_tab_widget is not None:
            self._layout.removeWidget(self._open_tab_widget)
            self._open_tab_widget.setVisible(False)
            self._open_tab_widget = None
        if new_tab_widget is not None:
            content_index = 0 if self._at_parent_start else 1
            self._layout.insertWidget(content_index, new_tab_widget)
            new_tab_widget.setVisible(self.is_open)
            if self.is_open:
                new_tab_widget.show()
            self._open_tab_widget = new_tab_widget
        if self.is_open and self._open_tab_widget is None:
            self.is_open = False

    def sizeHint(self) -> QSize:
        """Calculate size based on whether content is expanded."""
        return super().sizeHint() if self.is_open else self._tab_bar.sizeHint()

    def minimumSizeHint(self) -> QSize:
        """Calculate size based on whether content is expanded."""
        return super().minimumSizeHint() if self.is_open else self._tab_bar.minimumSizeHint()

    def _update_stretch_on_toggle(self, _=None) -> None:
        """Relinquish stretch when closed, reclaim it when opened"""
        parent = self.parentWidget()
        if parent is None:
            return
        parent_layout = parent.layout()
        if not isinstance(parent_layout, QBoxLayout):
            return
        total_stretch = 0
        own_idx = -1
        stretch_values = []
        for i in range(parent_layout.count()):
            stretch = parent_layout.stretch(i)
            total_stretch += stretch
            widget = extract_layout_item(parent_layout.itemAt(i))
            stretch_values.append(stretch)
            if widget == self:
                own_idx = i
        assert own_idx >= 0
        own_stretch = stretch_values[own_idx]
        active_stretch_item_count = len([stretch for stretch in stretch_values if stretch > 1])
        if own_stretch > 1:
            active_stretch_item_count -= 1
        if active_stretch_item_count == 0:
            return
        if self.is_open:  # Reclaim stretch from inline items, taking up to 1/3 total stretch:
            added_stretch = 0
            for i, stretch in enumerate(stretch_values):
                if i == own_idx or stretch < 2:
                    continue
                stretch_taken = min(round(stretch / max(active_stretch_item_count, 3)), stretch - 1)
                if stretch_taken > 0:
                    parent_layout.setStretch(i, stretch - stretch_taken)
                    added_stretch += stretch_taken
            if added_stretch > 0:
                parent_layout.setStretch(own_idx, own_stretch + added_stretch)
        else:  # Divide all stretch except one among inline items with more than one stretch:
            items_left = active_stretch_item_count
            stretch_remaining = own_stretch - 1
            for i, stretch in enumerate(stretch_values):
                if i == own_idx or stretch < 2:
                    continue
                if items_left == 1:
                    stretch_given = stretch_remaining
                else:
                    stretch_given = min(round((own_stretch - 1) / active_stretch_item_count), stretch_remaining)
                parent_layout.setStretch(i, stretch_values[i] + stretch_given)
                stretch_remaining -= stretch_given
                items_left -= 1
            assert stretch_remaining == 0
            assert items_left == 0
            parent_layout.setStretch(own_idx, 1)

    def _active_tab_change_slot(self, tab: QWidget) -> None:
        assert tab is None or isinstance(tab, Tab)
        self.set_active_tab(tab)

    def _update_tab_content_slot(self, new_tab_content: QWidget) -> None:
        assert self._active_tab is not None and new_tab_content == self._active_tab.content_widget
        self.set_active_tab(self._active_tab)

    def _box_opened_slot(self, is_open: bool) -> None:
        tab_widget = self._open_tab_widget
        if tab_widget is None:
            assert self._active_tab is None or self._active_tab.content_widget is None
        else:
            assert self._active_tab is not None and self._active_tab.content_widget == tab_widget
            content_index = 0 if self._at_parent_start else 1
            tab_widget.setVisible(is_open)
            if is_open:
                tab_widget.show()
            self._layout.setStretch(content_index, 1 if is_open else 0)
