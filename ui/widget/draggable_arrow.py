from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtCore import Qt, QPoint, QSize, QRect, pyqtSignal
from ui.util.get_scaled_placement import getScaledPlacement
from ui.util.contrast_color import contrastColor

class DraggableArrow(QWidget):
    dragged = pyqtSignal(QPoint)

    def __init__(self):
        super().__init__()
        self._dragging = False
        self.resizeEvent(None)
        self._mode = 'horizontal'
        self._hidden = False

    def setHorizontalMode(self):
        if self._mode != 'horizontal':
            self._mode = 'horizontal'
            self.update()

    def setVerticalMode(self):
        if self._mode != 'vertical':
            self._mode = 'vertical'
            self.update()

    def setHidden(self, hidden):
        if self._hidden != hidden:
            self._hidden = hidden
            self.update()


    def resizeEvent(self, event):
        minSize = min(self.width(), self.height())
        self._centerBox = getScaledPlacement(QRect(0, 0, self.width(), self.height()), QSize(minSize, minSize // 2))

    def paintEvent(self, event):
        if self._hidden:
            return
        painter = QPainter(self)
        color = Qt.green if self._dragging else contrastColor(self)
        size = 4 if self._dragging else 2
        painter.setPen(QPen(color, size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        centerBox = self._centerBox
        if self._mode == 'horizontal':
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
        else:
            xMid = centerBox.x() + (centerBox.width() // 2)
            midTop = QPoint(xMid, centerBox.y())
            midBottom = QPoint(xMid, centerBox.bottom())
            arrowSize = centerBox.height() // 4
            # Draw arrows:
            painter.drawLine(midTop, midBottom)
            painter.drawLine(midTop, midTop + QPoint(arrowSize, arrowSize))
            painter.drawLine(midTop, midTop + QPoint(-arrowSize, arrowSize))
            painter.drawLine(midBottom, midBottom + QPoint(arrowSize, -arrowSize))
            painter.drawLine(midBottom, midBottom + QPoint(-arrowSize, -arrowSize))

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
