"""
A simple widget that just draws a border around its content.
"""
from typing import Optional
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QPen, QPaintEvent
from PyQt5.QtCore import Qt, QPoint, QMargins
from src.ui.util.contrast_color import contrast_color


class BorderedWidget(QWidget):
    """BorderedWidget draws a 1-pixel border around its content."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the widget, optionally adding it to a parent."""
        super().__init__(parent)
        self.setContentsMargins(QMargins(5, 5, 5, 5))

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        """Draws the widget borders."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(contrast_color(self), 1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        widget_size = self.size()
        painter.drawLine(QPoint(1, 1), QPoint(0, widget_size.height() - 1))
        painter.drawLine(QPoint(1, 1), QPoint(widget_size.width() - 1, 0))
        painter.drawLine(QPoint(widget_size.width() - 1, 1), QPoint(widget_size.width() - 1, widget_size.height() - 1))
        painter.drawLine(QPoint(1, widget_size.height() - 1), QPoint(widget_size.width() - 1, widget_size.height() - 1))
