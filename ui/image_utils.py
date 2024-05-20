"""Adds general-purpose utility functions for manipulating image data"""

import io
from PIL import Image
from PyQt5.QtGui import QImage
from PyQt5.QtCore import QBuffer


def pil_image_to_qimage(pil_image: Image.Image) -> QImage:
    """Convert a PIL Image to a RGB888 formatted PyQt5 QImage."""
    if isinstance(pil_image, Image.Image):
        return QImage(pil_image.tobytes("raw","RGB"),
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
