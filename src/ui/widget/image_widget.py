"""Displays a single image or pixmap, keeping aspect ratios."""
from typing import Optional

from PySide6.QtCore import QSize, QRect
from PySide6.QtGui import QIcon, QPaintEvent, QPainter, QImage, QPixmap
from PySide6.QtWidgets import QWidget

from src.util.visual.geometry_utils import get_scaled_placement


class ImageWidget(QWidget):
    """Displays a single image, pixmap, or icon, keeping aspect ratios."""

    def __init__(self, image: Optional[QImage | QPixmap | QIcon], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._image = image

    def sizeHint(self) -> QSize:
        """Set expected size based on image size."""
        if self._image is None:
            return QSize(0, 0)
        if isinstance(self._image, QIcon):
            return self._image.availableSizes()[0]
        return self._image.size()

    def minimumSizeHint(self) -> QSize:
        """Set minimum size based on image size."""
        base_size = self.sizeHint()
        if base_size.width() > 3 and base_size.height() > 3:
            return QSize(base_size.width() // 3, base_size.height() // 3)
        return base_size

    @property
    def image(self) -> Optional[QImage | QPixmap | QIcon]:
        """Access the displayed image."""
        return self._image

    @image.setter
    def image(self, new_image: Optional[QImage | QPixmap | QIcon]) -> None:
        self._image = new_image
        self.update()

    @property
    def image_bounds(self) -> QRect:
        """Access the current image bounds within the widget."""
        return get_scaled_placement(self.size(), self.sizeHint(), 2)

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        """Draws the image scaled to widget size, keeping aspect ratios."""
        if self._image is None:
            return
        painter = QPainter(self)
        paint_bounds = self.image_bounds
        if isinstance(self._image, QImage):
            painter.drawImage(paint_bounds, self._image)
        elif isinstance(self._image, QPixmap):
            painter.drawPixmap(paint_bounds, self._image)
        elif isinstance(self._image, QIcon):
            self._image.paint(painter, paint_bounds)
        painter.end()
