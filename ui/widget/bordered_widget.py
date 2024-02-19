from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QPoint, QRect, QSize, QMargins
from ui.util.contrast_color import contrastColor

# Simple widget that just draws a black border around its content
class BorderedWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContentsMargins(QMargins(5, 5, 5, 5))

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(contrastColor(self), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        widgetSize = self.size()
        painter.drawLine(QPoint(1, 1), QPoint(0, widgetSize.height() - 1))
        painter.drawLine(QPoint(1, 1), QPoint(widgetSize.width() - 1, 0))
        painter.drawLine(QPoint(widgetSize.width() - 1, 1), QPoint(widgetSize.width() - 1, widgetSize.height() - 1))
        painter.drawLine(QPoint(1, widgetSize.height() - 1), QPoint(widgetSize.width() - 1, widgetSize.height() - 1))
