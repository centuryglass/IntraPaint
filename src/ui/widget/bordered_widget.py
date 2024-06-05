"""
A simple widget that just draws a border around its content.
"""
from typing import Optional
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen, QPaintEvent
from PyQt5.QtCore import Qt, QPoint, QRect, QMargins
from src.ui.util.contrast_color import contrast_color

DEFAULT_MARGIN = 2
DEFAULT_LINE_MARGIN = 1
DEFAULT_LINE_WIDTH = 1


class BorderedWidget(QWidget):
    """BorderedWidget draws a 1-pixel border around its content."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the widget, optionally adding it to a parent."""
        super().__init__(parent)
        self._color = contrast_color(self)
        self._contents_margin = DEFAULT_MARGIN
        self._line_margin = DEFAULT_LINE_MARGIN
        self._line_width = DEFAULT_LINE_WIDTH
        self.contents_margin = self._contents_margin

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        """Draws the widget borders."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(self._color, self._line_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        border = QRect(QPoint(0, 0), self.size()).adjusted(self._line_margin, self._line_margin, -self._line_margin,
                                                           -self._line_margin)
        painter.drawRect(border)

    @property
    def color(self) -> QColor:
        """Returns the drawn border color."""
        return self._color

    @color.setter
    def color(self, new_color: QColor) -> None:
        """Updates the drawn border color."""
        if new_color != self._color:
            self._color = new_color
            self.update()

    @property
    def contents_margin(self) -> int:
        """Returns the contents margin (equal on all sides)."""
        return self._contents_margin

    @contents_margin.setter
    def contents_margin(self, new_margin: int) -> None:
        """Updates the contents margin (equal on all sides)."""
        self._contents_margin = new_margin
        self.setContentsMargins(QMargins(new_margin, new_margin, new_margin, new_margin))
        self.update()

    @property
    def line_margin(self) -> int:
        """Returns the margin around the border line (equal on all sides)."""
        return self._line_margin

    @line_margin.setter
    def line_margin(self, new_margin: int) -> None:
        """Updates the margin around the border line (equal on all sides)."""
        self._line_margin = new_margin
        self.update()

    @property
    def line_width(self) -> int:
        """Returns the line width of the drawn border."""
        return self._line_width

    @line_width.setter
    def line_width(self, new_width: int) -> None:
        """Updates the line width of the drawn border."""
        self._line_width = new_width
