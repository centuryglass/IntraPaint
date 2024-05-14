"""
Animated widget used to indicate a loading state.
"""
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor
from PyQt5.QtCore import Qt, QRect, QPointF, pyqtProperty, QPropertyAnimation

class LoadingWidget(QWidget):
    """Show an animated loading indicator, with an optional message."""

    def __init__(self, parent=None, message=""):
        """Initializes the widget, optionally with a parent widget and/or initial loading message."""
        super().__init__(parent=parent)
        self._message = message
        self._rotation = 0
        self._anim = QPropertyAnimation(self, b"rotation")
        self._anim.setLoopCount(-1)
        self._anim.setStartValue(0)
        self._anim.setEndValue(359)
        self._anim.setDuration(2000)


    def set_message(self, message):
        """Sets the loading message displayed."""
        self._message = message
        self.update()


    @pyqtProperty(int)
    def rotation(self):
        """Returns the current animation rotation in degrees."""
        return self._rotation


    @rotation.setter
    def rotation(self, rotation):
        """Sets the current animation rotation in degrees."""
        self._rotation = rotation % 360
        self.update()


    def showEvent(self, unused_event):
        """Starts the animation when the widget is shown."""
        self._anim.start()


    def hideEvent(self, unused_event):
        """Stops the animation when the widget is hidden."""
        self._anim.stop()


    def paintEvent(self, unused_event):
        """Draws a circle with optional message text and an animated indicator."""
        painter = QPainter(self)
        ellipse_dim = int(min(self.width(), self.height()) * 0.8)
        paint_bounds = QRect((self.width() // 2) - (ellipse_dim // 2),
                (self.height() // 2 - ellipse_dim // 2),
                ellipse_dim,
                ellipse_dim)

        # draw background circle:
        painter.setPen(QPen(Qt.black, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(QBrush(QColor(0, 0, 0, 200), Qt.SolidPattern))
        painter.drawEllipse(paint_bounds)

        # Write text:
        painter.setPen(QPen(Qt.white, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(QBrush(Qt.white, Qt.SolidPattern))
        painter.drawText(QRect(0, 0, self.width(), self.height()), Qt.AlignCenter, self._message)

        # Draw animated indicator:
        painter.translate(QPointF(self.width() / 2, self.height() / 2))
        painter.rotate(self._rotation)
        painter.drawEllipse(QRect(0, int(-ellipse_dim / 2 + ellipse_dim * 0.05),
                    self.width() // 20, self.height() // 40))
