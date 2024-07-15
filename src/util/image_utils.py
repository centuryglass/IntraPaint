"""Adds general-purpose utility functions for manipulating image data"""
import base64
import io
import logging
from typing import Optional

import cv2
import numpy as np
from PIL import Image
from PyQt6.QtCore import QBuffer, QRect, QSize, Qt, QPoint, QFile, QIODevice, QByteArray
from PyQt6.QtGui import QImage, QIcon, QPixmap, QPainter, QColor
from PyQt6.QtWidgets import QStyle, QWidget, QApplication

from src.config.application_config import AppConfig
from src.image.mypaint.numpy_image_utils import AnyNpArray, image_data_as_numpy_8bit, numpy_8bit_to_qimage
from src.util.display_size import max_font_size
from src.util.geometry_utils import is_smaller_size
from src.util.shared_constants import PIL_SCALING_MODES

logger = logging.getLogger(__name__)
DEFAULT_ICON_SIZE = QSize(64, 64)


def create_transparent_image(size: QSize) -> QImage:
    """Returns a new image filled with transparency, set to the requested size."""
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    return image


def pil_image_to_qimage(pil_image: Image.Image) -> QImage:
    """Convert a PIL Image to a PyQt6 QImage."""
    if not isinstance(pil_image, Image.Image):
        raise TypeError('Invalid PIL Image parameter.')
    if pil_image.mode not in ('RGBA', 'RGB'):
        raise ValueError(f'Unsupported image mode {pil_image.mode}')
    if pil_image.mode == 'RGB':
        image = QImage(pil_image.tobytes('raw', 'RGB'),
                       pil_image.width,
                       pil_image.height,
                       pil_image.width * 3,
                       QImage.Format.Format_RGB888)
    else:  # RGBA
        image = QImage(pil_image.tobytes('raw', 'RGBA'),
                       pil_image.width,
                       pil_image.height,
                       pil_image.width * 4,
                       QImage.Format.Format_RGBA8888)
        image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    return image


def qimage_to_pil_image(qimage: QImage) -> Image.Image:
    """Convert a PyQt6 QImage to a PIL image, in PNG format."""
    if not isinstance(qimage, QImage):
        raise TypeError('Invalid QImage parameter.')
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.ReadWrite)
    qimage.save(buffer, 'PNG')
    pil_im = Image.open(io.BytesIO(buffer.data()))
    return pil_im


def pil_qsize(image: Image.Image) -> QSize:
    """Return PIL image size as QSize for easier comparison."""
    return QSize(image.width, image.height)


def pil_image_scaling(image: QImage | Image.Image, size: QSize, mode: Optional[Image.Resampling] = None) -> QImage:
    """Resize an image using a PIL scaling algorithm, returning a QImage.  If no specific scaling mode is provided,
       the appropriate scaling mode defined in AppConfig will be used."""
    image_size = image.size() if isinstance(image, QImage) else pil_qsize(image)
    if image_size == size:
        return image if isinstance(image, QImage) else pil_image_to_qimage(image)
    if isinstance(image, QImage):
        image = qimage_to_pil_image(image)
    if mode is None:
        if is_smaller_size(image_size, size):
            mode = PIL_SCALING_MODES[AppConfig().get(AppConfig.UPSCALE_MODE)]
        else:
            mode = PIL_SCALING_MODES[AppConfig().get(AppConfig.DOWNSCALE_MODE)]
    image = image.resize((size.width(), size.height()), mode)
    return pil_image_to_qimage(image)


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


def pil_image_from_base64(image_str: str) -> Image.Image:
    """Returns a PIL image object from base64-encoded string data."""
    if image_str.startswith(BASE_64_PREFIX):
        image_str = image_str[len(BASE_64_PREFIX):]
    return Image.open(io.BytesIO(base64.b64decode(image_str)))


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
        image_ptr.setsize(image.sizeInBytes())
        np_image: AnyNpArray = np.ndarray(shape=(image.height(), image.width(), 4), dtype=np.uint8, buffer=image_ptr)
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


def get_standard_qt_icon(icon_code: QStyle.StandardPixmap, style_source: Optional[QWidget] = None) -> QIcon:
    """Returns one of the standard Qt icons."""
    if style_source is None:
        style = QApplication.style()
    else:
        style = style_source.style()
    assert style is not None
    return style.standardIcon(icon_code)


def get_character_icon(character: str, color: QColor) -> QIcon:
    """Renders a character as an icon."""
    assert len(character) == 1, f'Expected a single character, got {character}'
    font = QApplication.font()
    size = DEFAULT_ICON_SIZE
    pt_size = max_font_size(character, font, size)
    font.setPointSize(pt_size)
    font.setBold(True)
    pixmap = QPixmap(size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setFont(font)
    painter.setPen(color)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.drawText(QRect(QPoint(), DEFAULT_ICON_SIZE), Qt.AlignmentFlag.AlignCenter, character)
    painter.end()
    return QIcon(pixmap)


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
    np_image = image_data_as_numpy_8bit(image)
    cv2_np_image = np_image[:, :, :3]  # cv2 won't accept 4-channel images.
    if not cv2_np_image.flags['C_CONTIGUOUS']:
        cv2_np_image = np.ascontiguousarray(cv2_np_image)
    seed_point = (pos.x(), pos.y())
    fill_color = (color.blue(), color.green(), color.red())
    height, width, _ = np_image.shape
    if in_place:
        mask = None
        flags = 0
    else:
        mask = np.zeros((height + 2, width + 2), np.uint8)
        flags = cv2.FLOODFILL_MASK_ONLY
    cv2.floodFill(cv2_np_image, mask, seed_point, fill_color,
                  loDiff=(threshold, threshold, threshold, threshold),
                  upDiff=(threshold, threshold, threshold, threshold),
                  flags=flags)
    if in_place:
        np_image[:, :, :3] = cv2_np_image
        return None
    assert mask is not None
    mask = mask[1:-1, 1:-1]  # Remove the border
    mask_image = np.zeros_like(np_image)
    mask_indices = np.where(mask == 1)
    mask_image[mask_indices[0], mask_indices[1], :3] = fill_color
    mask_image[mask_indices[0], mask_indices[1], 3] = 255  # Set alpha to 255 for filled areas
    return numpy_8bit_to_qimage(mask_image)
