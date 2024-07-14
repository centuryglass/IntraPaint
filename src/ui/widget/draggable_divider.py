"""
Provides a widget that can be dragged to resize UI elements.
"""
from typing import Optional, Tuple
from PyQt6.QtWidgets import QWidget, QSizePolicy, QBoxLayout, QHBoxLayout, QVBoxLayout
from PyQt6.QtGui import QPainter, QPen, QColor, QResizeEvent, QMouseEvent, QPaintEvent, QCursor
from PyQt6.QtCore import Qt, QPoint, QSize, QRect, pyqtSignal
from src.util.geometry_utils import get_scaled_placement
from src.util.contrast_color import contrast_color

DIVIDER_SIZE = 8


class DraggableDivider(QWidget):
    """DraggableArrow is a widget that can be dragged along an axis to resize UI elements."""

    dragged = pyqtSignal(QPoint)

    def __init__(self) -> None:
        super().__init__()
        self._dragging = False
        self._mode = Qt.Orientation.Horizontal
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
            self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Expanding)
            self.update()

    def set_vertical_mode(self) -> None:
        """Puts the widget in vertical mode, where it can be dragged up and down."""
        if self._mode != Qt.Orientation.Vertical:
            self._mode = Qt.Orientation.Vertical
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
            self.update()

    def set_hidden(self, hidden: bool) -> None:
        """Sets whether the widget should be shown or hidden."""
        if self._hidden != hidden:
            self._hidden = hidden
            self.update()

    def sizeHint(self):
        """Calculate preferred size based on orientation and parent size."""
        parent = self.parent()
        assert parent is not None
        parent_size = parent.size()
        if self._mode == Qt.Orientation.Horizontal:
            return QSize(DIVIDER_SIZE, parent_size.height() - DIVIDER_SIZE)
        return QSize(parent_size.width() - DIVIDER_SIZE, DIVIDER_SIZE)

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
            index = layout.indexOf(self)
            if index == 0 or index == layout.count() - 1:
                return
            prev_item = layout.itemAt(index - 1).widget()
            next_item = layout.itemAt(index + 1).widget()
            if prev_item is None or next_item is None:
                return
            if self._mode == Qt.Orientation.Horizontal:
                prev_item_start = self.x() - prev_item.width()
                next_item_end = self.x() + self.width() + next_item.width()
                drag_pos = event.pos().x() + self.x()
            else:
                prev_item_start = self.y() - prev_item.height()
                next_item_end = self.y() + self.height() + next_item.height()
                drag_pos = event.pos().y() + self.y()
            total_stretch = layout.stretch(index - 1) + layout.stretch(index + 1)
            fraction = max(1, (drag_pos - prev_item_start)) / max(1, (next_item_end - prev_item_start))
            stretch1 = max(1, int(total_stretch * fraction))
            stretch2 = total_stretch - stretch1
            layout.setStretch(index - 1, stretch1)
            layout.setStretch(index + 1, stretch2)

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

