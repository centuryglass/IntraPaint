"""Image exchange with the system clipboard, tracking images IntraPaint itself wrote.

Copied images are also kept in the ImageStack copy buffer, so an internal paste can restore transforms; the system
clipboard makes the same image available to other programs, and brings images copied elsewhere in. Ownership is
tracked with a custom clipboard format that only exists while the content set by `set_clipboard_image` is still on the
clipboard: any other program or clipboard owner that replaces the content replaces the formats with it. The format holds
a token unique to this process, so an image copied in another IntraPaint instance counts as a foreign image.
"""
import uuid
from typing import Optional

from PySide6.QtCore import QMimeData
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

# Custom clipboard format marking image content written by set_clipboard_image. Must stay namespaced to IntraPaint,
# since every format set here is offered to other programs while IntraPaint owns the clipboard.
_OWNERSHIP_MARKER = 'application/x-intrapaint-image-copy'
_PROCESS_TOKEN = uuid.uuid4().bytes


def set_clipboard_image(image: QImage) -> None:
    """Places an image on the system clipboard, marked so paste can recognize it as IntraPaint's own copy."""
    mime_data = QMimeData()
    mime_data.setImageData(image)
    mime_data.setData(_OWNERSHIP_MARKER, _PROCESS_TOKEN)
    QApplication.clipboard().setMimeData(mime_data)


def clipboard_has_image() -> bool:
    """Returns whether the system clipboard currently holds image data."""
    mime_data = QApplication.clipboard().mimeData()
    return mime_data is not None and mime_data.hasImage()


def get_clipboard_image() -> Optional[QImage]:
    """Returns the image on the system clipboard, or None if the clipboard holds none."""
    image = QApplication.clipboard().image()
    return None if image.isNull() else image


def clipboard_image_is_own_copy() -> bool:
    """Returns whether the system clipboard holds an image written by set_clipboard_image in this process."""
    mime_data = QApplication.clipboard().mimeData()
    return (mime_data is not None and mime_data.hasImage()
            and mime_data.data(_OWNERSHIP_MARKER).data() == _PROCESS_TOKEN)
