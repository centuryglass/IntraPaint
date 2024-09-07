"""Utility functions for converting between libmypaint pixel data, QImage, and numpy image arrays."""
from typing import TypeAlias, Any

import numpy as np

from src.image.mypaint.libmypaint import TilePixelBuffer, TILE_DIM
from src.util.visual.image_utils import NpUInt8Array

NpUInt16Array: TypeAlias = np.ndarray[Any, np.dtype[np.uint16]]


def pixel_data_as_numpy_16bit(pixel_data: TilePixelBuffer) -> NpUInt8Array:  # type: ignore
    """Returns a numpy array interface for a tile pixel buffer."""
    return np.ctypeslib.as_array(pixel_data, shape=(TILE_DIM, TILE_DIM, 4))


def numpy_8bit_to_16bit(np_image: NpUInt8Array) -> NpUInt16Array:
    """Converts a numpy image array with 8-bit image color data to 16-bit color image data."""
    img_arr = (np_image.astype(np.uint16) << 7) | (np_image.astype(np.uint16) >> 1)
    img_arr[:, :, [0, 2]] = img_arr[:, :, [2, 0]]  # R and G channels need to be swapped.
    return img_arr


def numpy_16bit_to_8bit(np_image: NpUInt16Array) -> NpUInt8Array:
    """Converts a numpy image array with 16-bit image color data to 8-bit color image data."""
    img_arr = (np_image >> 7).astype(np.uint8)
    img_arr[:, :, [0, 2]] = img_arr[:, :, [2, 0]]  # R and G channels need to be swapped.
    return img_arr
