"""Shows the edited image in its own window."""
from typing import Optional

from PyQt5.QtWidgets import QWidget

from src.image.image_stack import ImageStack
from src.ui.widget.image_widget import ImageWidget


class ImageWindow(ImageWidget):
    """Shows the edited image in its own window."""

    def __init__(self, image_stack: ImageStack, parent: Optional[QWidget] = None) -> None:
        super().__init__(image_stack.pixmap(), parent)
        self._image_stack = image_stack
        self._image_stack.content_changed.connect(self._pixmap_change_slot)

    def _pixmap_change_slot(self) -> None:
        self.image = self._image_stack.pixmap()
