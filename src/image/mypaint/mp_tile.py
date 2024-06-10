"""A Python wrapper for libmypaint image tile data."""
from typing import Optional
from ctypes import sizeof, memset
import numpy as np
from PyQt5.QtWidgets import QWidget, QGraphicsItem, QStyleOptionGraphicsItem
from PyQt5.QtGui import QImage, QPainter, QPainterPath
from PyQt5.QtCore import Qt, QRectF, QRect, QSize, QPoint
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
        self._pixels: Optional[TilePixelBuffer] = tile_buffer
        self._size = size
        self._cache_image: Optional[QImage] = QImage(size, QImage.Format_ARGB32_Premultiplied)
        self._cache_valid = False
        self.setCacheMode(QGraphicsItem.NoCache)
        if clear_buffer:
            self.clear()

    def invalidate(self) -> None:
        """Removes the tile from any scene, discards all cached data, and makes all other methods throw RuntimeError."""
        if self.scene() is not None:
            self.scene().removeItem(self)
        self._pixels = None
        self._cache_image = None

    @property
    def is_valid(self) -> bool:
        """Returns whether this tile is still a valid part of a surface."""
        return self._pixels is not None

    def _assert_is_valid(self):
        """Prevent an invalid tile from being used by throwing RuntimeError"""
        if not self.is_valid:
            raise RuntimeError('Tried to access invalid tile.')

    @property
    def size(self) -> QSize:
        """Returns the tile's size in pixels."""
        self._assert_is_valid()
        return self._size

    def boundingRect(self) -> QRectF:
        """Returns the tile's bounds."""
        self._assert_is_valid()
        return QRectF(self._cache_image.rect())

    def shape(self) -> QPainterPath:
        """Returns the tile's bounds as a shape."""
        self._assert_is_valid()
        path = QPainterPath()
        path.addRect(QRectF(self._cache_image.rect()))
        return path

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draw the tile to the graphics view."""
        self._assert_is_valid()
        if painter is None:
            return
        if not self._cache_valid:
            self.update_cache()
        painter.drawImage(QPoint(0, 0), self._cache_image, self._cache_image.rect())

    def get_bits(self, read_only: bool) -> TilePixelBuffer:
        """Access the image data array."""
        self._assert_is_valid()
        if read_only:
            self._cache_valid = False
        return self._pixels

    def draw_point(self, x: int, y: int, r: int, g: int, b: int, a: int) -> None:
        """Draw a single point into the image data."""
        self._assert_is_valid()
        self._cache_valid = False
        self._pixels[y][x][RED] = r
        self._pixels[y][x][GREEN] = g
        self._pixels[y][x][BLUE] = b
        self._pixels[y][x][ALPHA] = a

    def update_cache(self) -> None:
        """Copy data into the QImage cache."""
        self._assert_is_valid()
        self.copy_tile_into_image(self._cache_image, skip_if_transparent=False)
        self._cache_valid = True

    def set_cache(self, cache_image: QImage) -> None:
        """Directly update the cache with image data. This does not alter the pixel buffer."""
        self._assert_is_valid()
        self._cache_image = cache_image
        self._cache_valid = True

    def copy_tile_into_image(self, image: QImage, source: Optional[QRect] = None, destination: Optional[QRect] = None,
                             skip_if_transparent: bool = True, color_correction_edge_width: int = 0) -> bool:
        """Copy tile data into a QImage at arbitrary (x, y) image coordinates, returning whether data was copied.
        This operation does no scaling; any surface data that does not overlap with the image destination bounds will
        not be copied.

        Parameters
        ----------
        image: QImage
            Image where tile data will be copied.
        source: QRect, optional
            Area within the tile where the data will be copied from. If not defined, the entire tile will be copied
            into the destination.
        destination: QRect, optional
            Area within the image where the data will be copied. If not defined, the image bounds will be
            used.
        skip_if_transparent: bool
            If true, skip the operation if the tile's contents are completely transparent.
        color_correction_edge_width: int, default = 0
            If non-zero, perform color correction around all tile edges when copying data back into the image.
        """
        self._assert_is_valid()
        if source is None:
            source = QRect(0, 0, self.size.width(), self.size.height())
        if destination is None:
            destination = QRect(0, 0, image.width(), image.height())
        np_pixels = pixel_data_as_numpy_16bit(self._pixels)[source.y():source.y() + source.height(),
                                                            source.x():source.x() + source.width()]
        np_image = image_data_as_numpy_8bit(image)[destination.y():destination.y() + destination.height(),
                                                   destination.x():destination.x() + destination.width()]
        np_image, np_pixels = numpy_intersect(np_image, np_pixels, 0, 0)
        if np_image is None:
            return False  # No intersection.
        if skip_if_transparent and is_fully_transparent(np_pixels):
            return False  # Don't waste time converting and copying transparent pixels into a transparent image.
        np_pixels = numpy_16bit_to_8bit(np_pixels)

        if color_correction_edge_width == 0:
            np.copyto(np_image, np_pixels)
        else:
            min_color_difference = 1.8
            height, width, _ = np_pixels.shape
            color_correction_edge_width = min(color_correction_edge_width, width // 2 - 1, height // 2 - 1)

            # Copy the central area directly
            central_region = (slice(color_correction_edge_width, height - color_correction_edge_width),
                              slice(color_correction_edge_width, width - color_correction_edge_width))
            np.copyto(np_image[central_region], np_pixels[central_region])

            # Color conversion produces mild artifacts at tile edges if the data is copied directly.  Avoid this by
            # discarding pixel changes that don't exceed the magnitude of error created by color conversion.
            edge_regions = [
                (slice(0, color_correction_edge_width), slice(0, width)),  # Top edge
                (slice(height - color_correction_edge_width, height), slice(0, width)),  # Bottom edge
                (slice(0, height), slice(0, color_correction_edge_width)),  # Left edge
                (slice(0, height), slice(width - color_correction_edge_width, width))  # Right edge
            ]

            def color_difference(color1, color2):
                """Calculate the color difference between two RGB colors."""
                return np.linalg.norm(color1 - color2)

            for region in edge_regions:
                for y in range(region[0].start, region[0].stop):
                    for x in range(region[1].start, region[1].stop):
                        if color_difference(np_image[y, x], np_pixels[y, x]) > min_color_difference:
                            np_image[y, x] = np_pixels[y, x]
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
        self._assert_is_valid()
        return MPTile.copy_image_into_pixel_buffer(self._pixels, image, x, y, skip_if_transparent)

    def is_fully_transparent(self):
        """Checks if this tile is completely transparent."""
        self._assert_is_valid()
        np_pixels = pixel_data_as_numpy_16bit(self._pixels)
        return is_fully_transparent(np_pixels)

    def clear(self) -> None:
        """Clear all image data."""
        self._assert_is_valid()
        memset(self._pixels, 0, sizeof(self._pixels))
        self._cache_image.fill(Qt.transparent)
        self._cache_valid = True

    def save(self, path: str) -> None:
        """Save the tile's contents as an image."""
        self._assert_is_valid()
        if not self._cache_valid:
            self.update_cache()
        self._cache_image.save(path)

    def set_image(self, image: QImage) -> None:
        """Load image content from a QImage."""
        self._assert_is_valid()
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
