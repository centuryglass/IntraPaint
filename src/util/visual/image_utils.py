"""Adds general-purpose utility functions for manipulating image data"""
import base64
import io
import logging
import os
import tempfile
from typing import Optional, Any, Tuple, TypeAlias, Callable

# noinspection PyPackageRequirements
import cv2
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
    image.fill(Qt.GlobalColor.transparent)
    return image


def image_is_fully_transparent(image: QImage | QPixmap | NpAnyArray) -> bool:
    """Returns whether all pixels in the image are 100% transparent."""
    if isinstance(image, QPixmap):
        image = image.toImage()
    if isinstance(image, QImage):
        if not image.hasAlphaChannel():
            return False
        if image.format() != QImage.Format.Format_ARGB32_Premultiplied:
            image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        image = image_data_as_numpy_8bit(image)
    return not (image[:, :, 3] > 0).any()


def image_is_fully_opaque(image: QImage) -> bool:
    """Returns whether all pixels in the image are 100% opaque."""
    if isinstance(image, QPixmap):
        image = image.toImage()
    if isinstance(image, QImage):
        if not image.hasAlphaChannel():
            return True
        if image.format() != QImage.Format.Format_ARGB32_Premultiplied:
            image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        image = image_data_as_numpy_8bit(image)
    return not (image[:, :, 3] < 255).any()


def image_has_partial_alpha(image: QImage) -> bool:
    """Returns whether the image contains pixels with any opacity other than 0 or 255"""
    return not image_is_fully_transparent(image) and not image_is_fully_opaque(image)


def qimage_from_base64(image_str: str) -> QImage:
    """Returns a QImage from base64-encoded string data."""
    if image_str.startswith(BASE_64_PREFIX):
        image_str = image_str[len(BASE_64_PREFIX):]
    image_data = QByteArray.fromBase64(image_str.encode())
    image = QImage.fromData(image_data, 'PNG')
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
        image.save(buffer, 'PNG')
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
        y_max = np_image.shape[0]
        x_max = np_image.shape[1]
    content_rows = np.any(np_image[:, :, 3] > alpha_threshold, axis=1)
    if not np.any(content_rows):
        return QRect()
    content_columns = np.any(np_image[:, :, 3] > alpha_threshold, axis=0)
    min_content_row = y_min + np.argmax(content_rows)
    max_content_row = y_max - np.argmax(np.flip(content_rows)) - 1
    min_content_column = x_min + np.argmax(content_columns)
    max_content_column = x_max - np.argmax(np.flip(content_columns)) - 1
    if search_bounds is None:
        search_bounds = QRect(0, 0, np_image.shape[1], np_image.shape[0])
    left = int(min_content_column)
    top = int(min_content_row)
    width = max_content_column - min_content_column + 1
    height = max_content_row - min_content_row + 1
    logger.debug(f'image_content_bounds: searched {search_bounds.width()}x{search_bounds.height()} region at '
                 f'({search_bounds.x()},{search_bounds.y()}) in a {np_image.shape[1]}x{np_image.shape[0]} image, found '
                 f'content bounds {width}x{height} at ({left},{top})')
    if width <= 0 or height <= 0:
        return QRect()
    bounds = QRect(left, top, width, height)
    assert search_bounds.contains(bounds)
    return bounds


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


def tile_pattern_fill(pixmap: QPixmap,
                      tile_size: int,
                      tile_color_1: QColor | Qt.GlobalColor,
                      tile_color_2: QColor | Qt.GlobalColor) -> None:
    """Draws an alternating tile pattern onto a QPixmap."""
    fill_pixmap_size = tile_size * 2
    fill_pixmap = QPixmap(QSize(fill_pixmap_size, fill_pixmap_size))
    fill_pixmap.fill(tile_color_1)
    painter = QPainter(fill_pixmap)
    for x in range(tile_size, fill_pixmap_size + tile_size, tile_size):
        for y in range(tile_size, fill_pixmap_size + tile_size, tile_size):
            if (x % (tile_size * 2)) == (y % (tile_size * 2)):
                continue
            painter.fillRect(x - tile_size, y - tile_size, tile_size, tile_size, tile_color_2)
    painter.end()
    painter = QPainter(pixmap)
    painter.drawTiledPixmap(0, 0, pixmap.width(), pixmap.height(), fill_pixmap)
    painter.end()


def get_transparency_tile_pixmap(size: Optional[QSize] = None) -> QPixmap:
    """Returns a tiling pixmap used to represent transparency."""
    if size is None:
        size = QSize(TRANSPARENCY_PATTERN_BACKGROUND_DIM, TRANSPARENCY_PATTERN_BACKGROUND_DIM)
    transparency_pixmap = QPixmap(size)
    tile_pattern_fill(transparency_pixmap, TRANSPARENCY_PATTERN_TILE_DIM, Qt.GlobalColor.lightGray,
                      Qt.GlobalColor.darkGray)
    return transparency_pixmap


def flood_fill(image: QImage, pos: QPoint, color: QColor, threshold: float, in_place: bool = False) -> Optional[QImage]:
    """Returns a mask image marking all areas of similar color directly connected to a point in an image.

    Parameters
    ----------
        image: QImage
            Source image, in format Format_ARGB32_Premultiplied.
        pos: QPoint
            Seed point for the fill operation.
        color: QColor
            Color used to draw filled pixels in the final mask image.
        threshold: float
            Maximum color difference to ignore when determining which pixels to fill.
        in_place: bool, default=False
            If True, modify the image in-place and do not return a mask.
    Returns
    -------
        mask: Optional[QImage]
            Mask image marking the area to be filled, returned only if in_place=False. The mask image will be the same
            size as the source image. filled pixels will be set to the color parameter, while unfilled pixels will be
            fully transparent.
    """
    un_multiplied_image = image.convertToFormat(QImage.Format.Format_ARGB32)
    np_image = image_data_as_numpy_8bit(un_multiplied_image)
    np_color = np.array(np_image[pos.y(), pos.x(), :], dtype=np_image.dtype).reshape(1, 1, 4)
    diff = np.linalg.norm(np_image - np_color, axis=-1)
    diff = np.clip(diff, 0, 255).astype(np.uint8)
    within_threshold = np.zeros((image.height() + 2, image.width() + 2), np.uint8)
    seed_point = (pos.x(), pos.y())
    cv2.floodFill(diff, within_threshold, seed_point, 255, loDiff=threshold, upDiff=threshold,
                  flags=cv2.FLOODFILL_MASK_ONLY)
    within_threshold = within_threshold[1:-1, 1:-1]
    # Convert color to premultiplied ARGB to match the image color format:
    paint_color = [int(color.blue() * color.alphaF()), int(color.green() * color.alphaF()),
                   int(color.red() * color.alphaF()), color.alpha()]
    np_paint_color = np.array(paint_color, dtype=np_image.dtype).reshape(1, 1, 4)
    if in_place:
        np_image = image_data_as_numpy_8bit(image)
        np_image[within_threshold == 1, :] = np_paint_color
        return None
    mask_image = create_transparent_image(image.size())
    np_mask_image = image_data_as_numpy_8bit(mask_image)
    np_mask_image[within_threshold == 1, :] = np_paint_color
    return mask_image


def color_fill(image: QImage, color: QColor, threshold: float) -> QImage:
    """Return an image mask marking all pixels where the color value matches a given color within a threshold range."""
    un_multiplied_image = image.convertToFormat(QImage.Format.Format_ARGB32)
    np_image = image_data_as_numpy_8bit(un_multiplied_image)
    # Convert color to premultiplied ARGB to match the image color format:
    color = [int(color.blue() * color.alphaF()), int(color.green() * color.alphaF()), int(color.red() * color.alphaF()),
             color.alpha()]
    np_color = np.array(color, dtype=np_image.dtype).reshape(1, 1, 4)
    diff = np.linalg.norm(np_image - np_color, axis=-1)
    within_threshold = diff <= threshold
    mask_image = create_transparent_image(image.size())
    np_mask_image = image_data_as_numpy_8bit(mask_image)
    np_mask_image[within_threshold, 3] = 255
    return mask_image


def image_data_as_numpy_8bit(image: QImage) -> NpAnyArray:
    """Returns a numpy array interface for a QImage's internal data buffer."""
    assert image.format() in (QImage.Format.Format_ARGB32_Premultiplied, QImage.Format.Format_ARGB32), \
        f'Image must be pre-converted to ARGB32_premultiplied, format was {image.format()}'
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
    left = bounds.x()
    top = bounds.y()
    right = left + bounds.width()
    bottom = top + bounds.height()
    assert top >= 0 and bottom <= np_image.shape[0] and left >= 0 and right <= np_image.shape[1], \
        f'bounds ({left},{top})->({right},{bottom}) not contained within shape {np_image.shape}'
    return np_image[top:bottom, left:right, :]


def numpy_intersect(arr1: NpAnyArray, arr2: NpAnyArray,
                    x: int = 0, y: int = 0) -> Tuple[NpAnyArray, NpAnyArray] | Tuple[None, None]:
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


def temp_image_path(image_name: str, image_draw_fn: Callable[[], QImage]) -> str:
    """Creates or loads a temporary image with a particular filename."""
    global temp_image_dir
    if temp_image_dir == '':
        temp_image_dir = tempfile.mkdtemp()
    img_path = os.path.join(temp_image_dir, f'{image_name}.png')
    if os.path.isfile(img_path):
        return img_path
    image = image_draw_fn()
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
