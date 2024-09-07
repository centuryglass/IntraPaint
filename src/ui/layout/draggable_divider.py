"""
Provides a widget that can be dragged to resize UI elements.
"""
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QSize, QRect, Signal
from PySide6.QtGui import QPainter, QPen, QResizeEvent, QMouseEvent, QPaintEvent, QCursor
from PySide6.QtWidgets import QWidget, QSizePolicy, QBoxLayout, QHBoxLayout, QVBoxLayout, QLayoutItem

from src.util.visual.contrast_color import contrast_color

DIVIDER_SIZE = 4


class DraggableDivider(QWidget):
    """DraggableArrow is a widget that can be dragged along an axis to resize UI elements."""

    dragged = Signal(QPoint)

    def __init__(self, orientation=Qt.Orientation.Horizontal) -> None:
        super().__init__()
        self._dragging = False
        self._mode = orientation
        if orientation == Qt.Orientation.Horizontal:
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._hidden = False
        self._center_box = QRect(0, 0, 0, 0)
        self.resizeEvent(None)
        self._inactive_cursor = QCursor(Qt.CursorShape.OpenHandCursor)
        self._dragging_cursor = QCursor(Qt.CursorShape.ClosedHandCursor)
        self.setCursor(self._inactive_cursor)

    def set_horizontal_mode(self) -> None:
        """Puts the widget in horizontal mode, where it can be dragged left and right."""
        if self._mode != Qt.Orientation.Horizontal:
            self._mode = Qt.Orientation.Horizontal
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
            self.update()

    def set_vertical_mode(self) -> None:
        """Puts the widget in vertical mode, where it can be dragged up and down."""
        if self._mode != Qt.Orientation.Vertical:
            self._mode = Qt.Orientation.Vertical
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.update()

    def set_hidden(self, hidden: bool) -> None:
        """Sets whether the widget should be shown or hidden."""
        if self._hidden != hidden:
            self._hidden = hidden
            self.update()

    def sizeHint(self):
        """Calculate preferred size based on orientation."""
        if self._mode == Qt.Orientation.Horizontal:
            return QSize(DIVIDER_SIZE, DIVIDER_SIZE * 3)
        return QSize(DIVIDER_SIZE * 3, DIVIDER_SIZE)

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Recalculate arrow placement when widget bounds change."""
        layout = self._get_containing_layout()
        if isinstance(layout, QHBoxLayout) and self._mode != Qt.Orientation.Horizontal:
            self.set_horizontal_mode()
        elif isinstance(layout, QVBoxLayout) and self._mode != Qt.Orientation.Vertical:
            self.set_vertical_mode()

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draws the arrow in the chosen orientation."""
        if self._hidden:
            return
        painter = QPainter(self)
        color = contrast_color(self).lighter() if self._dragging else contrast_color(self)
        size = 4 if self._dragging else 2
        painter.setPen(QPen(color, size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap,
                            Qt.PenJoinStyle.BevelJoin))

        if self._mode == Qt.Orientation.Horizontal:
            p1 = QPoint(self.width() // 2, DIVIDER_SIZE)
            p2 = QPoint(self.width() // 2, self.height() - DIVIDER_SIZE)
        else:
            p1 = QPoint(DIVIDER_SIZE, self.height() // 2)
            p2 = QPoint(self.width() - DIVIDER_SIZE, self.height() // 2)
        painter.drawLine(p1, p2)

    def mousePressEvent(self, unused_event: Optional[QMouseEvent]) -> None:
        """Starts dragging the widget when clicked."""
        if self._hidden:
            return
        self._dragging = True
        self.setCursor(self._dragging_cursor)
        self.update()

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Emits the drag position when the mouse moves and the widget is being dragged."""
        if event is None:
            return
        if event.buttons() and self._dragging:
            self.dragged.emit(event.pos() + self.geometry().topLeft())
            layout = self._get_containing_layout()
            assert layout is not None
            index = layout.indexOf(self)
            if index in (0, index == layout.count() - 1):
                return

            def _get_item_widget(idx: int) -> Optional[QWidget | QLayoutItem]:
                item = layout.itemAt(idx)
                assert item is not None
                widget = item.widget()
                return widget if widget is not None else item
            prev_item = _get_item_widget(index - 1)
            next_item = _get_item_widget(index + 1)
            if prev_item is None or next_item is None:
                return
            if self._mode == Qt.Orientation.Horizontal:
                divider_pos = self.x()
                drag_pos = event.pos().x() + self.x()
                prev_min = prev_item.minimumWidth()
                prev_max = prev_item.maximumWidth()
                prev_size = prev_item.width()
                next_min = next_item.minimumWidth()
                next_max = next_item.maximumWidth()
                next_size = next_item.width()
                prev_item_start = self.x() - prev_item.width()
                next_item_end = self.x() + self.width() + next_item.width()
            else:
                divider_pos = self.y()
                drag_pos = event.pos().y() + self.y()
                prev_min = prev_item.minimumWidth()
                prev_max = prev_item.maximumWidth()
                prev_size = prev_item.width()
                next_min = next_item.minimumWidth()
                next_max = next_item.maximumWidth()
                next_size = next_item.width()
                prev_item_start = self.y() - prev_item.height()
                next_item_end = self.y() + self.height() + next_item.height()
            total_stretch = layout.stretch(index - 1) + layout.stretch(index + 1)
            assert total_stretch >= 2
            # Don't continue if trying to resize a widget beyond its limits:
            if ((prev_size == prev_min or next_size == next_max) and drag_pos < divider_pos) \
                    or ((prev_size == prev_max or next_size == next_min) and drag_pos > divider_pos):
                fraction = max(1, prev_size) / max(1, prev_size + next_size)
            else:
                fraction = max(1, (drag_pos - prev_item_start)) / max(1, (next_item_end - prev_item_start))

            prev_item_stretch = max(1, int(total_stretch * fraction))
            next_item_stretch = max(1, total_stretch - prev_item_stretch)
            overflow = (prev_item_stretch + next_item_stretch) - total_stretch
            if overflow > 0:
                if prev_item_stretch > next_item_stretch:
                    prev_item_stretch -= overflow
                else:
                    next_item_stretch -= overflow
            layout.setStretch(index - 1, prev_item_stretch)
            layout.setStretch(index + 1, next_item_stretch)

    def mouseReleaseEvent(self, unused_event: Optional[QMouseEvent]) -> None:
        """Exits the dragging state when the mouse is released. """
        if self._dragging:
            self._dragging = False
            self.setCursor(self._inactive_cursor)
            self.update()

    def _get_containing_layout(self) -> Optional[QBoxLayout]:
        parent = self.parent()
        if parent is None:
            return None
        layout = parent.layout()
        assert isinstance(layout, QBoxLayout) and layout.indexOf(self) != -1, ('DraggableDivider must be'
                                                                               ' within a box layout')
        return layout
