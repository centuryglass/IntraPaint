"""Utility functions for manipulating PIL images."""
import base64
import io
from typing import Optional

from PIL import Image, ImageQt
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from src.config.application_config import AppConfig
from src.util.shared_constants import PIL_SCALING_MODES
from src.util.visual.geometry_utils import is_smaller_size
from src.util.visual.image_utils import BASE_64_PREFIX


def pil_image_to_qimage(pil_image: Image.Image) -> QImage:
    """Convert a PIL Image to a Qt6 QImage."""
    if not isinstance(pil_image, Image.Image):
        raise TypeError('Invalid PIL Image parameter.')
    if pil_image.mode not in ('RGBA', 'RGB'):
        pil_image = pil_image.convert('RGBA')
    if pil_image.mode == 'RGB':
        image = QImage(pil_image.tobytes('raw', 'RGB'),
                       pil_image.width,
                       pil_image.height,
                       pil_image.width * 3,
                       QImage.Format.Format_RGB888)
    else:  # RGBA
        assert pil_image.mode == 'RGBA', f'Unexpected PIL image mode {pil_image.mode}'
        image = QImage(pil_image.tobytes('raw', 'RGBA'),
                       pil_image.width,
                       pil_image.height,
                       pil_image.width * 4,
                       QImage.Format.Format_RGBA8888)
        image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    return image


def qimage_to_pil_image(qimage: QImage) -> Image.Image:
    """Convert a Qt6 QImage to a PIL image, in PNG format."""
    if not isinstance(qimage, QImage):
        raise TypeError('Invalid QImage parameter.')
    return ImageQt.fromqimage(qimage)


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
            mode = PIL_SCALING_MODES[AppConfig().get(AppConfig.PIL_UPSCALE_MODE)]
        else:
            mode = PIL_SCALING_MODES[AppConfig().get(AppConfig.PIL_DOWNSCALE_MODE)]
    image = image.resize((size.width(), size.height()), mode)
    return pil_image_to_qimage(image)


def pil_image_from_base64(image_str: str) -> Image.Image:
    """Returns a PIL image object from base64-encoded string data."""
    if image_str.startswith(BASE_64_PREFIX):
        image_str = image_str[len(BASE_64_PREFIX):]
    return Image.open(io.BytesIO(base64.b64decode(image_str)))
