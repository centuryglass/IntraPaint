"""Adds general-purpose utility functions for manipulating image data"""
import base64
import io
import logging
import os
import tempfile
import uuid
from typing import Optional, Any, TypeAlias, Callable

import cv2
# noinspection PyPackageRequirements
import numpy as np
from PIL import Image
from PySide6.QtCore import QBuffer, QRect, QSize, Qt, QPoint, QFile, QIODevice, QByteArray
from PySide6.QtGui import QImage, QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import QStyle, QWidget, QApplication
from numpy import ndarray, dtype

from src.util.shared_constants import ICON_SIZE

logger = logging.getLogger(__name__)

NpAnyArray: TypeAlias = ndarray[Any, dtype[Any]]
NpUInt8Array: TypeAlias = np.ndarray[Any, np.dtype[np.uint8]]

temp_image_dir = ''


def create_transparent_image(size: QSize) -> QImage:
    """Returns a new image filled with transparency, set to the requested size."""
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    if not size.isEmpty():
        image.fill(Qt.GlobalColor.transparent)
    return image


def image_is_fully_transparent(image: QImage | QPixmap | NpAnyArray) -> bool:
    """Returns whether all pixels in the image are 100% transparent."""
    if isinstance(image, (QImage, QPixmap)):
        if not image.hasAlphaChannel():
            return False
        if isinstance(image, QPixmap):
            image = image.toImage()
        if image.format() != QImage.Format.Format_ARGB32_Premultiplied:
            image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        image = image_data_as_numpy_8bit(image)
    return image[:, :, 3].max() == 0


def image_is_fully_opaque(image: QImage | QPixmap | NpAnyArray) -> bool:
    """Returns whether all pixels in the image are 100% opaque."""
    if isinstance(image, (QImage, QPixmap)):
        if not image.hasAlphaChannel():
            return True
        if isinstance(image, QPixmap):
            image = image.toImage()
        if image.format() != QImage.Format.Format_ARGB32_Premultiplied:
            image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        image = image_data_as_numpy_8bit(image)
    return image[:, :, 3].min() == 255


def image_has_partial_alpha(image: QImage | QPixmap | NpAnyArray) -> bool:
    """Returns whether the image contains pixels with any opacity other than 0 or 255"""
    if isinstance(image, (QImage, QPixmap)):
        if not image.hasAlphaChannel():
            return False
        if isinstance(image, QPixmap):
            image = image.toImage()
        if image.format() != QImage.Format.Format_ARGB32_Premultiplied:
            image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        image = image_data_as_numpy_8bit(image)
    image_alpha = image[:, :, 3]
    return image_alpha.max() > 0 and image_alpha.min() < 255


def qimage_from_base64(image_str: str) -> QImage:
    """Returns a QImage from base64-encoded string data."""
    if image_str.startswith(BASE_64_PREFIX):
        image_str = image_str[len(BASE_64_PREFIX):]
    image_data = QByteArray.fromBase64(image_str.encode())
    image = QImage.fromData(image_data, 'PNG')  # type: ignore
    if image.isNull():
        raise ValueError('Invalid base64 image string')
    if image.hasAlphaChannel():
        image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    else:
        image = image.convertToFormat(QImage.Format.Format_RGB888)
    return image


BASE_64_PREFIX = 'data:image/png;base64,'


def image_to_base64(image: QImage | Image.Image | str, include_prefix=False) -> str:
    """Convert a PIL image, QImage or image path to a base64 string."""
    if isinstance(image, str):
        file = QFile(image)
        if not file.open(QIODevice.OpenModeFlag.ReadOnly):
            raise IOError(f'Failed to open {image}')
        image_str = QByteArray(file.readAll()).toBase64().data().decode('utf-8')
        file.close()
    elif isinstance(image, QImage):
        image_bytes = QByteArray()
        buffer = QBuffer(image_bytes)
        image.save(buffer, 'PNG')  # type: ignore
        image_str = base64.b64encode(image_bytes.data()).decode('utf-8')
    else:
        assert isinstance(image, Image.Image)
        pil_buffer = io.BytesIO()
        image.save(pil_buffer, format='PNG')
        image_str = str(base64.b64encode(pil_buffer.getvalue()), 'utf-8')
    if include_prefix:
        return BASE_64_PREFIX + image_str
    return image_str


def image_content_bounds(image: QImage | np.ndarray, search_bounds: Optional[QRect] = None,
                             alpha_threshold=0.0) -> QRect:
    """Finds the smallest rectangle within an image that contains all non-empty pixels in that image.

    Parameters
    ----------
    image: QImage | ndarray
        A QImage with format ARGB32_Premultiplied, optionally pre-converted to a numpy array.
    search_bounds: QRect, optional
        Image content outside of these bounds will be ignored. If None, entire image bounds will be used.
    alpha_threshold: float, default = 0.0
        Any pixel with an alpha value at or below the alpha_threshold will be considered empty.
    """
    if isinstance(image, QImage):
        image_ptr = image.bits()
        assert image_ptr is not None
        np_image: NpAnyArray = np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)
    else:
        np_image = image
    if search_bounds is not None:
        x_min = max(0, search_bounds.x())
        x_max = min(np_image.shape[1], search_bounds.x() + search_bounds.width())
        y_min = max(0, search_bounds.y())
        y_max = min(np_image.shape[0], search_bounds.y() + search_bounds.height())
        if x_max <= x_min or y_max <= y_min:
            return QRect()
        np_image = np_image[y_min:y_max, x_min:x_max:, :]
    else:
        x_min = 0
        y_min = 0

    # If alpha_threshold is 0.0, we can use the alpha channel directly as a binary mask. Otherwise, create a new mask
    # from the comparison:
    if alpha_threshold != 0.0:
        binary_mask = (np_image[:, :, 3] > alpha_threshold)
    else:
        binary_mask = np_image[:, :, 3]
    coords = cv2.findNonZero(binary_mask)

    if coords is None:
        return QRect()

    x, y, w, h = cv2.boundingRect(coords)
    return QRect(x_min + x, y_min + y, w, h)


def crop_to_content(image: QImage) -> QImage:
    """Return a copy of an image with outer transparent pixels cropped away."""
    if image.isNull():
        return QImage()
    bounds = image_content_bounds(image)
    if bounds.isEmpty():
        return image.copy()
    return image.copy(bounds)


def get_standard_qt_icon(icon_code: QStyle.StandardPixmap, style_source: Optional[QWidget] = None) -> QIcon:
    """Returns one of the standard Qt icons."""
    if style_source is None:
        style = QApplication.style()
    else:
        style = style_source.style()
    assert style is not None
    return style.standardIcon(icon_code)


TRANSPARENCY_PATTERN_BACKGROUND_DIM = 640
TRANSPARENCY_PATTERN_TILE_DIM = 16


def tile_pattern_fill(painter: QPainter,
                      bounds: QRect,
                      tile_size: int,
                      tile_color_1: QColor | Qt.GlobalColor,
                      tile_color_2: QColor | Qt.GlobalColor) -> None:
    """Draws an alternating tile pattern onto a painter."""
    fill_pixmap_size = tile_size * 2
    fill_pixmap = QPixmap(QSize(fill_pixmap_size, fill_pixmap_size))
    fill_pixmap.fill(tile_color_1)
    tile_painter = QPainter(fill_pixmap)
    for x in range(tile_size, fill_pixmap_size + tile_size, tile_size):
        for y in range(tile_size, fill_pixmap_size + tile_size, tile_size):
            if (x % (tile_size * 2)) == (y % (tile_size * 2)):
                continue
            tile_painter.fillRect(x - tile_size, y - tile_size, tile_size, tile_size, tile_color_2)
    tile_painter.end()
    painter.drawTiledPixmap(bounds, fill_pixmap)


def get_transparency_tile_pixmap(size: Optional[QSize] = None) -> QPixmap:
    """Returns a tiling pixmap used to represent transparency."""
    initial_size = size
    min_tile_size = TRANSPARENCY_PATTERN_TILE_DIM * 2
    if size is None:
        size = QSize(TRANSPARENCY_PATTERN_BACKGROUND_DIM, TRANSPARENCY_PATTERN_BACKGROUND_DIM)
        initial_size = size
    elif size.width() < min_tile_size or size.height() < min_tile_size:
        width = max(min_tile_size, size.width())
        height = max(min_tile_size, size.height())
        size = QSize(width, height)
    transparency_pixmap = QPixmap(size)
    painter = QPainter(transparency_pixmap)
    tile_pattern_fill(painter, transparency_pixmap.rect(), TRANSPARENCY_PATTERN_TILE_DIM, Qt.GlobalColor.lightGray,
                      Qt.GlobalColor.darkGray)
    painter.end()
    if initial_size != size:
        return transparency_pixmap.scaled(initial_size)
    return transparency_pixmap


def image_data_as_numpy_8bit(image: QImage) -> NpAnyArray:
    """Returns a numpy array interface for a QImage's internal data buffer."""
    assert image.format() in (QImage.Format.Format_ARGB32_Premultiplied, QImage.Format.Format_ARGB32), \
        f'Image must be pre-converted to ARGB32 or ARGB32_premultiplied, format was {image.format()}'
    image_ptr = image.bits()
    if image_ptr is None:
        raise ValueError('Invalid image parameter')
    return np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)


def image_data_as_numpy_8bit_readonly(image: QImage) -> NpAnyArray:
    """Returns a numpy array interface for a QImage's internal data buffer."""
    assert image.format() == QImage.Format.Format_ARGB32_Premultiplied, \
        f'Image must be pre-converted to ARGB32_premultiplied, format was {image.format()}'
    image_ptr = image.constBits()
    if image_ptr is None:
        raise ValueError('Invalid image parameter')
    return np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)


def numpy_8bit_to_qimage(np_image: NpAnyArray) -> QImage:
    """Create a new QImage from numpy image data."""
    height, width, channel = np_image.shape
    assert channel == 4, f'Expected ARGB32 image, but found {channel} channels'
    return QImage(np_image.data, width, height, QImage.Format.Format_ARGB32_Premultiplied)


def numpy_bounds_index(np_image: NpAnyArray, bounds: QRect) -> NpAnyArray:
    """Gets a numpy array that points to a smaller region within a larger array."""
    assert not bounds.isEmpty() and bounds.isValid(), f'invalid bounds {bounds}, array shape={np_image.shape}'
    if bounds.x() == 0 and bounds.y() == 0 and bounds.height() == np_image.shape[0] \
            and bounds.width() == np_image.shape[1]:
        return np_image
    left = bounds.x()
    top = bounds.y()
    right = left + bounds.width()
    bottom = top + bounds.height()
    assert top >= 0 and bottom <= np_image.shape[0] and left >= 0 and right <= np_image.shape[1], \
        f'bounds ({left},{top})->({right},{bottom}) not contained within shape {np_image.shape}'
    return np_image[top:bottom, left:right, :]


def numpy_intersect(arr1: NpAnyArray, arr2: NpAnyArray,
                    x: int = 0, y: int = 0) -> tuple[NpAnyArray, NpAnyArray] | tuple[None, None]:
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


def get_color_icon(color: QColor | Qt.GlobalColor, size: Optional[QSize] = None) -> QPixmap:
    """Returns a pixmap icon representing a color."""
    if size is None or size.isEmpty():
        size = QSize(ICON_SIZE, ICON_SIZE)
    if isinstance(color, Qt.GlobalColor):
        color = QColor(color)
    if color.alpha() < 255:
        pixmap = get_transparency_tile_pixmap(size)
        painter = QPainter(pixmap)
        painter.fillRect(QRect(QPoint(), size), color)
    else:
        pixmap = QPixmap(size)
        pixmap.fill(color)
        painter = QPainter(pixmap)
    painter.setPen(Qt.GlobalColor.black if color.lightness() > 128 else Qt.GlobalColor.white)
    painter.drawRect(QRect(QPoint(), size).adjusted(0, 0, -1, -1))
    painter.end()
    return pixmap


def temp_image_path(image_name: Optional[str], image_or_draw_fn: Callable[[], QImage] | QImage) -> str:
    """Creates or loads a temporary image with a particular filename."""
    global temp_image_dir
    if temp_image_dir == '':
        temp_image_dir = tempfile.mkdtemp()
    if image_name is None:
        image_name = f'{uuid.uuid4()}.png'
    img_path = os.path.join(temp_image_dir, f'{image_name}.png')
    if os.path.isfile(img_path):
        return img_path
    if isinstance(image_or_draw_fn, QImage):
        image = image_or_draw_fn
    else:
        image = image_or_draw_fn()
    image.save(img_path)
    return img_path


def temp_rich_text_image(image_name: str, image_draw_fn: Callable[[], QImage]) -> str:
    """Create a string that can embed an image into rich text by writing the image to temporary storage.  If called
       multiple times with the same image_name, the same image will be reused."""
    img_path = temp_image_path(image_name, image_draw_fn)
    return f'<img src="{img_path}"/>'


def numpy_source_over_composition(source: NpUInt8Array, destination: NpUInt8Array) -> None:
    """ Performs a source-over image composition operation on two premultiplied ARGB images of equal size, writing
    changes directly to the destination image."""
    assert source.shape == destination.shape, f'Image shape mismatch: {source.shape} != {destination.shape}'
    alpha_unchanged = source[:, :, 3] == destination[:, :, 3]
    src_full_alpha = source[:, :, 3] == 0
    dst_full_alpha = destination[:, :, 3] == 0

    # where the source is fully transparent, completely clear the destination:
    destination[src_full_alpha, :] = 0

    # where the destination is fully transparent and the source isn't, completely override the destination
    # with the source:
    source_overrides = dst_full_alpha & ~src_full_alpha
    destination[source_overrides, :] = source[source_overrides, :]

    # where both images are not fully transparent and both images have differing opacity, re-multiply color
    # channels:
    re_multiply = ~src_full_alpha & ~dst_full_alpha & ~alpha_unchanged
    for c in range(3):
        destination[re_multiply, c] = (destination[re_multiply, c]
                                       / (destination[re_multiply, 3] / 255)
                                       * (source[re_multiply, 3] / 255))

    # apply source alpha across the image:
    destination[~alpha_unchanged, 3] = source[~alpha_unchanged, 3]


def np_composite_with_mask(source: NpUInt8Array, destination: NpUInt8Array, mask: NpUInt8Array) -> None:
    """ Performs an image composition operation on two premultiplied ARGB images of equal size, writing
    changes directly to the destination image, and using a mask of equal size to further restrict compositing based on
    the mask alpha channel."""
    alpha_mask = mask[:, :, 3] / 255.0

    # Where the mask is 100% opaque, the source completely overrides the destination:
    full_alpha = alpha_mask[:, :] == 1.0
    destination[full_alpha, :] = source[full_alpha, :]

    # Where the mask has partial alpha, fade between source and destination based on mask alpha level:
    partial_alpha = (alpha_mask[:, :] > 0) & (~full_alpha)
    if np.any(partial_alpha):
        destination[partial_alpha, :] = (source[partial_alpha, :] * alpha_mask[partial_alpha, None]
                                         + destination[partial_alpha, :] * (1 - alpha_mask[partial_alpha, None]))
