"""Fills in all bounds except an inner rectangular region with a solid color."""
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPoint, QRect
from PySide6.QtGui import QPainter, QPainterPath, QColor
from PySide6.QtWidgets import QWidget, QGraphicsItem, QGraphicsScene, QStyleOptionGraphicsItem

from src.ui.widget.image_graphics_view import ImageGraphicsView


class Border(QGraphicsItem):
    """Fills in all bounds except an inner rectangular region with a solid color.

    Useful for dynamically cropping scene content to highlight an area.
    """

    def __init__(self,
                 scene: QGraphicsScene,
                 view: ImageGraphicsView,
                 parent: Optional[QGraphicsItem] = None):
        super().__init__(parent)
        self._rect = QRectF()
        self._view = view
        self._color = QColor(Qt.GlobalColor.black)
        scene.addItem(self)

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draws the outline within the scene."""
        assert painter is not None
        bounds = self._view.mapToScene(QRect(QPoint(), self._view.size())).boundingRect().adjusted(-9999, -9999, 9999,
                                                                                                   9999)
        if self._rect.isEmpty():
            painter.fillRect(bounds, self._color)
            return
        height = bounds.height()
        width = bounds.width()
        window_right = self._rect.x() + self._rect.width()
        window_bottom = self._rect.y() + self._rect.height()
        left = QRectF(bounds.x(), bounds.y(), self._rect.x() - bounds.x(), height)
        right = QRectF(self._rect.x() + self._rect.width(), bounds.y(), width - window_right, height)
        top = QRectF(self._rect.x(), bounds.y(), self._rect.width(), self._rect.y() - bounds.y())
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
        bounds = self._view.mapToScene(QRect(QPoint(), self._view.size())).boundingRect().adjusted(-9999, -9999, 9999,
                                                                                                   9999)
        return bounds

    def shape(self) -> QPainterPath:
        """Returns the outline's bounds as a shape."""
        path = QPainterPath()
        path.addRect(QRectF(self.boundingRect()))
        return path
