"""Shows the edited image in its own window."""
from typing import Optional

from PyQt5.QtWidgets import QWidget

from src.image.layer_stack import LayerStack
from src.ui.widget.image_widget import ImageWidget


class ImageWindow(ImageWidget):
    """Shows the edited image in its own window."""

    def __init__(self, layer_stack: LayerStack, parent: Optional[QWidget] = None) -> None:
        super().__init__(layer_stack.pixmap(), parent)
        self._layer_stack = layer_stack
        self._layer_stack.visible_content_changed.connect(self._pixmap_change_slot)

    def _pixmap_change_slot(self) -> None:
        self.image = self._layer_stack.pixmap()
