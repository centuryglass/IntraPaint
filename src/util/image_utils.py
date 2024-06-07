"""Adds general-purpose utility functions for manipulating image data"""
from typing import Optional
import base64
import io
import logging
from PIL import Image
from PyQt5.QtGui import QImage, QIcon
from PyQt5.QtCore import QBuffer, QRect
import numpy as np
from PyQt5.QtWidgets import QStyle, QWidget, QApplication

logger = logging.getLogger(__name__)


def pil_image_to_qimage(pil_image: Image.Image) -> QImage:
    """Convert a PIL Image to a RGB888 formatted PyQt5 QImage."""
    if isinstance(pil_image, Image.Image):
        return QImage(pil_image.tobytes("raw", "RGB"),
                      pil_image.width,
                      pil_image.height,
                      pil_image.width * 3,
                      QImage.Format_RGB888)
    raise TypeError("Invalid PIL Image parameter.")


def qimage_to_pil_image(qimage: QImage) -> Image.Image:
    """Convert a PyQt5 QImage to a PIL image, in PNG format."""
    if isinstance(qimage, QImage):
        buffer = QBuffer()
        buffer.open(QBuffer.ReadWrite)
        qimage.save(buffer, "PNG")
        pil_im = Image.open(io.BytesIO(buffer.data()))
        return pil_im
    raise TypeError("Invalid QImage parameter.")


def load_image_from_base64(image_str: str) -> Image.Image:
    """Initialize a PIL image object from base64-encoded string data."""
    if image_str.startswith(BASE_64_PREFIX):
        image_str = image_str[len(BASE_64_PREFIX):]
    return Image.open(io.BytesIO(base64.b64decode(image_str)))


BASE_64_PREFIX = 'data:image/png;base64,'


def image_to_base64(pil_image: Image.Image, include_prefix=False) -> str:
    """Convert a PIL image to a base64 string."""
    if isinstance(pil_image, str):
        pil_image = Image.open(pil_image)
    buffer = io.BytesIO()
    pil_image.save(buffer, format='PNG')
    image_str = str(base64.b64encode(buffer.getvalue()), 'utf-8')
    if include_prefix:
        image_str = BASE_64_PREFIX + image_str
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
        image_ptr.setsize(image.byteCount())
        np_image = np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)
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
    left = min_content_column
    top = min_content_row
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


def get_standard_qt_icon(icon_code: int, style_source: Optional[QWidget] = None) -> QIcon:
    """Returns one of the standard Qt icons."""
    if style_source is None:
        style = QApplication.style()
    else:
        style = style_source.style()
    return style.standardIcon(icon_code)
