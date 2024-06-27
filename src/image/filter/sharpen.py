"""Define image sharpening functions."""
from typing import List
from PIL import Image, ImageEnhance
from PyQt5.QtGui import QImage
from src.util.image_utils import qimage_to_pil_image, pil_image_to_qimage
from src.util.parameter import Parameter, TYPE_FLOAT

SHARPEN_FILTER_TITLE = 'Sharpen'
SHARPEN_FILTER_DESCRIPTION = 'Sharpen the image'

FACTOR_LABEL = 'Factor'
FACTOR_DESCRIPTION = 'Sharpness factor (1.0: no change)'

def sharpen(image: QImage, factor: float) -> QImage:
    """Sharpens an image."""
    pil_image = qimage_to_pil_image(image)
    enhancer = ImageEnhance.Sharpness(pil_image)
    return pil_image_to_qimage(enhancer.enhance(factor))

def get_sharpen_params() -> List[Parameter]:
    """Return parameter definitions for the sharpen filter."""
    return [
        Parameter(FACTOR_LABEL, TYPE_FLOAT, 2.0, FACTOR_DESCRIPTION)
    ]
