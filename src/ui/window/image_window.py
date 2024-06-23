"""Shows the edited image in its own window."""
from typing import Optional

from PyQt5.QtCore import QPoint, QRect
from PyQt5.QtGui import QPaintEvent, QPainter
from PyQt5.QtWidgets import QWidget

from src.image.layer_stack import LayerStack
from src.util.geometry_utils import get_scaled_placement


class ImageWindow(QWidget):
    """Shows the edited image in its own window."""

    def __init__(self, layer_stack: LayerStack) -> None:
        super().__init__()
        self._layer_stack = layer_stack
        self._pixmap = layer_stack.pixmap()
        self._layer_stack.visible_content_changed.connect(self._pixmap_change_slot)

    def _pixmap_change_slot(self) -> None:
        last = self._pixmap
        self._pixmap = self._layer_stack.pixmap()
        self.update()

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        """Draw the image, scaling to preserve aspect ratio."""
        painter = QPainter(self)
        image_bounds = get_scaled_placement(QRect(QPoint(), self.size()), self._pixmap.size(), 0)
        painter.drawPixmap(image_bounds, self._pixmap)
        painter.end()