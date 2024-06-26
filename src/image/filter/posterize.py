"""Simplify images by reducing color count."""
from typing import List

from PIL import Image, ImageOps
from PyQt5.QtCore import QRect
from PyQt5.QtGui import QImage, QPainter

from src.util.image_utils import qimage_to_pil_image, pil_image_to_qimage
from src.util.parameter import Parameter, TYPE_INT

POSTERIZE_FILTER_TITLE = 'Posterize'
POSTERIZE_FILTER_DESCRIPTION = 'Reduce color range by reducing image color bit count.'
PARAM_LABEL = 'Bit Count:'
PARAM_TEXT = 'Image color bits to preserve (1-8)'


def posterize(image: QImage, bits: int) -> QImage:
    """Reduce color depth within an image.

    Parameters
    ----------
    image: QImage | Image.Image
        Source image to adjust.
    bits: int
        The color channel bit count to keep. must be 1-8 inclusive.
    preserve_transparency: Whether transparency from the source image should be preserved.
    """
    assert 0 < bits <= 8, f'Invalid bit count {bits}'
    pil_image = qimage_to_pil_image(image).convert('RGB')
    posterized = ImageOps.posterize(pil_image, bits)
    filtered_image = pil_image_to_qimage(posterized)
    # Preserve transparency:
    painter = QPainter(filtered_image)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationAtop)
    painter.drawImage(QRect(0, 0, image.width(), image.height()), image)
    painter.end()
    return filtered_image


def get_posterize_params() -> List[Parameter]:
    """Return parameter definitions for the posterize filter."""
    return [Parameter(PARAM_LABEL, TYPE_INT, 3, PARAM_TEXT, 1, 8, 1 )]
