"""
A QFrame with a flat border, drawn in the palette's ink color unless a color is set.
"""
from typing import Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QFrame, QWidget

DEFAULT_LINE_WIDTH = 1


class BorderedWidget(QFrame):
    """A QFrame with a flat border, drawn in the palette's ink color unless a color is set.

    The border is a solid line `line_width` pixels wide. It follows the palette's `Shadow` color until `frame_color`
    is set to anything else.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the widget, optionally adding it to a parent."""
        super().__init__(parent)
        self._frame_color: Optional[QColor] = None
        # A Box frame reserves line_width pixels on each side as contents margins. paintEvent draws the border:
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        self.setLineWidth(DEFAULT_LINE_WIDTH)
        self.setAutoFillBackground(True)

    @property
    def default_frame_color(self) -> QColor:
        """Returns the border color used while no other color is set."""
        return self.palette().color(QPalette.ColorRole.Shadow)

    @property
    def frame_color(self) -> QColor:
        """Returns the drawn border color."""
        return QColor(self._frame_color) if self._frame_color is not None else self.default_frame_color

    @frame_color.setter
    def frame_color(self, new_color: QColor | Qt.GlobalColor) -> None:
        """Updates the drawn border color. Setting the default color makes the border follow the palette again."""
        new_color = QColor(new_color)
        if new_color != self.frame_color:
            self._frame_color = None if new_color == self.default_frame_color else new_color
            self.update()

    @property
    def line_width(self) -> int:
        """Returns the line width of the drawn border."""
        return self.lineWidth()

    @line_width.setter
    def line_width(self, new_width: int) -> None:
        """Updates the line width of the drawn border."""
        self.setLineWidth(new_width)

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draws the border as a solid line."""
        line_width = self.lineWidth()
        if line_width <= 0:
            return
        painter = QPainter(self)
        painter.setPen(QPen(self.frame_color, line_width))
        inset = line_width / 2
        painter.drawRect(QRectF(self.rect()).adjusted(inset, inset, -inset, -inset))
        painter.end()
