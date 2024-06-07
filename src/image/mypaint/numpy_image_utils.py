"""Utility functions for speeding up image operations using numpy."""
from typing import Tuple
from PyQt5.QtGui import QImage
import numpy as np
from src.image.mypaint.libmypaint import TilePixelBuffer, TILE_DIM


def pixel_data_as_numpy_16bit(pixel_data: TilePixelBuffer) -> np.ndarray:
    """Returns a numpy array interface for a tile pixel buffer."""
    return np.ctypeslib.as_array(pixel_data, shape=(TILE_DIM, TILE_DIM, 4))


def image_data_as_numpy_8bit(image: QImage) -> np.ndarray:
    """Returns a numpy array interface for a QImage's internal data buffer."""
    assert image.format() == QImage.Format_ARGB32_Premultiplied, \
        f'Image must be pre-converted to ARGB32_premultiplied, format was {image.format()}'
    image_ptr = image.bits()
    image_ptr.setsize(image.byteCount())
    return np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)


def numpy_8bit_to_16bit(np_image: np.ndarray) -> np.ndarray:
    """Converts a numpy image array with 8-bit image color data to 16-bit color image data."""
    img_arr = (np_image.astype(np.float32) / 255 * (1 << 15)).astype(np.uint16)
    img_arr[:, :, [0, 2]] = img_arr[:, :, [2, 0]]  # R and G channels need to be swapped.
    return img_arr


def numpy_16bit_to_8bit(np_image: np.ndarray) -> np.ndarray:
    """Converts a numpy image array with 16-bit image color data to 8-bit color image data."""
    img_arr = (np_image / (1 << 15) * 255).astype(np.uint8)
    img_arr[:, :, [0, 2]] = img_arr[:, :, [2, 0]]  # R and G channels need to be swapped.
    return img_arr


def is_fully_transparent(np_image: np.ndarray) -> bool:
    """Returns whether numpy image data is 100% transparent."""
    return np.all(np_image[:, :, 3] == 0)


def zero_image(image: QImage) -> None:
    """Quickly set image data to fully transparent."""
    image_ptr = image.bits()
    image_ptr.setsize(image.byteCount())
    img_arr = np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)
    img_arr[:, :, [3]] = 0


def numpy_intersect(arr1: np.ndarray, arr2: np.ndarray,
                    x: int = 0, y: int = 0) -> Tuple[np.array, np.array] | Tuple[None, None]:
    """Takes two offset numpy arrays and returns only their intersecting regions."""
    w1 = arr1.shape[1]
    w2 = arr2.shape[1]
    h1 = arr1.shape[0]
    h2 = arr2.shape[0]
    x1_start = max(x, 0)
    y1_start = max(y, 0)
    x1_end = min(x + w2, w1)
    y1_end = min(y + h2, h1)
    if x1_start >= x1_end or y1_start >= y1_end:
        return None, None
    x2_start = max(0, -x)
    y2_start = max(0, -y)
    x2_end = x2_start + (x1_end - x1_start)
    y2_end = y2_start + (y1_end - y1_start)
    arr1_cropped = arr1[y1_start:y1_end, x1_start:x1_end]
    arr2_cropped = arr2[y2_start:y2_end, x2_start:x2_end]
    return arr1_cropped, arr2_cropped
