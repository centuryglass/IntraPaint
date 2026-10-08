"""Image exchange with the system clipboard, tracking images IntraPaint itself wrote.

Copied images are also kept in the ImageStack copy buffer, so an internal paste can restore transforms; the system
clipboard makes the same image available to other programs, and brings images copied elsewhere in. Ownership is
tracked with a custom clipboard format that only exists while the content set by `set_clipboard_image` is still on the
clipboard: any other program or clipboard owner that replaces the content replaces the formats with it.
"""
from typing import Optional

from PySide6.QtCore import QMimeData
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

# Custom clipboard format marking image content written by set_clipboard_image. Must stay namespaced to IntraPaint,
# since every format set here is offered to other programs while IntraPaint owns the clipboard.
_OWNERSHIP_MARKER = 'application/x-intrapaint-image-copy'


def set_clipboard_image(image: QImage) -> None:
    """Places an image on the system clipboard, marked so paste can recognize it as IntraPaint's own copy."""
    mime_data = QMimeData()
    mime_data.setImageData(image)
    mime_data.setData(_OWNERSHIP_MARKER, b'1')
    QApplication.clipboard().setMimeData(mime_data)


def clipboard_has_image() -> bool:
    """Returns whether the system clipboard currently holds image data."""
    return QApplication.clipboard().mimeData().hasImage()


def get_clipboard_image() -> Optional[QImage]:
    """Returns the image on the system clipboard, or None if the clipboard holds none."""
    image = QApplication.clipboard().image()
    return None if image.isNull() else image


def clipboard_image_is_own_copy() -> bool:
    """Returns whether the system clipboard holds an image written by set_clipboard_image."""
    mime_data = QApplication.clipboard().mimeData()
    return mime_data.hasImage() and mime_data.hasFormat(_OWNERSHIP_MARKER)
