from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtCore import Qt, QPoint, QSize, QRect, pyqtSignal
from ui.util.get_scaled_placement import getScaledPlacement

class DraggableArrow(QWidget):
    dragged = pyqtSignal(QPoint)

    def __init__(self):
        super().__init__()
        self._dragging = False
        self.resizeEvent(None)

    def resizeEvent(self, event):
        minSize = min(self.width(), self.height())
        self._centerBox = getScaledPlacement(QRect(0, 0, self.width(), self.height()), QSize(minSize, minSize // 2))

    def paintEvent(self, event):
        painter = QPainter(self)
        color = Qt.green if self._dragging else Qt.black
        size = 4 if self._dragging else 2
        painter.setPen(QPen(color, size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        centerBox = self._centerBox
        yMid = centerBox.y() + (centerBox.height() // 2)
        midLeft = QPoint(centerBox.x(), yMid)
        midRight = QPoint(centerBox.right(), yMid)
        arrowWidth = centerBox.width() // 4
        # Draw arrows:
        painter.drawLine(midLeft, midRight)
        painter.drawLine(midLeft, centerBox.topLeft() + QPoint(arrowWidth, 0))
        painter.drawLine(midLeft, centerBox.bottomLeft() + QPoint(arrowWidth, 0))
        painter.drawLine(midRight, centerBox.topRight() - QPoint(arrowWidth, 0))
        painter.drawLine(midRight, centerBox.bottomRight() - QPoint(arrowWidth, 0))

    def mousePressEvent(self, event):
        self._dragging = True
        self.update()

    def mouseMoveEvent(self, event):
        if event.buttons() and self._dragging:
            self.dragged.emit(event.pos() + self.geometry().topLeft())

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging= False
            self.update()
