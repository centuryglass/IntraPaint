"""Displays a single image or pixmap, keeping aspect ratios."""
from typing import Optional

from PyQt5.QtCore import QSize
from PyQt5.QtGui import QIcon, QPaintEvent, QPainter, QImage, QPixmap
from PyQt5.QtWidgets import QWidget

from src.util.geometry_utils import get_scaled_placement


class ImageWidget(QWidget):
    """Displays a single image, pixmap, or icon, keeping aspect ratios."""

    def __init__(self, image: Optional[QImage | QPixmap | QIcon], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._image = image

    def sizeHint(self) -> QSize:
        """Set expected size based on image size."""
        if self._image is None:
            return QSize(0, 0)
        elif isinstance(self._image, QIcon):
            return self._image.pixmap().size()
        return self._image.size()

    @property
    def image(self) -> Optional[QImage | QPixmap | QIcon]:
        """Access the displayed image."""
        return self._image

    @image.setter
    def image(self, new_image: Optional[QImage | QPixmap | QIcon]) -> None:
        self._image = new_image
        self.update()

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        """Draws the image scaled to widget size, keeping aspect ratios."""
        if self._image is None:
            return
        painter = QPainter(self)
        paint_bounds = get_scaled_placement(self.size(), self.sizeHint(), 2)
        if isinstance(self._image, QImage):
            painter.drawImage(paint_bounds, self._image)
        elif isinstance(self._image, QPixmap):
            painter.drawPixmap(paint_bounds, self._image)
        elif isinstance(self._image, QIcon):
            painter.drawPixmap(paint_bounds, self._image.pixmap())
        painter.end()

