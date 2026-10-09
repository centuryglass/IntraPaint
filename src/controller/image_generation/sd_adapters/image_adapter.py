"""Converts images between IntraPaint's QImages and the PIL images `sd_backend_client` takes and returns."""
from PIL import Image
from PySide6.QtGui import QImage

from src.util.visual.pil_image_utils import pil_image_to_qimage, qimage_to_pil_image


def qimage_to_pil(image: QImage) -> Image.Image:
    """Returns a straight-alpha RGBA copy of a QImage, the mode the library normalizes every image to.

    Premultiplied input is unpremultiplied, so a fully transparent pixel comes out as (0, 0, 0, 0).
    """
    pil_image = qimage_to_pil_image(image)
    if pil_image.mode != 'RGBA':
        pil_image = pil_image.convert('RGBA')
    return pil_image


def pil_to_qimage(image: Image.Image) -> QImage:
    """Returns a `Format_ARGB32_Premultiplied` copy of a PIL image, the format IntraPaint's image code expects."""
    qimage = pil_image_to_qimage(image)
    if qimage.format() != QImage.Format.Format_ARGB32_Premultiplied:
        qimage = qimage.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    return qimage
