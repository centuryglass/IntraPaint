"""Widget bar that accepts draggable tabs.

Most of the functionality in draggable_tabs is handled within the TabBar, including the following:
- Displaying a set of widgets, sorted between Tab widgets and others.
- Keeping track of which Tab is currently active.
- Tracking whether the content widget associated with a Tab should be displayed.
- Allowing the user to switch between different tabs on the bar.
- Displaying a set of optional tab bar widgets for each Tab, except when that tab's main content widget is showing.
- Accepting Tabs dragged from other TabBars
"""
from typing import Optional

from PySide6.QtCore import Signal, Qt, QPointF, QLine, QSize, QTimer
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QDropEvent, QPaintEvent, QPainter
from PySide6.QtWidgets import QWidget, QBoxLayout, QHBoxLayout, QVBoxLayout, QToolButton, QSizePolicy, QFrame

from src.ui.layout.draggable_tabs.tab import Tab
from src.ui.panel.layer_ui.layer_widget import LayerWidget
from src.util.layout import clear_layout
from src.util.signals_blocked import signals_blocked

BASE_EMPTY_BAR_SIZE = 10
TAB_BAR_OPEN_DELAY_MS = 100
INLINE_MARGIN = 2
EDGE_MARGIN = 5
BASE_MARGIN = 3


class TabBar(QFrame):
    """Widget bar that can accept dragged tabs."""

    active_tab_changed = Signal(Tab)
    active_tab_content_replaced = Signal(Tab)
    tab_clicked = Signal(Tab)
    tab_added = Signal(Tab)
    tab_removed = Signal(Tab)
    toggled = Signal(bool)
    tab_bar_will_open = Signal()

    def __init__(self, orientation: Qt.Orientation, at_parent_start: bool, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout: QBoxLayout = QHBoxLayout(self) if orientation == Qt.Orientation.Horizontal else QVBoxLayout(self)
        self._orientation = orientation
        self._at_parent_start = at_parent_start
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)

        # TabBar open/close toggle button setup:
        self._toggle_button = QToolButton()
        self._toggle_button.setCheckable(True)
        self._toggle_button.setChecked(False)
        self._toggle_button.setStyleSheet('QToolButton { border: none; }')
        self._toggle_button.toggled.connect(self._toggle_button_slot)
        self._toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._toggle_button.setChecked(False)
        self._layout.addWidget(self._toggle_button)
        self._toggle_button.setVisible(False)
        self._toggle_button.setEnabled(False)
        self._active_tab: Optional[Tab] = None

        # Remaining layout contents: all tabs, a spacer, then all additional widgets
        self._tabs: list[Tab] = []
        self._spacer_widget = QWidget(self)
        self._layout.addWidget(self._spacer_widget, stretch=5)
        self._widgets: list[QWidget] = []

        # Track pending drag and drop state:
        self._insert_pos: Optional[int] = None
        self._insert_index: Optional[int] = None
        self._drag_list: Optional[list[QWidget] | list[Tab]] = None
        self.setAcceptDrops(True)

        # Track active tab, tab widget open/close state:
        self._is_open = False
        self._tab_open_timer = QTimer()
        self._tab_open_timer.setInterval(TAB_BAR_OPEN_DELAY_MS)
        self._tab_open_timer.setSingleShot(True)
        self._tab_open_timer.timeout.connect(self._finish_tab_open)

        self._apply_orientation()

    @property
    def active_tab(self) -> Optional[Tab]:
        """Gets and sets the active tab.

        Only one tab in the tab bar may be active at a time. When the bar is open, the active tab's tab bar widgets
        will be hidden.
        """
        return self._active_tab

    @active_tab.setter
    def active_tab(self, tab: Optional[Tab]) -> None:
        if tab == self._active_tab:
            return
        if tab is not None and tab not in self._tabs:
            raise ValueError(f'Tried to activate tab "{tab.text()}" not found in the list of tabs')
        if self._active_tab is not None:
            for tab_bar_widget in self._active_tab.tab_bar_widgets:
                assert tab_bar_widget in self._widgets
                tab_bar_widget.setVisible(True)
        self._active_tab = tab
        if tab is not None:
            for tab_bar_widget in tab.tab_bar_widgets:
                assert tab_bar_widget in self._widgets
                tab_bar_widget.setVisible(not self.is_open)
        self.active_tab_changed.emit(tab)
        self.repaint()

    @property
    def is_open(self) -> bool:
        """Access whether the tab bar is open.

         When the tab bar is open, the active tab's content widget should be displayed next to the bar. The tab bar
         can only be open if it contains at least one tab."""
        return self._is_open

    @is_open.setter
    def is_open(self, is_open: bool) -> None:
        if self.active_tab is None:
            is_open = False
        if self._toggle_button.isChecked() != is_open:
            with signals_blocked(self._toggle_button):
                self._toggle_button.setChecked(is_open)
                self._update_toggle_arrow(is_open)
        if is_open == self._is_open:
            return
        if is_open:
            if not self._tab_open_timer.isActive():
                self._tab_open_timer.start()
                self.tab_bar_will_open.emit()
        else:
            if self._tab_open_timer.isActive():
                self._tab_open_timer.stop()
            self._is_open = False
            self._update_tab_widget_visibility()
            self._update_toggle_arrow(False)
            self.toggled.emit(False)

    def _finish_tab_open(self) -> None:
        self._tab_open_timer.stop()
        if self._active_tab is None:
            self.is_open = False
            return
        if not self._toggle_button.isChecked():
            with signals_blocked(self._toggle_button):
                self._toggle_button.setChecked(True)
        active_tab = self.active_tab
        assert active_tab is not None
        for tab_bar_widget in active_tab.tab_bar_widgets:
            assert tab_bar_widget in self._widgets
            tab_bar_widget.setVisible(True)
        self._is_open = True
        self._update_toggle_arrow(True)
        self._update_tab_widget_visibility()
        self.toggled.emit(True)

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Switch between vertical and horizontal orientation."""
        if self._orientation != orientation:
            self._orientation = orientation
            self._apply_orientation()

    def sizeHint(self) -> QSize:
        """Returns a reduced thickness when the bar is empty."""
        hint = super().sizeHint()
        if len(self._tabs) == 0 and len(self._widgets) == 0:
            if self._orientation == Qt.Orientation.Horizontal:
                hint.setHeight(BASE_EMPTY_BAR_SIZE)
            else:
                hint.setWidth(BASE_EMPTY_BAR_SIZE)
        return hint

    def minimumSizeHint(self) -> QSize:
        """Returns a reduced thickness when the bar is empty."""
        hint = super().minimumSizeHint()
        if len(self._tabs) == 0 and len(self._widgets) == 0:
            if self._orientation == Qt.Orientation.Horizontal:
                hint.setHeight(BASE_EMPTY_BAR_SIZE)
            else:
                hint.setWidth(BASE_EMPTY_BAR_SIZE)
        return hint

    def add_tab(self, tab: Tab, index: Optional[int] = None) -> None:
        """Add a tab to the bar."""
        if index is None or index < 0:
            index = len(self._tabs)
        if tab in self._tabs:
            self.move_widget(tab, index)
            return
        last_parent = tab.parent()
        if isinstance(last_parent, TabBar):
            last_parent.remove_widget(tab)
        self._tabs.insert(index, tab)
        if len(self._tabs) == 1:
            self._toggle_button.setEnabled(True)
            self._toggle_button.setVisible(True)
        self._layout.insertWidget(1 + index, tab)
        tab.show()
        self._apply_widget_orientation(tab)
        tab.clicked.connect(self._tab_clicked_slot)
        tab.double_clicked.connect(self._tab_double_clicked_slot)
        tab.tab_content_replaced.connect(self._tab_widget_change_slot)
        tab.tab_bar_widget_added.connect(self.add_widget)
        tab.tab_bar_widget_removed.connect(self.remove_widget)
        tab.tab_bar_widget_order_changed.connect(self._update_widget_order)
        tab_content_widget = tab.content_widget
        if tab_content_widget is not None:
            self._apply_widget_orientation(tab_content_widget)
        widget_insert_idx = self._layout.indexOf(self._spacer_widget) + 1
        for other_tab in self._tabs:
            if other_tab == tab:
                break
            widget_insert_idx += len(other_tab.tab_bar_widgets)
        for tab_bar_widget in tab.tab_bar_widgets:
            self.add_widget(tab_bar_widget, widget_insert_idx)
            widget_insert_idx += 1
        self.tab_added.emit(tab)
        if self.active_tab is None:
            self.active_tab = tab
            self.tab_clicked.emit(tab)
            self.is_open = True
            self.update()

    def add_widget(self, widget: QWidget, index: Optional[int] = None) -> None:
        """Add a widget to the bar."""
        if widget in self._widgets:
            if index is not None:
                self.move_widget(widget, index)
            return
        if isinstance(widget, Tab):
            self.add_tab(widget, index)
            return
        last_parent = widget.parent()
        if isinstance(last_parent, TabBar):
            last_parent.remove_widget(widget)
        if index is None or index < 0:
            index = len(self._widgets)
        index = min(index, len(self._widgets))
        self._widgets.insert(index, widget)
        layout_index = min(self._layout.indexOf(self._spacer_widget) + index + 1, self._layout.count())
        self._apply_widget_orientation(widget)
        self._layout.insertWidget(layout_index, widget)
        widget.show()
        if self.active_tab is not None and widget in self.active_tab.tab_bar_widgets:
            widget.setVisible(not self.is_open)
        self._update_widget_order()

    def remove_tab(self, tab: Tab) -> None:
        """Remove a tab from the bar."""
        assert tab in self._tabs
        self._tabs.remove(tab)
        if tab == self.active_tab:
            first_tab = None if len(self._tabs) == 0 else self._tabs[0]
            self.active_tab = first_tab
            if first_tab is not None:
                self.tab_clicked.emit(first_tab)
            if self.is_open:
                self.is_open = False
        tab.clicked.disconnect(self._tab_clicked_slot)
        tab.double_clicked.disconnect(self._tab_double_clicked_slot)
        tab.tab_content_replaced.disconnect(self._tab_widget_change_slot)
        tab.tab_bar_widget_added.disconnect(self.add_widget)
        tab.tab_bar_widget_removed.disconnect(self.remove_widget)
        tab.tab_bar_widget_order_changed.disconnect(self._update_widget_order)
        for tab_bar_widget in tab.tab_bar_widgets:
            if tab_bar_widget in self._widgets:
                self.remove_widget(tab_bar_widget)
        self.tab_removed.emit(tab)
        self._layout.removeWidget(tab)
        tab.hide()
        tab.setParent(None)
        if len(self._tabs) == 0:
            self._toggle_button.setEnabled(False)
            self._toggle_button.setVisible(False)
        self._update_widget_order()

    def remove_widget(self, widget: QWidget) -> None:
        """Remove a widget from the bar."""
        if isinstance(widget, Tab):
            self.remove_tab(widget)
            return
        assert widget in self._widgets
        widget.setVisible(False)
        self._widgets.remove(widget)
        self._layout.removeWidget(widget)
        widget.hide()
        widget.setParent(None)
        self.update()

    def move_widget(self, widget: QWidget, index: int) -> None:
        """Moves a widget to another position in the bar."""
        widget_list = self._tabs if isinstance(widget, Tab) else self._widgets
        assert widget in widget_list
        current_index = widget_list.index(widget)
        if index in (current_index, current_index + 1):
            return
        if index > current_index:
            index -= 1
        widget_list.remove(widget)
        widget_list.insert(index, widget)
        if isinstance(widget, Tab):
            layout_index = index + 1
            self._update_widget_order()
        else:
            spacer_index = self._layout.indexOf(self._spacer_widget)
            layout_index = spacer_index + 1 + index
        self._layout.removeWidget(widget)
        self._layout.insertWidget(layout_index, widget)
        self.update()
        self._update_widget_order()

    @property
    def tabs(self) -> list[Tab]:
        """Returns all tabs in this tab bar."""
        return list(self._tabs)

    def _update_toggle_arrow(self, checked: bool):
        if self._orientation == Qt.Orientation.Horizontal:
            open_arrow = Qt.ArrowType.UpArrow if self._at_parent_start else Qt.ArrowType.DownArrow
            closed_arrow = Qt.ArrowType.RightArrow
        else:
            open_arrow = Qt.ArrowType.LeftArrow if self._at_parent_start else Qt.ArrowType.RightArrow
            closed_arrow = Qt.ArrowType.DownArrow
        self._toggle_button.setArrowType(open_arrow if checked else closed_arrow)

    def _update_tab_widget_visibility(self) -> None:
        """Hide tab widgets only when their tab is active and the bar is open."""
        for tab in self._tabs:
            for widget in tab.tab_bar_widgets:
                widget.setVisible((not self.is_open) or (tab != self.active_tab))

    def _toggle_button_slot(self) -> None:
        self.is_open = self._toggle_button.isChecked()

    def _tab_clicked_slot(self, tab: QWidget) -> None:
        self.active_tab = tab

    def _tab_double_clicked_slot(self, tab: QWidget) -> None:
        """If double-clicking an inactive tab, activate it. If double-clicking the active tab, open or close tab
         content."""
        assert isinstance(tab, Tab)
        if self._active_tab != tab:
            self._tab_clicked_slot(tab)
            if not self.is_open:
                self.is_open = True
                self.update()
        else:
            self.is_open = not self.is_open
            self.update()

    def _tab_widget_change_slot(self, tab: QWidget, tab_widget: QWidget) -> None:
        if self._active_tab == tab:
            self.active_tab_content_replaced.emit(tab_widget)

    def _update_widget_order(self) -> None:
        """Ensure widgets are ordered in tab order, in the order provided by the tabs"""
        all_widgets = list(self._widgets)
        widget_idx = 0
        layout_idx = self._layout.indexOf(self._spacer_widget) + 1
        for tab in self._tabs:
            tab_widgets = tab.tab_bar_widgets
            for tab_widget in tab_widgets:
                try:
                    widget_list_idx = self._widgets.index(tab_widget)
                except ValueError:
                    return  # Currently adding all widgets in a Tab, wait until they're all added to sort.
                widget_layout_idx = self._layout.indexOf(tab_widget)
                assert widget_layout_idx != -1 and widget_list_idx != -1
                if widget_list_idx != widget_idx:
                    self._widgets.remove(tab_widget)
                    self._widgets.insert(widget_idx, tab_widget)
                if widget_layout_idx != layout_idx:
                    self._layout.removeWidget(tab_widget)
                    self._layout.insertWidget(layout_idx, tab_widget)
                widget_idx += 1
                layout_idx += 1
                all_widgets.remove(tab_widget)
        for non_tab_widget in all_widgets:
            self._widgets.remove(non_tab_widget)
            self._widgets.insert(widget_idx, non_tab_widget)
            self._layout.removeWidget(non_tab_widget)
            self._layout.insertWidget(layout_idx, non_tab_widget)
            widget_idx += 1
            layout_idx += 1

    def _alignment(self) -> Qt.AlignmentFlag:
        if self._orientation == Qt.Orientation.Horizontal:
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        # Vertical:
        return Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter

    def _size_policy(self, widget: QWidget) -> QSizePolicy:
        if widget == self:
            if self._orientation == Qt.Orientation.Horizontal:
                return QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            # Vertical:
            return QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        if widget in self._widgets or widget == self._toggle_button:
            if self._orientation == Qt.Orientation.Horizontal:
                return QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            # Vertical:
            return QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        # Panel widget:
        return QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _apply_widget_orientation(self, widget: QWidget) -> None:
        if hasattr(widget, 'setAlignment'):
            widget.setAlignment(self._alignment())
        if hasattr(widget, 'setOrientation'):
            widget.setOrientation(self._orientation)
        if hasattr(widget, 'set_orientation'):
            widget.set_orientation(self._orientation)

    def _apply_orientation(self) -> None:
        layout_class = QHBoxLayout if self._orientation == Qt.Orientation.Horizontal else QVBoxLayout
        if not isinstance(self._orientation, layout_class):
            clear_layout(self._layout, unparent=False)
            temp_widget = QWidget()
            temp_widget.setLayout(self._layout)
            self._layout = layout_class(self)
            self._layout.addWidget(self._toggle_button)
            for tab in self._tabs:
                self._layout.addWidget(tab)
            self._layout.addWidget(self._spacer_widget, stretch=5)
            for widget in self._widgets:
                self._layout.addWidget(widget)
        if self._orientation == Qt.Orientation.Horizontal:
            self._spacer_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
            margin_top = BASE_MARGIN if self._at_parent_start else EDGE_MARGIN
            margin_bottom = EDGE_MARGIN if self._at_parent_start else BASE_MARGIN
            self._layout.setContentsMargins(INLINE_MARGIN, margin_top, INLINE_MARGIN, margin_bottom)
            self.setMinimumHeight(BASE_EMPTY_BAR_SIZE)
        else:
            self._spacer_widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Expanding)
            margin_left = BASE_MARGIN if self._at_parent_start else EDGE_MARGIN
            margin_right = EDGE_MARGIN if self._at_parent_start else BASE_MARGIN
            self._layout.setContentsMargins(margin_left, INLINE_MARGIN, margin_right, INLINE_MARGIN)
            self.setMinimumWidth(BASE_EMPTY_BAR_SIZE)

        self._apply_widget_orientation(self)
        self._apply_widget_orientation(self._toggle_button)
        self._layout.setAlignment(self._alignment())
        for tab in self._tabs:
            self._apply_widget_orientation(tab)
            tab_widget = tab.content_widget
            if tab_widget is not None:
                self._apply_widget_orientation(tab_widget)
        for widget in self._widgets:
            self._apply_widget_orientation(widget)
        self._update_toggle_arrow(self._toggle_button.isChecked())
        self.setSizePolicy(self._size_policy(self))

    def _update_insert_pos(self, point: QPointF):
        """When dragging in a Tab or other widget, find where the tab will be placed."""
        if len(self._widgets) == 0:
            if self._insert_index != 0:
                self._insert_index = 0
                self._insert_pos = 10
                self.update()
            return
        mouse_pos = int(point.x() if self._orientation == Qt.Orientation.Horizontal else point.y())
        assert self._drag_list is not None
        start_widget = self._toggle_button if self._drag_list == self._tabs else self._spacer_widget
        if self._orientation == Qt.Orientation.Horizontal:
            margin = self._layout.contentsMargins().right()
            end_pos = start_widget.x() + start_widget.width()
        else:
            margin = self._layout.contentsMargins().bottom()
            end_pos = start_widget.y() + start_widget.height()
        for i, widget in enumerate(self._drag_list):
            if self._orientation == Qt.Orientation.Horizontal:
                start_pos = end_pos + (widget.x() - end_pos) // 2
                mid_pos = widget.x() + (widget.width() // 2)
                end_pos = widget.x() + widget.width()
            else:
                start_pos = end_pos + (widget.y() - end_pos) // 2
                mid_pos = widget.y() + (widget.height() // 2)
                end_pos = widget.y() + widget.height()
            if mouse_pos < mid_pos:
                self._insert_index = i
                self._insert_pos = start_pos
                self.update()
                return
        self._insert_index = len(self._drag_list)
        self._insert_pos = end_pos + margin
        self.update()

    def dragEnterEvent(self, event: Optional[QDragEnterEvent]) -> None:
        """Accept drag events from widgets."""
        assert event is not None
        dragged_item = event.source()
        if not isinstance(dragged_item, QWidget) or isinstance(dragged_item, LayerWidget):
            return
        self._drag_list = self._tabs if isinstance(dragged_item, Tab) else self._widgets
        event.accept()
        self._update_insert_pos(event.position())

    def dragMoveEvent(self, event: Optional[QDragMoveEvent]) -> None:
        """Track where a dragged widget would be inserted."""
        assert event is not None
        self._update_insert_pos(event.position())

    def dragLeaveEvent(self, event: Optional[QDragLeaveEvent]) -> None:
        """Clear the insert marker on drag exit."""
        if self._insert_pos is not None:
            self._insert_pos = None
            self._insert_index = None
            self._drag_list = None
            self.update()

    def dropEvent(self, event: Optional[QDropEvent]) -> None:
        """Insert the dragged widget"""
        assert event is not None
        widget = event.source()
        assert isinstance(widget, QWidget)
        if self._insert_index is not None:
            self.add_widget(widget, self._insert_index)
            self._insert_index = None
            self._insert_pos = None
            self._drag_list = None
            self.update()

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        """Draw the insert position on drag and drop."""
        super().paintEvent(event)
        painter = QPainter(self)
        foreground_color = self.palette().color(self.foregroundRole())
        painter.setPen(foreground_color)
        active_tab = self.active_tab
        if active_tab is not None:
            active_rect = active_tab.geometry()
            if self._orientation == Qt.Orientation.Horizontal:
                if self._at_parent_start:
                    active_rect.setBottom(self.height() - 1)
                    active_rect.setY(active_tab.y() + active_tab.height() + 1)
                else:
                    active_rect.setY(2)
                    active_rect.setBottom(active_tab.y() - 1)
            else:
                if self._at_parent_start:
                    active_rect.setRight(self.width() - 1)
                    active_rect.setX(active_tab.x() + active_tab.width() + 1)
                else:
                    active_rect.setX(1)
                    active_rect.setRight(active_tab.x() - 1)
            painter.fillRect(active_rect, foreground_color)

        if self._insert_pos is not None:
            if self._orientation == Qt.Orientation.Horizontal:
                painter.drawLine(QLine(self._insert_pos, 0, self._insert_pos, self.height()))
            else:
                painter.drawLine(QLine(0, self._insert_pos, self.width(), self._insert_pos))
        painter.end()
