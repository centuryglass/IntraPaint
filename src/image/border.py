"""Fills in all bounds except an inner rectangular region with a solid color."""
from typing import Optional

from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QPainterPath, QColor
from PyQt5.QtWidgets import QWidget, QGraphicsItem, QGraphicsView, QGraphicsScene, QStyleOptionGraphicsItem


class Border(QGraphicsItem):
    """Fills in all bounds except an inner rectangular region with a solid color.

    Useful for dynamically cropping scene content to highlight an area.
    """

    def __init__(self,
                 scene: QGraphicsScene,
                 view: QGraphicsView,
                 parent: Optional[QGraphicsItem] = None):
        super().__init__(parent)
        self._rect = QRectF()
        self._view = view
        self._color = QColor(Qt.black)
        scene.addItem(self)

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draws the outline within the scene."""
        height = self._view.scene().height()
        width = self._view.scene().width()
        window_right = self._rect.x() + self._rect.width()
        window_bottom = self._rect.y() + self._rect.height()
        left = QRectF(0.0, 0.0, self._rect.x(), height)
        right = QRectF(self._rect.x() + self._rect.width(), 0.0, width - window_right, height)
        top = QRectF(self._rect.x(), 0.0, self._rect.width(), self._rect.y())
        bottom = QRectF(self._rect.x(), window_bottom, self._rect.width(), height - window_bottom)
        for border_rect in (left, right, top, bottom):
            painter.fillRect(border_rect, self._color)

    @property
    def color(self) -> QColor:
        """Returns the fill color for the area outside the window."""
        return self._color

    @color.setter
    def color(self, new_color: QColor | Qt.GlobalColor) -> None:
        """Sets the fill color for the area outside the window."""
        self._color = QColor(new_color)
        if self.isVisible():
            self.update()

    @property
    def windowed_area(self) -> QRectF:
        """Returns the outlined area in the scene."""
        return self._rect

    @windowed_area.setter
    def windowed_area(self, new_region) -> None:
        """Updates the outlined area in the scene."""
        self.prepareGeometryChange()
        self._rect = new_region

    def boundingRect(self) -> QRectF:
        """Returns the rectangle within the scene containing all pixels drawn by the outline."""
        return QRectF(self._view.contentsRect())

    def shape(self) -> QPainterPath:
        """Returns the outline's bounds as a shape."""
        path = QPainterPath()
        path.addRect(QRectF(self.boundingRect()))
        return path

