from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtCore import Qt, QPoint, QRect, QSize

# Simple widget that just draws a black border around its content
class BorderedWidget(QWidget):

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(Qt.black, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        widgetSize = self.size()
        painter.drawLine(QPoint(0, 0), QPoint(0, widgetSize.height()))
        painter.drawLine(QPoint(0, 0), QPoint(widgetSize.width(), 0))
        painter.drawLine(QPoint(widgetSize.width(), 0), QPoint(widgetSize.width(), widgetSize.height()))
        painter.drawLine(QPoint(0, widgetSize.height()), QPoint(widgetSize.width(), widgetSize.height()))
