"""A Python wrapper for libmypaint image tile data."""
from ctypes import sizeof, memset
from typing import Optional

import numpy as np
from PyQt6.QtCore import Qt, QRectF, QRect, QSize
from PyQt6.QtGui import QImage, QPainter, QPainterPath
from PyQt6.QtWidgets import QWidget, QGraphicsItem, QStyleOptionGraphicsItem

from src.image.mypaint.libmypaint import TILE_DIM, TilePixelBuffer
from src.image.mypaint.numpy_image_utils import pixel_data_as_numpy_16bit, image_data_as_numpy_8bit, \
    numpy_8bit_to_16bit, numpy_16bit_to_8bit, numpy_intersect, \
    is_fully_transparent, AnyNpArray
from src.ui.graphics_items.layer_graphics_item import LayerGraphicsItem

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
        self._lock_alpha = False
        self._pixels: Optional[TilePixelBuffer] = tile_buffer
        self._size = size
        self._cache_image: Optional[QImage] = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
        self._mask_image: Optional[QImage] = None
        self._cache_valid = False
        self._composition_mode = QPainter.CompositionMode.CompositionMode_SourceOver
        self.setCacheMode(QGraphicsItem.CacheMode.NoCache)
        self.setFlag(LayerGraphicsItem.GraphicsItemFlag.ItemStacksBehindParent, True)
        if clear_buffer:
            self.clear()

    def invalidate(self) -> None:
        """Removes the tile from any scene, discards all cached data, and makes all other methods throw RuntimeError."""
        scene = self.scene()
        if scene is not None:
            scene.removeItem(self)
        self._pixels = None
        self._cache_image = None

    @property
    def composition_mode(self) -> QPainter.CompositionMode:
        """Access the painting mode used to render the tile into a QGraphicsScene."""
        return self._composition_mode

    @composition_mode.setter
    def composition_mode(self, new_mode: QPainter.CompositionMode) -> None:
        if new_mode != self._composition_mode:
            self._composition_mode = QPainter.CompositionMode(new_mode)
            self.update()

    @property
    def alpha_lock(self) -> bool:
        """Return whether the alpha channel is currently locked."""
        return self._lock_alpha

    @alpha_lock.setter
    def alpha_lock(self, locked: bool) -> None:
        if self._lock_alpha and not locked:  # When unlocking, make sure suppressed alpha changes don't appear suddenly
            if not self._cache_valid:
                self.update_cache()
            self.copy_image_into_pixel_buffer(self._pixels, self._cache_image, 0, 0, False)
        self._lock_alpha = locked

    @property
    def mask(self) -> Optional[QImage]:
        """If not None, only content covered by sections of the mask with alpha > 0 will be shown or copied."""
        return self._mask_image

    @mask.setter
    def mask(self, mask: Optional[QImage]) -> None:
        if mask is None and self._mask_image is None:
            return
        if not self._cache_valid:
            self.update_cache()
        if mask is not None:
            assert mask.size() == self._size, 'Mask size must match tile size'
        if self._mask_image is not None:  # Clear hidden changes suppressed by the old mask:
            self.copy_image_into_pixel_buffer(self._pixels, self._cache_image, 0, 0, False)
        self._mask_image = mask
        self.update_cache()

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
        assert self._cache_image is not None
        return QRectF(self._cache_image.rect())

    def shape(self) -> QPainterPath:
        """Returns the tile's bounds as a shape."""
        self._assert_is_valid()
        assert self._cache_image is not None
        path = QPainterPath()
        path.addRect(QRectF(self._cache_image.rect()))
        return path

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draw the tile to the graphics view."""
        self._assert_is_valid()
        assert self._cache_image is not None
        if painter is None:
            return
        if not self._cache_valid:
            self.update_cache()
        painter.save()
        painter.setCompositionMode(self._composition_mode)
        bounds = QRect(0, 0, self._cache_image.width(), self._cache_image.height())
        painter.drawImage(bounds, self._cache_image)
        painter.restore()

    def get_bits(self, read_only: bool) -> TilePixelBuffer:
        """Access the image data array."""
        self._assert_is_valid()
        assert self._pixels is not None
        if read_only:
            self._cache_valid = False
        return self._pixels

    def draw_point(self, x: int, y: int, r: int, g: int, b: int, a: int) -> None:
        """Draw a single point into the image data."""
        self._assert_is_valid()
        assert self._pixels is not None
        self._cache_valid = False
        self._pixels[y][x][RED] = r
        self._pixels[y][x][GREEN] = g
        self._pixels[y][x][BLUE] = b
        self._pixels[y][x][ALPHA] = a

    def update_cache(self) -> None:
        """Copy data into the QImage cache."""
        self._assert_is_valid()
        assert self._cache_image is not None
        self.copy_tile_into_image(self._cache_image, skip_if_transparent=False)
        self._cache_valid = True

    def set_cache(self, cache_image: QImage) -> None:
        """Directly update the cache with image data. This does not alter the pixel buffer."""
        self._assert_is_valid()
        self._cache_image = cache_image
        self._cache_valid = True

    def copy_tile_into_image(self, image: QImage, source: Optional[QRect] = None, destination: Optional[QRect] = None,
                             skip_if_transparent: bool = True, color_correction: bool = False) -> bool:
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
        color_correction: bool, default = False
            Perform corrections for possible color conversion issues.
        """
        self._assert_is_valid()
        if source is None:
            source = QRect(0, 0, self.size.width(), self.size.height())
        if destination is None:
            destination = QRect(0, 0, image.width(), image.height())
        assert self._pixels is not None
        np_pixels = pixel_data_as_numpy_16bit(self._pixels)[source.y():source.y() + source.height(),
                                                            source.x():source.x() + source.width()]
        np_image = image_data_as_numpy_8bit(image)[
                   destination.y():destination.y() + destination.height(),
                   destination.x():destination.x() + destination.width()]
        if self._mask_image is not None:
            np_mask = image_data_as_numpy_8bit(self._mask_image)
            _, np_mask = numpy_intersect(np_image, np_mask, 0, 0)
        else:
            np_mask = None
        intersect = numpy_intersect(np_image, np_pixels, 0, 0)
        if intersect[0] is None or intersect[1] is None:
            return False  # No intersection.
        np_image, np_pixels = intersect
        if skip_if_transparent and is_fully_transparent(np_pixels):
            return False  # Don't waste time converting and copying transparent pixels into a transparent image.
        np_pixels = numpy_16bit_to_8bit(np_pixels)

        if self._lock_alpha:
            np_image = np_image[:, :, 0:3]
            np_pixels = np_pixels[:, :, 0:3]

        if color_correction:
            # Color conversion produces artifacts at tile edges if the data is copied directly.  Avoid this by
            # discarding pixel changes that don't exceed the magnitude of error created by color conversion.
            min_color_difference = 3.0

            def color_difference(color1, color2):
                """Calculate the color difference between two RGB colors."""
                return np.linalg.norm(color1 - color2)

            for y in range(np_image.shape[0]):
                for x in range(np_image.shape[1]):
                    if np_mask is not None and np_mask[y, x, ALPHA] == 0:
                        continue
                    if not self._lock_alpha and np_image[y, x, ALPHA] == 0:
                        # Don't filter out changes to transparent pixels:
                        np_image[y, x] = np_pixels[y, x]
                        continue
                    color_diff = color_difference(np_image[y, x], np_pixels[y, x])
                    if color_diff > min_color_difference:
                        np_image[y, x] = np_pixels[y, x]
        else:
            if np_mask is not None:
                mask_index = np_mask[..., 3] != 0
                np_image[mask_index] = np_pixels[mask_index]
            else:
                np.copyto(np_image, np_pixels)
        return True

    @staticmethod
    def copy_image_into_pixel_buffer(pixels, image: QImage, x: int, y: int, skip_if_transparent: bool = True) -> bool:
        """Copy tile data from a QImage at arbitrary (x, y) image coordinates, returning whether data was copied."""
        np_pixels = pixel_data_as_numpy_16bit(pixels)
        np_image = image_data_as_numpy_8bit(image)
        intersect = numpy_intersect(np_image, np_pixels, x, y)
        if intersect[0] is None or intersect[1] is None:
            return False  # No intersection.
        np_image, np_pixels = intersect
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
        assert self._pixels is not None and self._cache_image is not None
        memset(self._pixels, 0, sizeof(self._pixels))
        self._cache_image.fill(Qt.GlobalColor.transparent)
        self._cache_valid = True

    def save(self, path: str) -> None:
        """Save the tile's contents as an image."""
        self._assert_is_valid()
        assert self._cache_image is not None
        if not self._cache_valid:
            self.update_cache()
        self._cache_image.save(path)

    def set_image(self, image: QImage) -> None:
        """Load image content from a QImage."""
        self._assert_is_valid()
        tile_size = self.boundingRect().size()
        if tile_size != image.size():
            image = image.scaled(tile_size)
        if image.format() != QImage.Format.Format_ARGB32_Premultiplied:
            image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self._cache_image = image.scaled(tile_size)
        image_ptr = image.bits()
        assert image_ptr is not None, 'Invalid image given'
        image_ptr.setsize(image.byteCount())
        np_image: AnyNpArray = np.ndarray(shape=(TILE_DIM, TILE_DIM, 4), dtype=np.uint8, buffer=image_ptr)
        np_pixels = (np_image.astype(np.float32) / 255 * (1 << 15)).astype(np.uint16)
        np.ctypeslib.as_array(self._pixels, shape=(TILE_DIM, TILE_DIM, 4))[:] = np_pixels
        self._cache_valid = True
