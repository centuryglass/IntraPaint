"""Utility functions for converting between libmypaint pixel data, QImage, and numpy image arrays."""
from typing import TypeAlias, Any

import numpy as np

from src.image.mypaint.libmypaint import TilePixelBuffer, TILE_DIM
from src.util.visual.image_utils import NpUInt8Array, ARGB32_RGBA_ORDER

NpUInt16Array: TypeAlias = np.ndarray[Any, np.dtype[np.uint16]]


def pixel_data_as_numpy_16bit(pixel_data: TilePixelBuffer) -> NpUInt8Array:  # type: ignore
    """Returns a numpy array interface for a tile pixel buffer."""
    return np.ctypeslib.as_array(pixel_data, shape=(TILE_DIM, TILE_DIM, 4))


def numpy_8bit_to_16bit(np_image: NpUInt8Array) -> NpUInt16Array:
    """Converts an 8-bit ARGB32 numpy image array to libmypaint's 16-bit RGBA channel order and range."""
    rgba = np_image[:, :, ARGB32_RGBA_ORDER].astype(np.uint16)
    return (rgba << 7) | (rgba >> 1)


def numpy_16bit_to_8bit(np_image: NpUInt16Array) -> NpUInt8Array:
    """Converts a numpy image array in libmypaint's 16-bit RGBA format to an 8-bit ARGB32 array.

    libmypaint's channel range is 0-32768 (1 << 15), so a fully saturated channel is 256 after the shift and has to be
    clamped, or it wraps to 0 and fully opaque pixels from hard brushes become transparent."""
    img_arr = np.empty(np_image.shape, dtype=np.uint8)
    img_arr[:, :, ARGB32_RGBA_ORDER] = np.minimum(np_image >> 7, 255)
    return img_arr
