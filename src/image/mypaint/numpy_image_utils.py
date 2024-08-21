"""Utility functions for speeding up image operations using numpy."""
from typing import TypeAlias, Optional
import numpy as np

from src.image.mypaint.libmypaint import TilePixelBuffer, TILE_DIM
from src.util.image_utils import AnyNpArray

OptionalNpArray: TypeAlias = Optional[AnyNpArray]


def pixel_data_as_numpy_16bit(pixel_data: TilePixelBuffer) -> AnyNpArray:  # type: ignore
    """Returns a numpy array interface for a tile pixel buffer."""
    return np.ctypeslib.as_array(pixel_data, shape=(TILE_DIM, TILE_DIM, 4))


def numpy_8bit_to_16bit(np_image: AnyNpArray) -> AnyNpArray:
    """Converts a numpy image array with 8-bit image color data to 16-bit color image data."""
    img_arr = (np_image.astype(np.float32) / 255 * (1 << 15)).astype(np.uint16)
    img_arr[:, :, [0, 2]] = img_arr[:, :, [2, 0]]  # R and G channels need to be swapped.
    return img_arr


def numpy_16bit_to_8bit(np_image: AnyNpArray) -> AnyNpArray:
    """Converts a numpy image array with 16-bit image color data to 8-bit color image data."""
    img_arr = (np_image / (1 << 15) * 255).astype(np.uint8)
    img_arr[:, :, [0, 2]] = img_arr[:, :, [2, 0]]  # R and G channels need to be swapped.
    return img_arr
