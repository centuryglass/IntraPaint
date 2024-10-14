"""A temporary graphics item that appears above a Layer to indicate that it's locked."""
from typing import Optional

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPainter, QBrush, Qt
from PySide6.QtWidgets import QGraphicsView, QStyleOptionGraphicsItem, QWidget

from src.image.layers.layer import Layer
from src.image.layers.transform_layer import TransformLayer
from src.ui.graphics_items.temp_image_item import TempImageItem
from src.util.shared_constants import PROJECT_DIR

ICON_PATH_LOCKED_LAYER = f'{PROJECT_DIR}/resources/icons/lock_large.svg'


class LayerLockAlertItem(TempImageItem):
    """A temporary graphics item that appears above a Layer to indicate that it's locked."""

    def __init__(self, layer: Layer, view: QGraphicsView) -> None:
        lock_icon = QIcon(ICON_PATH_LOCKED_LAYER)
        self._bounds = layer.bounds
        image_dim = max(round(min(self._bounds.width(), self._bounds.height()) * 0.5), 30)
        pixmap = lock_icon.pixmap(QSize(image_dim, image_dim))
        super().__init__(pixmap, self._bounds, view)
        if isinstance(layer, TransformLayer):
            self.setTransform(layer.transform)

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draws the text over a rounded rectangle."""
        assert painter is not None
        painter.save()
        painter.setOpacity(self.animation_opacity)
        brush = QBrush(Qt.GlobalColor.black)
        brush.setStyle(Qt.BrushStyle.Dense2Pattern)
        painter.fillRect(self._bounds, brush)
        painter.restore()
        super().paint(painter, unused_option, unused_widget)
