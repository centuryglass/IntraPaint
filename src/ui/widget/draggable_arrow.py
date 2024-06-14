"""
Provides a widget that can be dragged to resize UI elements.
"""
from typing import Optional
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QPen, QColor, QResizeEvent, QMouseEvent, QPaintEvent
from PyQt5.QtCore import Qt, QPoint, QSize, QRect, pyqtSignal
from src.util.geometry_utils import get_scaled_placement
from src.util.contrast_color import contrast_color


class DraggableArrow(QWidget):
    """DraggableArrow is a widget that can be dragged along an axis to resize UI elements."""

    dragged = pyqtSignal(QPoint)

    def __init__(self) -> None:
        super().__init__()
        self._dragging = False
        self._mode = Qt.Orientation.Horizontal
        self._hidden = False
        self._center_box = QRect(0, 0, 0, 0)
        self.resizeEvent(None)

    def set_horizontal_mode(self) -> None:
        """Puts the widget in horizontal mode, where it can be dragged left and right."""
        if self._mode != Qt.Orientation.Horizontal:
            self._mode = Qt.Orientation.Horizontal
            self.update()

    def set_vertical_mode(self) -> None:
        """Puts the widget in vertical mode, where it can be dragged up and down."""
        if self._mode != Qt.Orientation.Vertical:
            self._mode = Qt.Orientation.Vertical
            self.update()

    def set_hidden(self, hidden: bool) -> None:
        """Sets whether the widget should be shown or hidden."""
        if self._hidden != hidden:
            self._hidden = hidden
            self.update()

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Recalculate arrow placement when widget bounds change."""
        min_size = min(self.width(), self.height())
        self._center_box = get_scaled_placement(QRect(0, 0, self.width(), self.height()),
                                                QSize(min_size, min_size // 2))

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draws the arrow in the chosen orientation."""
        if self._hidden:
            return
        painter = QPainter(self)
        color: Qt.GlobalColor | QColor = Qt.GlobalColor.green if self._dragging else contrast_color(self)
        size = 4 if self._dragging else 2
        painter.setPen(QPen(color, size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        center_box = self._center_box
        if self._mode == Qt.Orientation.Horizontal:
            y_mid = center_box.y() + (center_box.height() // 2)
            mid_left = QPoint(center_box.x(), y_mid)
            mid_right = QPoint(center_box.right(), y_mid)
            arrow_width = center_box.width() // 4
            # Draw arrows:
            painter.drawLine(mid_left, mid_right)
            painter.drawLine(mid_left, center_box.topLeft() + QPoint(arrow_width, 0))
            painter.drawLine(mid_left, center_box.bottomLeft() + QPoint(arrow_width, 0))
            painter.drawLine(mid_right, center_box.topRight() - QPoint(arrow_width, 0))
            painter.drawLine(mid_right, center_box.bottomRight() - QPoint(arrow_width, 0))
        else:
            x_mid = center_box.x() + (center_box.width() // 2)
            mid_top = QPoint(x_mid, center_box.y())
            mid_bottom = QPoint(x_mid, center_box.bottom())
            arrow_size = center_box.height() // 4
            # Draw arrows:
            painter.drawLine(mid_top, mid_bottom)
            painter.drawLine(mid_top, mid_top + QPoint(arrow_size, arrow_size))
            painter.drawLine(mid_top, mid_top + QPoint(-arrow_size, arrow_size))
            painter.drawLine(mid_bottom, mid_bottom + QPoint(arrow_size, -arrow_size))
            painter.drawLine(mid_bottom, mid_bottom + QPoint(-arrow_size, -arrow_size))

    def mousePressEvent(self, unused_event: Optional[QMouseEvent]) -> None:
        """Starts dragging the widget when clicked."""
        if self._hidden:
            return
        self._dragging = True
        self.update()

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Emits the drag position when the mouse moves and the widget is being dragged."""
        if event is None:
            return
        if event.buttons() and self._dragging:
            self.dragged.emit(event.pos() + self.geometry().topLeft())

    def mouseReleaseEvent(self, unused_event: Optional[QMouseEvent]) -> None:
        """Exits the dragging state when the mouse is released. """
        if self._dragging:
            self._dragging = False
            self.update()
