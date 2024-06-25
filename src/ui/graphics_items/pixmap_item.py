"""Extends QGraphicsPixmapItem to add alternate composition modes."""
from typing import Optional

from PyQt5.QtGui import QPainter, QPixmap
from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsItem, QStyleOptionGraphicsItem, QWidget


class PixmapItem(QGraphicsPixmapItem):
    """Extends QGraphicsPixmapItem to add alternate composition modes."""

    def __init__(self, pixmap: Optional[QPixmap] = None, parent: Optional[QGraphicsItem] = None) -> None:
        if pixmap is None:
            super().__init__(parent)
        else:
            super().__init__(pixmap, parent)
        self._mode = QPainter.CompositionMode.CompositionMode_SourceOver

    @property
    def composition_mode(self) -> QPainter.CompositionMode:
        """Access the painting mode used to render the tile into a QGraphicsScene."""
        return self._mode

    @composition_mode.setter
    def composition_mode(self, new_mode: QPainter.CompositionMode) -> None:
        if new_mode != self._mode:
            self._mode = new_mode
            self.update()

    def paint(self,
              painter: Optional[QPainter],
              option: Optional[QStyleOptionGraphicsItem],
              widget: Optional[QWidget] = None) -> None:
        """Paints the pixmap using the item's composition mode.."""
        painter.save()
        painter.setCompositionMode(self._mode)
        super().paint(painter, option, widget)
        painter.restore()
