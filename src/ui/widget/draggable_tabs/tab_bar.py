"""Widget bar that accepts draggable tabs."""
from typing import Optional, List

from PyQt6.QtCore import pyqtSignal, Qt, QPointF, QRect, QLine, QSize
from PyQt6.QtGui import QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QDropEvent, QPaintEvent, QPainter
from PyQt6.QtWidgets import QWidget, QBoxLayout, QHBoxLayout, QVBoxLayout, QToolButton, QSizePolicy, QFrame

from src.ui.panel.layer_ui.layer_widget import LayerWidget
from src.ui.widget.bordered_widget import BorderedWidget
from src.ui.widget.draggable_tabs.tab import Tab
from src.ui.widget.label import Label
from src.util.shared_constants import MAX_WIDGET_SIZE

BASE_BAR_SIZE = 10


class TabBar(BorderedWidget):
    """Widget bar that can accept dragged tabs."""

    active_tab_content_replaced = pyqtSignal(QWidget)
    tab_clicked = pyqtSignal(QWidget)
    max_size_changed = pyqtSignal(QSize)
    toggled = pyqtSignal(bool)

    def __init__(self, orientation: Qt.Orientation, at_parent_start: bool) -> None:
        super().__init__()
        self._orientation = orientation
        self._at_parent_start = at_parent_start
        self._active_tab: Optional[Tab] = None
        self._widgets: List[QWidget] = []
        self._insert_pos: Optional[int] = None
        self._insert_index: Optional[int] = None
        self._layout: QBoxLayout = QHBoxLayout(self) if orientation == Qt.Orientation.Horizontal else QVBoxLayout(self)
        self._toggle_button = QToolButton(checkable=True, checked=True)
        self._toggle_button.setStyleSheet('QToolButton { border: none; }')
        self._toggle_button.toggled.connect(self._toggle_button_slot)
        self._bar_size = BASE_BAR_SIZE

        self._toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._toggle_button.setChecked(False)
        self._layout.addWidget(self._toggle_button)
        self._toggle_button.setVisible(False)
        self._toggle_button.setEnabled(False)
        self.setAcceptDrops(True)
        self._apply_orientation()

    @property
    def is_open(self) -> bool:
        """Return true if tab content is open (or would be open if the tab is non-empty)."""
        return self._toggle_button.isChecked()

    @is_open.setter
    def is_open(self, is_open: bool) -> None:
        if self._toggle_button.isChecked() != is_open:
            self._toggle_button.toggle()

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Switch between vertical and horizontal orientation."""
        if self._orientation != orientation:
            self._orientation = orientation
            self._update_bar_size()
            self._apply_orientation()

    def add_widget(self, widget: QWidget, index: int) -> None:
        """Add a widget to the bar."""
        assert widget not in self._widgets
        last_parent = widget.parent()
        if isinstance(last_parent, TabBar):
            last_parent.remove_widget(widget)
        if index < 0:
            index = len(self._widgets)
        self._widgets.insert(index, widget)
        if len(self._widgets) == 1:
            if self._layout.count() == 0:
                self._layout.addWidget(self._toggle_button)
            self._toggle_button.setEnabled(True)
            self._toggle_button.setVisible(True)
        self._layout.insertWidget(index + 1, widget)
        self._apply_widget_orientation(widget)
        self._update_bar_size()
        if isinstance(widget, Tab):
            widget.clicked.connect(self._tab_clicked_slot)
            widget.tab_content_replaced.connect(self._tab_widget_change_slot)
            if self._active_tab is None:
                self._active_tab = widget
                self.tab_clicked.emit(widget)
                self.is_open = True
                self.update()

    def remove_widget(self, widget: QWidget) -> None:
        """Remove a widget from the bar."""
        assert widget in self._widgets
        if isinstance(widget, Tab):
            widget.clicked.disconnect(self._tab_clicked_slot)
            widget.tab_content_replaced.disconnect(self._tab_widget_change_slot)
        self._widgets.remove(widget)
        self._layout.removeWidget(widget)
        widget.setParent(None)
        self._update_bar_size()
        if widget == self._active_tab:
            first_tab = None
            for other_widget in self._widgets:
                if isinstance(other_widget, Tab):
                    first_tab = other_widget
                    break
            self._active_tab = first_tab
            self.tab_clicked.emit(first_tab)
            if self.is_open:
                self.is_open = False
        if len(self._widgets) == 0:
            self._toggle_button.setEnabled(False)
            self._toggle_button.setVisible(False)
        self.update()

    def _update_toggle_arrow(self, checked: bool):
        if self._orientation == Qt.Orientation.Horizontal:
            open_arrow = Qt.ArrowType.UpArrow if self._at_parent_start else Qt.ArrowType.DownArrow
            closed_arrow = Qt.ArrowType.RightArrow
        else:
            open_arrow = Qt.ArrowType.LeftArrow if self._at_parent_start else Qt.ArrowType.RightArrow
            closed_arrow = Qt.ArrowType.DownArrow
        self._toggle_button.setArrowType(open_arrow if checked else closed_arrow)

    def _toggle_button_slot(self) -> None:
        checked = self._toggle_button.isChecked()
        self._update_toggle_arrow(checked)
        self.toggled.emit(checked)

    def _tab_clicked_slot(self, tab: QWidget) -> None:
        assert isinstance(tab, Tab)
        if self._active_tab != tab:
            self._active_tab = tab
            self.tab_clicked.emit(tab)
            self.update()

    def _tab_widget_change_slot(self, tab: QWidget, tab_widget: QWidget) -> None:
        if self._active_tab == tab:
            self.active_tab_content_replaced.emit(tab_widget)

    def _alignment(self) -> Qt.AlignmentFlag:
        if self._orientation == Qt.Orientation.Horizontal:
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        else:  # Vertical:
            return Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter

    def _size_policy(self, widget: QWidget) -> QSizePolicy:
        long_side_policy = QSizePolicy.Policy.Expanding if widget == self else QSizePolicy.Policy.Preferred
        if self._orientation == Qt.Orientation.Horizontal:
            return QSizePolicy(long_side_policy, QSizePolicy.Policy.Fixed)
        else:  # Vertical:
            return QSizePolicy(QSizePolicy.Policy.Fixed, long_side_policy)

    def _update_bar_size(self) -> None:
        bar_size = BASE_BAR_SIZE
        margins = self.contentsMargins()
        for widget in self._widgets:
            if not isinstance(widget, Label):
                return
            size_hint = widget.sizeHint()
            bar_size = max(bar_size, int(1.5 * min(size_hint.width() + margins.left() + margins.right(),
                                         size_hint.height() + margins.top() + margins.bottom())))
        if bar_size != self._bar_size:
            self._bar_size = bar_size
            self._apply_orientation()

    def _max_width(self) -> int:
        return MAX_WIDGET_SIZE if self._orientation == Qt.Orientation.Horizontal else self._bar_size

    def _max_height(self) -> int:
        return self._bar_size if self._orientation == Qt.Orientation.Horizontal else MAX_WIDGET_SIZE

    def _apply_widget_orientation(self, widget: QWidget) -> None:
        if hasattr(widget, 'setAlignment'):
            widget.setAlignment(self._alignment())
        if hasattr(widget, 'setOrientation'):
            widget.setOrientation(self._orientation)
        if hasattr(widget, 'set_orientation'):
            widget.set_orientation(self._orientation)
        widget.setSizePolicy(self._size_policy(widget))

    def _apply_orientation(self) -> None:
        layout_class = QHBoxLayout if self._orientation == Qt.Orientation.Horizontal else QVBoxLayout
        if self._orientation == Qt.Orientation.Horizontal:
            self.setMinimumHeight(self._bar_size)
        else:
            self.setMinimumWidth(self._bar_size)

        if not isinstance(self._orientation, layout_class):
            while self._layout.count() > 0:
                self._layout.takeAt(0)
            temp_widget = QWidget()
            temp_widget.setLayout(self._layout)
            self._layout = layout_class(self)
            self._layout.addWidget(self._toggle_button)
            for widget in self._widgets:
                self._layout.addWidget(widget)
        self._apply_widget_orientation(self)
        self._apply_widget_orientation(self._toggle_button)
        self._layout.setAlignment(self._alignment())
        for widget in self._widgets:
            self._apply_widget_orientation(widget)
        self._update_toggle_arrow(self._toggle_button.isChecked())
        max_size = QSize(self._max_width(), self._max_height())
        if max_size != self.maximumSize():
            self.setMaximumSize(max_size)
            self.max_size_changed.emit(max_size)
        # Update frame based on whether the bar is empty:
        self.setLineWidth(4)
        if len(self._widgets) > 0:
            self.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Plain)
        elif self.width() > self.height():
            self.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Plain)
        else:
            self.setFrameStyle(QFrame.Shape.VLine | QFrame.Shadow.Plain)

    def _update_insert_pos(self, point: QPointF):
        if len(self._widgets) == 0:
            if self._insert_index != 0:
                self._insert_index = 0
                self._insert_pos = 10
                self.update()
            return
        mouse_pos = int(point.x() if self._orientation == Qt.Orientation.Horizontal else point.y())
        for i, widget in enumerate(self._widgets):
            if self._orientation == Qt.Orientation.Horizontal:
                start_pos = widget.x() - (self._layout.contentsMargins().right())
                mid_pos = widget.x() + (widget.width() // 2)
            else:
                start_pos = widget.y() - (self._layout.contentsMargins().bottom())
                mid_pos = widget.y() + (widget.height() // 2)
            if mouse_pos < mid_pos:
                self._insert_index = i
                self._insert_pos = start_pos
                self.update()
                return
        self._insert_index = len(self._widgets)
        if self._orientation == Qt.Orientation.Horizontal:
            self._insert_pos = self._widgets[-1].geometry().right() + self._layout.contentsMargins().right()
        else:
            self._insert_pos = self._widgets[-1].geometry().bottom() + self._layout.contentsMargins().bottom()
        self.update()

    def dragEnterEvent(self, event: Optional[QDragEnterEvent]) -> None:
        """Accept drag events from widgets."""
        assert event is not None
        dragged_item = event.source()
        if not isinstance(dragged_item, QWidget) or isinstance(dragged_item, LayerWidget) \
                or dragged_item in self._widgets:
            return
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
            self.update()

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        """Draw the insert position on drag and drop."""
        super().paintEvent(event)
        painter = QPainter(self)
        foreground_color = self.palette().color(self.foregroundRole())
        painter.setPen(foreground_color)
        for widget in self._widgets:
            if not isinstance(widget, Tab):
                continue
            box = widget.geometry()
            box.adjust(-1, -1, 1, 1)
            if self._orientation == Qt.Orientation.Horizontal:
                if self._at_parent_start:
                    edge_rect = QRect(box.x(), 0, box.width(), box.top() + 1)
                    box.setTop(2)
                else:
                    edge_rect = QRect(box.x(), box.bottom(), box.width(), self.height() - box.bottom() - 1)
                    box.setBottom(self.height() -2)
            else:
                if self._at_parent_start:
                    edge_rect = QRect(0, box.y(), box.x() - 1, box.height())
                    box.setLeft(2)
                else:
                    edge_rect = QRect(box.right() - 1, box.y(), self.width() - box.right() - 1,  box.height())
                    box.setRight(self.width() - 2)
            painter.fillRect(edge_rect, foreground_color if widget == self._active_tab else Qt.GlobalColor.gray)
            painter.drawRect(box)

        if self._insert_pos is not None:
            if self._orientation == Qt.Orientation.Horizontal:
                painter.drawLine(QLine(self._insert_pos, 0, self._insert_pos, self.height()))
            else:
                painter.drawLine(QLine(0, self._insert_pos, self.width(), self._insert_pos))
        painter.end()

