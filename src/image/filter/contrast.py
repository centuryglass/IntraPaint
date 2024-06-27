"""Adjust image brightness/contrast."""
from typing import List
from PIL import Image, ImageEnhance
from PyQt5.QtGui import QImage
from src.util.image_utils import qimage_to_pil_image, pil_image_to_qimage
from src.util.parameter import Parameter, TYPE_FLOAT

BRIGHTNESS_CONTRAST_FILTER_TITLE = 'Brightness/Contrast'
BRIGHTNESS_CONTRAST_FILTER_DESCRIPTION = 'Adjust image brightness and contrast.'

BRIGHTNESS_LABEL = 'Brightness:'
CONTRAST_LABEL = 'Contrast'

def contrast(image: QImage, brightness: float, contrast: float) -> QImage:
    """Blurs an image."""
    pil_image = qimage_to_pil_image(image)
    pil_image = ImageEnhance.Brightness(pil_image).enhance(brightness)
    pil_image = ImageEnhance.Contrast(pil_image).enhance(contrast)
    return pil_image_to_qimage(pil_image)

def get_contrast_params() -> List[Parameter]:
    """Return parameter definitions for the brightness/contrast filter."""
    return [
        Parameter(BRIGHTNESS_LABEL,
                TYPE_FLOAT,
                1.0,
                '',
                0.0,
                50.0,
                0.5),
        Parameter(CONTRAST_LABEL,
                TYPE_FLOAT,
                1.0,
                '',
                0.0,
                50.0,
                0.5),
    ]
