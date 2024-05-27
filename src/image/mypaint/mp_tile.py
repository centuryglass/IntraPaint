"""A Python wrapper for libmypaint image tile data."""
from typing import Optional
from ctypes import sizeof, memset
import numpy as np
from PyQt5.QtWidgets import QWidget, QGraphicsItem, QStyleOptionGraphicsItem
from PyQt5.QtGui import QImage, QPainter, QPainterPath
from PyQt5.QtCore import Qt, QRectF, QSize, QPoint
from src.image.mypaint.libmypaint import TILE_DIM, TilePixelBuffer
from src.image.mypaint.numpy_image_utils import pixel_data_as_numpy_16bit, image_data_as_numpy_8bit, \
    numpy_8bit_to_16bit, numpy_16bit_to_8bit, numpy_intersect, \
    is_fully_transparent

RED = 0
GREEN = 1
BLUE = 2
ALPHA = 3


class MPTile(QGraphicsItem):
    """A Python wrapper for libmypaint image tile data."""

    def __init__(self,
                 tile_buffer: TilePixelBuffer,
                 clear_buffer: bool = True,
                 size: QSize = QSize(TILE_DIM, TILE_DIM),
                 parent: Optional[QGraphicsItem] = None):
        """Initialize tile data."""
        super().__init__(parent)
        self._pixels = tile_buffer
        self._size = size
        self._cache_image = QImage(size, QImage.Format_ARGB32_Premultiplied)
        self._cache_valid = False
        self.setCacheMode(QGraphicsItem.NoCache)
        if clear_buffer:
            self.clear()

    def boundingRect(self) -> QRectF:
        """Returns the tile's bounds."""
        return QRectF(self._cache_image.rect())

    def shape(self) -> QPainterPath:
        """Returns the tile's bounds as a shape."""
        path = QPainterPath()
        path.addRect(QRectF(self._cache_image.rect()))
        return path

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draw the tile to the graphics view."""
        if painter is None:
            return
        if not self._cache_valid:
            self.update_cache()
        painter.drawImage(QPoint(0, 0), self._cache_image, self._cache_image.rect())

    def get_bits(self, read_only: bool) -> TilePixelBuffer:
        """Access the image data array."""
        if read_only:
            self._cache_valid = False
        return self._pixels

    def draw_point(self, x: int, y: int, r: int, g: int, b: int, a: int) -> None:
        """Draw a single point into the image data."""
        self._cache_valid = False
        self._pixels[y][x][RED] = r
        self._pixels[y][x][GREEN] = g
        self._pixels[y][x][BLUE] = b
        self._pixels[y][x][ALPHA] = a

    def update_cache(self) -> None:
        """Copy data into the QImage cache."""
        self.copy_tile_into_image(self._cache_image, 0, 0, False)
        self._cache_valid = True

    def copy_tile_into_image(self, image: QImage, x: int, y: int, skip_if_transparent: bool = True) -> bool:
        """Copy tile data into a QImage at arbitrary (x, y) image coordinates, returning whether data was copied."""
        np_pixels = pixel_data_as_numpy_16bit(self._pixels)[:self._size.height(), :self._size.width()]
        np_image = image_data_as_numpy_8bit(image)
        np_image, np_pixels = numpy_intersect(np_image, np_pixels, x, y)
        if np_image is None:
            return False  # No intersection.
        if skip_if_transparent and is_fully_transparent(np_pixels):
            return False  # Don't waste time converting and copying transparent pixels into a transparent image.
        np_pixels = numpy_16bit_to_8bit(np_pixels)
        np.copyto(np_image, np_pixels)
        return True

    @staticmethod
    def copy_image_into_pixel_buffer(pixels, image: QImage, x: int, y: int, skip_if_transparent: bool = True) -> bool:
        """Copy tile data from a QImage at arbitrary (x, y) image coordinates, returning whether data was copied."""
        np_pixels = pixel_data_as_numpy_16bit(pixels)
        np_image = image_data_as_numpy_8bit(image)
        np_image, np_pixels = numpy_intersect(np_image, np_pixels, x, y)
        if np_image is None:
            return False  # No intersection.
        if skip_if_transparent and is_fully_transparent(np_image):
            return False  # Don't waste time converting and copying transparent pixels into a transparent tile.
        np_image = numpy_8bit_to_16bit(np_image)
        np.copyto(np_pixels, np_image)
        return True

    def copy_image_into_tile(self, image: QImage, x: int, y: int, skip_if_transparent: bool = True) -> bool:
        """Copy tile data from a QImage at arbitrary (x, y) image coordinates."""
        return MPTile.copy_image_into_pixel_buffer(self._pixels, image, x, y, skip_if_transparent)

    def is_fully_transparent(self):
        """Checks if this tile is completely transparent."""
        np_pixels = pixel_data_as_numpy_16bit(self._pixels)
        return is_fully_transparent(np_pixels)

    def clear(self) -> None:
        """Clear all image data."""
        memset(self._pixels, 0, sizeof(self._pixels))
        self._cache_image.fill(Qt.transparent)
        self._cache_valid = True

    def save(self, path: str) -> None:
        """Save the tile's contents as an image."""
        if not self._cache_valid:
            self.update_cache()
        self._cache_image.save(path)

    def set_image(self, image: QImage) -> None:
        """Load image content from a QImage."""
        tile_size = self.boundingRect().size()
        if tile_size != image.size():
            image = image.scaled(tile_size)
        if image.format() != QImage.Format_ARGB32_Premultiplied:
            image = image.convertToFormat(QImage.Format_ARGB32_Premultiplied)
        self._cache_image = image.scaled(tile_size)
        image_ptr = image.bits()
        image_ptr.setsize(image.byteCount())
        np_image = np.ndarray(shape=(TILE_DIM, TILE_DIM, 4), dtype=np.uint8, buffer=image_ptr)
        np_pixels = (np_image.astype(np.float32) / 255 * (1 << 15)).astype(np.uint16)
        np.ctypeslib.as_array(self._pixels, shape=(TILE_DIM, TILE_DIM, 4))[:] = np_pixels
        self._cache_valid = True
