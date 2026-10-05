"""Square resize handle drawn on a rectangle's outline at a fixed screen size."""
from typing import Optional

from PySide6.QtCore import QRectF, Qt, QPointF
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from src.ui.graphics_items.transform_handle import HANDLE_SIZE


class AreaResizeHandle(QGraphicsItem):
    """Square resize handle drawn at a fixed screen size, centered on its scene position.

    The handle only draws. It accepts no mouse buttons, so the tool that owns it does its own hit testing.
    """

    def __init__(self, parent: Optional[QGraphicsItem] = None) -> None:
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._rect = QRectF(-HANDLE_SIZE / 2, -HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE)

    def boundingRect(self) -> QRectF:
        """Returns the handle's bounds in screen pixels around its position, including the outline."""
        return self._rect.adjusted(-1.0, -1.0, 1.0, 1.0)

    def move_center(self, scene_point: QPointF) -> None:
        """Centers the handle on a scene point."""
        self.setPos(scene_point)

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draws a black square with a white outline."""
        assert painter is not None
        painter.save()
        painter.fillRect(self._rect, Qt.GlobalColor.black)
        painter.setPen(QPen(Qt.GlobalColor.white, 1.0))
        painter.drawRect(self._rect)
        painter.restore()
