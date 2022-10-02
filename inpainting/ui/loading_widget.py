from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor
from PyQt5.QtCore import Qt, QMargins, QRect, QPointF, pyqtProperty, QPropertyAnimation

class LoadingWidget(QWidget):
    """Show an animated loading indicator, with an optional message."""
    def __init__(self, parent=None, message=""):
        super().__init__(parent=parent)
        self._message = message
        self._rotation = 0
        self._anim = QPropertyAnimation(self, b"rotation")
        self._anim.setLoopCount(-1)
        self._anim.setStartValue(0)
        self._anim.setEndValue(359)
        self._anim.setDuration(2000)

    def setMessage(self, message):
        self._message = message
        self.update()

    @pyqtProperty(int)
    def rotation(self):
        return self._rotation
    @rotation.setter
    def rotation(self, rotation):
        self._rotation = rotation % 360
        self.update()

    def showEvent(self, event):
        self._anim.start()

    def hideEvent(self, event):
        self._anim.stop()

    def paintEvent(self, event):
        painter = QPainter(self)
        ellipseDim = int(min(self.width(), self.height()) * 0.8)
        paintBounds = QRect((self.width() // 2) - (ellipseDim // 2),
                (self.height() // 2 - ellipseDim // 2),
                ellipseDim,
                ellipseDim)

        # draw background circle:
        painter.setPen(QPen(Qt.black, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(QBrush(QColor(0, 0, 0, 200), Qt.SolidPattern))
        painter.drawEllipse(paintBounds)

        # Write text:
        painter.setPen(QPen(Qt.white, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(QBrush(Qt.white, Qt.SolidPattern))
        painter.drawText(self.width() // 2 - 20, self.height() // 2, "Loading...")

        # Draw animated indicator:
        painter.translate(QPointF(self.width() / 2, self.height() / 2))
        painter.rotate(self._rotation)
        painter.drawEllipse(QRect(0, int(-ellipseDim / 2 + ellipseDim * 0.05),
                    self.width() // 20, self.height() // 40))
