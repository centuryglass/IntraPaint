"""Extends QGraphicsPixmapItem to add alternate composition modes."""
from typing import Optional

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter, QPixmap, Qt, QImage, QTransform
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from src.ui.graphics_items.composable_item import ComposableItem


class PixmapItem(QGraphicsPixmapItem, ComposableItem):
    """Extends QGraphicsPixmapItem to add alternate composition modes."""

    def __init__(self, pixmap: Optional[QPixmap] = None, parent: Optional[QGraphicsItem] = None) -> None:
        super().__init__()
        if pixmap is not None:
            self.setPixmap(pixmap)
        if parent is not None:
            self.setParentItem(parent)
        self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

    def paint(self,
              painter: Optional[QPainter],
              option: Optional[QStyleOptionGraphicsItem],
              widget: Optional[QWidget] = None) -> None:
        """Paints the pixmap using the item's composition mode."""
        assert painter is not None
        painter.save()
        composite_image, qt_composite_mode = self.get_composited_image()
        if qt_composite_mode is not None:
            painter.setCompositionMode(qt_composite_mode)
            super().paint(painter, option, widget)
        else:
            painter.drawImage(self.pos(), composite_image)
        painter.restore()

    # Base methods extended to update the change timestamp:

    def setTransform(self, matrix: QTransform, combine: bool = False) -> None:
        """Update change timestamp if the item's transformation changes."""
        super().setTransform(matrix, combine)
        self.update_bounds_change_timestamp()

    def setPixmap(self, pixmap: QPixmap) -> None:
        """Update change timestamp if the item's pixmap changes."""
        bounds_changed = pixmap.size() != self.pixmap().size()
        super().setPixmap(pixmap)
        if bounds_changed:
            self.update_bounds_change_timestamp()
        else:
            self.update_change_timestamp()

    def setOpacity(self, opacity: float) -> None:
        """Update change timestamp if the item's opacity changes."""
        super().setOpacity(opacity)
        self.update_change_timestamp()

    def setVisible(self, visible: bool) -> None:
        """Update change timestamp if the item's visibility changes."""
        super().setVisible(visible)
        self.update_change_timestamp()

    def setX(self, x: float) -> None:
        """Update change timestamp if the item's x-position changes."""
        super().setX(x)
        self.update_bounds_change_timestamp()

    def setY(self, y: float) -> None:
        """Update change timestamp if the item's y-position changes."""
        super().setX(y)
        self.update_bounds_change_timestamp()

    def setPos(self, pos: QPointF) -> None:
        """Update change timestamp if the item's position changes."""
        super().setPos(pos)
        self.update_bounds_change_timestamp()

    def setZValue(self, z: float) -> None:
        """Update change timestamp if the item's z-value changes."""
        super().setZValue(z)
        self.update_bounds_change_timestamp()

    def get_composite_source_image(self) -> QImage:
        """Return the item's contents as a composable QImage."""
        image = self.pixmap().toImage()
        if not image.hasAlphaChannel():
            return image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        return image
