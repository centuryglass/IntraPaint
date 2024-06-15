"""Simplify images by reducing color count."""
from PIL import Image, ImageOps
from PyQt5.QtGui import QImage

from src.util.image_utils import qimage_to_pil_image, pil_image_to_qimage


def posterize(image: QImage, bits: int, preserve_transparency: bool = True) -> QImage:
    """Reduce color depth within an image.

    Parameters
    ----------
    image: QImage | Image.Image
        Source image to adjust.
    bits: int
        Color channel bit count to keep must be 1-8 inclusive.
    preserve_transparency: Whether transparency from the source image should be preserved.
    """
    assert 0 < bits <= 8, f'Invalid bit count {bits}'
    pil_image = qimage_to_pil_image(image)
    posterized = ImageOps.posterize(pil_image, bits)
    return pil_image_to_qimage(posterized)
