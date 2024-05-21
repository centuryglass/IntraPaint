"""Adds general-purpose utility functions for manipulating image data"""
import base64
import io
from PIL import Image
from PyQt5.QtGui import QImage
from PyQt5.QtCore import QBuffer


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


def load_image_from_base64(image_str):
    """Initialize a PIL image object from base64-encoded string data."""
    if image_str.startswith(BASE_64_PREFIX):
        image_str = image_str[len(BASE_64_PREFIX):]
    return Image.open(io.BytesIO(base64.b64decode(image_str)))


BASE_64_PREFIX = 'data:image/png;base64,'


def image_to_base64(pil_image, include_prefix=False):
    """Convert a PIL image to a base64 string."""
    if isinstance(pil_image, str):
        pil_image = Image.open(pil_image)
    buffer = io.BytesIO()
    pil_image.save(buffer, format='PNG')
    image_str = str(base64.b64encode(buffer.getvalue()), 'utf-8')
    if include_prefix:
        image_str = BASE_64_PREFIX + image_str
    return image_str
