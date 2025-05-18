"""Extends QGraphicsPixmapItem to add alternate composition modes."""
from typing import Optional

from PySide6.QtGui import QPainter, QPixmap, Qt, QTransform
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from src.image.composite_mode import CompositeMode
from src.util.visual.geometry_utils import transform_scale


class PixmapItem(QGraphicsPixmapItem):
    """Extends QGraphicsPixmapItem to add alternate composition modes."""

    def __init__(self, pixmap: Optional[QPixmap] = None, parent: Optional[QGraphicsItem] = None) -> None:
        super().__init__()
        if pixmap is not None:
            self.setPixmap(pixmap)
        if parent is not None:
            self.setParentItem(parent)
        self.setTransformationMode(Qt.TransformationMode.FastTransformation)
        self._mode = CompositeMode.NORMAL

    @property
    def composition_mode(self) -> CompositeMode:
        """Access the graphic item composition mode."""
        return self._mode

    @composition_mode.setter
    def composition_mode(self, new_mode: CompositeMode) -> None:
        self._mode = new_mode
        self.update()

    def paint(self,
              painter: Optional[QPainter],
              option: Optional[QStyleOptionGraphicsItem],
              widget: Optional[QWidget] = None) -> None:
        """Paints the pixmap using the item's composition mode."""
        assert painter is not None
        painter.save()
        qt_composite_mode = self._mode.qt_composite_mode()
        if qt_composite_mode is not None:
            painter.setCompositionMode(qt_composite_mode)
        scale = max(*transform_scale(painter.transform()))
        if scale > 16 or ((scale % 1.0) == 0.0):
            self.setTransformationMode(Qt.TransformationMode.FastTransformation)
        else:
            self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        super().paint(painter, option, widget)
        painter.restore()
