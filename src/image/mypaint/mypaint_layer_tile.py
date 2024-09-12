"""Connects a libmypaint image tile to a region in an ImageLayer."""
from ctypes import sizeof, memset
from typing import Optional, Tuple

import numpy as np
from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QImage

from src.image.layers.image_layer import ImageLayer
from src.image.mypaint.libmypaint import TilePixelBuffer
from src.image.mypaint.numpy_image_utils import pixel_data_as_numpy_16bit, numpy_8bit_to_16bit, numpy_16bit_to_8bit
from src.util.visual.image_utils import (NpAnyArray, image_data_as_numpy_8bit, numpy_intersect, numpy_bounds_index,
                                         NpUInt8Array)


class MyPaintLayerTile:
    """Connects a libmypaint image tile to an ImageLayer."""

    def __init__(self,
                 tile_buffer: TilePixelBuffer,  # type: ignore
                 layer: Optional[ImageLayer] = None,
                 bounds: QRect = QRect(),
                 clear_buffer: bool = True):
        """Initialize tile data."""
        self._layer: Optional[ImageLayer] = None
        self._base_bounds = QRect()
        self._bounds = QRect()
        self._pixels: TilePixelBuffer = tile_buffer  # type: ignore
        self._mask: Optional[NpUInt8Array] = None
        if clear_buffer:
            self.clear()
        self.set_layer(layer, bounds)

    def set_layer(self, layer: Optional[ImageLayer], bounds: Optional[QRect] = None) -> None:
        """Connects this tile to a specific place within an image layer, loading that layer's image data, or clearing
           the tile if the layer is None."""
        if layer is not None:
            assert bounds is not None and bounds.isValid() and not bounds.isEmpty(), f'invalid bounds {bounds}'
        if bounds is not None:
            self._base_bounds = bounds
        if layer is not None and bounds is not None:
            bounds = bounds.intersected(layer.bounds)
            assert not bounds.isEmpty(), f'invalid bounds {bounds} (from {self._base_bounds})'
        elif layer is None:
            bounds = QRect()
        if layer == self._layer and bounds == self._bounds:
            return
        if self._layer is not None:
            self.disconnect_layer_signals()
        self._layer = layer
        self._bounds = bounds
        self.connect_layer_signals()
        if layer is None:
            self.clear()
        else:
            self.load_pixels_from_layer()

    def _image_and_pixel_intersect_arrays(self, np_image: NpAnyArray) -> Tuple[NpAnyArray, NpAnyArray]:
        """Given an image array cropped to bounds, return a converted image array and an array into the pixel buffer,
        cropped so that both are equal size."""
        np_pixels = pixel_data_as_numpy_16bit(self._pixels)
        img_intersect, pixel_intersect = numpy_intersect(np_image, np_pixels)
        assert img_intersect is not None and pixel_intersect is not None
        return img_intersect, pixel_intersect

    def load_pixels_from_layer(self) -> None:
        """Overwrite the tile's MyPaint pixel buffer with pixel data from the connected image layer."""
        if self._layer is None or self._bounds.isEmpty():
            return
        np_image = numpy_8bit_to_16bit(numpy_bounds_index(self._layer.image_bits_readonly, self._bounds))
        np_image, np_pixels = self._image_and_pixel_intersect_arrays(np_image)

        np.copyto(np_pixels, np_image)

    def write_pixels_to_layer_image(self, layer_image: QImage) -> None:
        """Write image data from the MyPaint pixel buffer into a layer image."""
        if self._layer is None or self._bounds.isEmpty() or self._layer.locked:
            return
        np_image = numpy_bounds_index(image_data_as_numpy_8bit(layer_image), self._bounds)
        np_image, np_pixels = self._image_and_pixel_intersect_arrays(np_image)
        np_pixels = numpy_16bit_to_8bit(np_pixels)
        if self._mask is not None:
            _, np_mask = numpy_intersect(np_image, self._mask)
        else:
            np_mask = None
        change_mask = None
        if self._layer.alpha_locked:
            change_mask = np_image[:, :, 3] > 0
            np_image = np_image[:, :, :3]
            np_pixels = np_pixels[:, :, :3]
        if np_mask is not None:
            selection_mask = np_mask[..., 3] > 0
            change_mask = selection_mask if change_mask is None else selection_mask & change_mask
        if change_mask is not None:
            np_image[change_mask] = np_pixels[change_mask]
        else:
            np.copyto(np_image, np_pixels)

    def write_pixels_to_layer(self) -> None:
        """Write image data from the MyPaint pixel buffer into the connected image layer."""
        if self._layer is None or self._bounds.isEmpty() or self._layer.locked:
            return
        self._layer.content_changed.disconnect(self._layer_content_changed_slot)
        with self._layer.borrow_image(self._bounds) as layer_image:
            self.write_pixels_to_layer_image(layer_image)
        self._layer.content_changed.connect(self._layer_content_changed_slot)

    def connect_layer_signals(self) -> None:
        """Connect to layer change signals to automatically update tile bounds, lock state, and image content."""
        if self._layer is not None:
            self._layer.content_changed.connect(self._layer_content_changed_slot)
            self._layer.size_changed.connect(self._layer_size_changed_slot)
            self._layer.lock_changed.connect(self._layer_lock_change_slot)
            self._layer.alpha_lock_changed.connect(self._layer_lock_change_slot)

    def disconnect_layer_signals(self) -> None:
        """disconnect layer change signals to stop the tile from updating when the layer changes."""
        if self._layer is not None:
            self._layer.content_changed.disconnect(self._layer_content_changed_slot)
            self._layer.size_changed.disconnect(self._layer_size_changed_slot)
            self._layer.lock_changed.disconnect(self._layer_lock_change_slot)
            self._layer.alpha_lock_changed.connect(self._layer_lock_change_slot)

    @property
    def bounds(self) -> QRect:
        """Accesses the tile's bounds within the layer."""
        return QRect(self._bounds)

    @property
    def mask(self) -> Optional[NpUInt8Array]:
        """If not None, only content covered by sections of the mask with alpha > 0 will be shown or copied."""
        return self._mask

    @mask.setter
    def mask(self, mask: Optional[NpUInt8Array]) -> None:
        if mask is None and self._mask is None:
            return
        if mask is not None:
            assert mask.shape[0] == self.size.height() and mask.shape[1] == self.size.width(), \
                f'Tile size = {self.size}, mask shape = {mask.shape}'
        if self._mask is not None:  # Clear hidden changes suppressed by the old mask:
            self.load_pixels_from_layer()
        self._mask = mask

    @property
    def size(self) -> QSize:
        """Returns the tile's size in pixels."""
        return self._bounds.size()

    @property
    def pixel_buffer(self) -> TilePixelBuffer:  # type: ignore
        """Access the tile's libmypaint pixel buffer."""
        return self._pixels

    def clear(self) -> None:
        """Clear all image data."""
        memset(self._pixels, 0, sizeof(self._pixels))

    def _layer_content_changed_slot(self, layer: ImageLayer, bounds: QRect) -> None:
        assert layer == self._layer
        if bounds.intersects(self._bounds):
            self.load_pixels_from_layer()

    def _layer_size_changed_slot(self, layer: ImageLayer, _) -> None:
        assert layer == self._layer
        self.set_layer(layer, self._base_bounds)

    def _layer_lock_change_slot(self, layer: ImageLayer, locked: bool) -> None:
        """Reset the pixel buffer on unlock"""
        assert layer == self._layer
        if not locked:
            self.load_pixels_from_layer()
