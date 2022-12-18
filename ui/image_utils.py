from PIL import Image
from PyQt5.QtGui import QImage
from PyQt5.QtCore import QBuffer
import traceback, io

"""Adds general-purpose utility functions to reuse in UI code"""

def imageToQImage(pilImage):
    """Convert a PIL Image to a RGB888 formatted PyQt5 QImage."""
    if isinstance(pilImage, Image.Image):
        return QImage(pilImage.tobytes("raw","RGB"),
                pilImage.width,
                pilImage.height,
                pilImage.width * 3,
                QImage.Format_RGB888)

def qImageToImage(qImage):
    """Convert a PyQt5 QImage to a PIL image, in PNG format."""
    if isinstance(qImage, QImage):
        buffer = QBuffer()
        buffer.open(QBuffer.ReadWrite)
        qImage.save(buffer, "PNG")
        pil_im = Image.open(io.BytesIO(buffer.data()))
        return pil_im
