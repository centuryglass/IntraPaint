"""Temporary animated line to show in the scene."""
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, QLineF
from PySide6.QtGui import QPainterPath, QPolygonF, QPainter
from PySide6.QtWidgets import QGraphicsScene, QStyleOptionGraphicsItem, QWidget

from src.ui.graphics_items.animated_dash_item import AnimatedDashItem

PEN_WIDTH = 3


class TempDashedLineItem(AnimatedDashItem):
    """Editable path item used to create a polygon."""

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__()
        self._line = QLineF()
        scene.addItem(self)
        self.animated = True

    def set_line(self, line: QLineF) -> None:
        """Updates the drawn line."""
        self.prepareGeometryChange()
        self._line = QLineF(line)
        self.update()

    def _line_polygon(self) -> QPolygonF:
        p1 = self._line.p1()
        p2 = self._line.p2()
        perpendicular = QPointF(self._line.dx(), self._line.dy())
        length = (perpendicular.x() ** 2 + perpendicular.y() ** 2) ** 0.5
        perpendicular /= length
        offset = perpendicular * (PEN_WIDTH / 2)
        return QPolygonF([p1 + offset, p1 - offset, p2 - offset, p2 + offset])

    def boundingRect(self) -> QRectF:
        """Sse the union of all handle bounds as the bounding rect."""
        return self._line_polygon().boundingRect()

    def shape(self) -> QPainterPath:
        """Returns the outline's bounds as a shape."""
        path = QPainterPath()
        path.addPolygon(self._line_polygon())
        return path

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draw animated dotted lines between all handles."""
        if not self._line.isNull():
            assert painter is not None
            painter.save()
            painter.setPen(self.get_pen())
            painter.drawLine(self._line)
            painter.restore()
