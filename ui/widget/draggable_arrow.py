"""
Provides a widget that can be dragged to resize UI elements.
"""
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtCore import Qt, QPoint, QSize, QRect, pyqtSignal
from ui.util.get_scaled_placement import get_scaled_placement
from ui.util.contrast_color import contrast_color

class DraggableArrow(QWidget):
    dragged = pyqtSignal(QPoint)

    def __init__(self):
        super().__init__()
        self._dragging = False
        self.resizeEvent(None)
        self._mode = 'horizontal'
        self._hidden = False

    def set_horizontal_mode(self):
        if self._mode != 'horizontal':
            self._mode = 'horizontal'
            self.update()

    def set_vertical_mode(self):
        if self._mode != 'vertical':
            self._mode = 'vertical'
            self.update()

    def set_hidden(self, hidden):
        if self._hidden != hidden:
            self._hidden = hidden
            self.update()

    def resizeEvent(self, event):
        minSize = min(self.width(), self.height())
        self._centerBox = get_scaled_placement(QRect(0, 0, self.width(), self.height()), QSize(minSize, minSize // 2))

    def paintEvent(self, event):
        if self._hidden:
            return
        painter = QPainter(self)
        color = Qt.green if self._dragging else contrast_color(self)
        size = 4 if self._dragging else 2
        painter.setPen(QPen(color, size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        center_box = self._centerBox
        if self._mode == 'horizontal':
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

    def mousePressEvent(self, event):
        if self._hidden:
            return
        self._dragging = True
        self.update()

    def mouseMoveEvent(self, event):
        if event.buttons() and self._dragging:
            self.dragged.emit(event.pos() + self.geometry().topLeft())

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging= False
            self.update()
