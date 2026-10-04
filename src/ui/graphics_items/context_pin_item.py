"""Crosshair marker drawn over a context pin."""
from typing import Optional

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

# Marker size in screen pixels, unaffected by the view scale:
MARKER_RADIUS = 6
MARKER_GAP = 2
OUTER_LINE_WIDTH = 3
INNER_LINE_WIDTH = 1


class ContextPinItem(QGraphicsItem):
    """Draws a fixed-size crosshair centered on one image pixel, at every view scale."""

    def __init__(self, pin: QPoint) -> None:
        super().__init__()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setPos(QPointF(pin) + QPointF(0.5, 0.5))

    def boundingRect(self) -> QRectF:
        """Returns the marker bounds in screen pixels around the pin."""
        extent = MARKER_RADIUS + OUTER_LINE_WIDTH
        return QRectF(-extent, -extent, extent * 2, extent * 2)

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draws a light crosshair over a dark outline, so it shows on any image content."""
        assert painter is not None
        painter.save()
        for color, width in ((QColor(Qt.GlobalColor.black), OUTER_LINE_WIDTH),
                             (QColor(Qt.GlobalColor.white), INNER_LINE_WIDTH)):
            pen = QPen(color, width)
            pen.setCosmetic(True)
            painter.setPen(pen)
            for sign in (-1, 1):
                painter.drawLine(QPointF(sign * MARKER_GAP, 0), QPointF(sign * MARKER_RADIUS, 0))
                painter.drawLine(QPointF(0, sign * MARKER_GAP), QPointF(0, sign * MARKER_RADIUS))
        painter.restore()
