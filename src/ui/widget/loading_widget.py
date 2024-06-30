"""
Animated widget used to indicate a loading state.
"""
from typing import Optional
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QShowEvent, QHideEvent, QPaintEvent
from PyQt5.QtCore import Qt, QRect, QPointF, pyqtProperty, QPropertyAnimation


class LoadingWidget(QWidget):
    """Show an animated loading indicator, with an optional message."""

    def __init__(self, parent: Optional[QWidget] = None, message: str = "") -> None:
        """Initializes the widget, optionally with a parent widget and/or initial loading message."""
        super().__init__(parent=parent)
        self._message = message
        self._rotation = 0
        self._anim = QPropertyAnimation(self, b"rotation")
        self._anim.setLoopCount(-1)
        self._anim.setStartValue(0)
        self._anim.setEndValue(359)
        self._anim.setDuration(2000)

    @property
    def paused(self) -> bool:
        """Whether the loading animation is currently paused."""
        return self._anim.state() == QPropertyAnimation.Paused

    @paused.setter
    def paused(self, should_pause: bool) -> None:
        if should_pause == self.paused:
            return
        if should_pause:
            self._anim.pause()
        else:
            self._anim.resume()

    def pause_animation(self) -> None:
        """Pauses animation and clears the message. Setting a new message will resume the animation."""
        self._message = ''
        self._anim.pause()
        self.update()

    @property
    def visible(self) -> bool:
        """Exposes isVisible() as a property."""
        return self.isVisible()

    @property
    def message(self) -> str:
        """Returns the current loading message."""
        return self._message

    @message.setter
    def message(self, message: str) -> None:
        """Sets the loading message displayed."""
        self._message = message
        self.paused = False
        self.update()

    @pyqtProperty(int)
    def rotation(self) -> int:
        """Returns the current animation rotation in degrees."""
        return self._rotation

    @rotation.setter
    def rotation(self, rotation: int) -> None:
        """Sets the current animation rotation in degrees."""
        self._rotation = rotation % 360
        self.update()

    def showEvent(self, unused_event: Optional[QShowEvent]) -> None:
        """Starts the animation when the widget is shown."""
        self._anim.start()

    def hideEvent(self, unused_event: Optional[QHideEvent]) -> None:
        """Stops the animation when the widget is hidden."""
        self._anim.stop()

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draws a circle with optional message text and an animated indicator."""
        painter = QPainter(self)
        ellipse_dim = int(min(self.width(), self.height()) * 0.8)
        paint_bounds = QRect((self.width() // 2) - (ellipse_dim // 2),
                             (self.height() // 2 - ellipse_dim // 2),
                             ellipse_dim,
                             ellipse_dim)

        # draw background circle:
        painter.setPen(QPen(Qt.GlobalColor.black, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(QBrush(QColor(0, 0, 0, 200), Qt.BrushStyle.SolidPattern))
        painter.drawEllipse(paint_bounds)

        # Write text:
        painter.setPen(QPen(Qt.GlobalColor.white, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(QBrush(Qt.GlobalColor.white, Qt.BrushStyle.SolidPattern))
        painter.drawText(QRect(0, 0, self.width(), self.height()), Qt.AlignmentFlag.AlignCenter, self._message)

        # Draw animated indicator:
        painter.translate(QPointF(self.width() / 2, self.height() / 2))
        painter.rotate(self._rotation)
        painter.drawEllipse(QRect(0, int(-ellipse_dim / 2 + ellipse_dim * 0.05),
                                  self.width() // 20, self.height() // 40))
        painter.end()
