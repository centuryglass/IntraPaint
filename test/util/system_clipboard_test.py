"""Tests system clipboard image exchange, including IntraPaint's own-copy ownership marker."""
import sys
import unittest

from PySide6.QtCore import QMimeData, QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from src.util.system_clipboard import _OWNERSHIP_MARKER, clipboard_has_image, clipboard_image_is_own_copy, \
    get_clipboard_image, set_clipboard_image
from test.base_test_case import IntraPaintTestCase, assert_images_equal

app = QApplication.instance() or QApplication(sys.argv)

BASE_COLOR = QColor(120, 40, 200)
FOREIGN_COLOR = QColor(40, 200, 120)


def _filled_image(color: QColor) -> QImage:
    image = QImage(QSize(8, 8), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    return image


class SystemClipboardTest(IntraPaintTestCase):

    def test_set_clipboard_image_marks_ownership(self) -> None:
        """set_clipboard_image places a readable image on the clipboard, marked as IntraPaint's own copy."""
        image = _filled_image(BASE_COLOR)
        set_clipboard_image(image)
        self.assertTrue(clipboard_has_image())
        self.assertTrue(clipboard_image_is_own_copy())
        read_back = get_clipboard_image()
        assert read_back is not None
        assert_images_equal(read_back, image)

    def test_foreign_image_is_not_own_copy(self) -> None:
        """An image placed on the clipboard without the ownership marker isn't recognized as IntraPaint's copy."""
        image = _filled_image(FOREIGN_COLOR)
        QApplication.clipboard().setImage(image)
        self.assertTrue(clipboard_has_image())
        self.assertFalse(clipboard_image_is_own_copy())
        read_back = get_clipboard_image()
        assert read_back is not None
        assert_images_equal(read_back, image)

    def test_other_instance_image_is_not_own_copy(self) -> None:
        """An image marked by another IntraPaint process isn't recognized as this process's copy."""
        mime_data = QMimeData()
        mime_data.setImageData(_filled_image(FOREIGN_COLOR))
        mime_data.setData(_OWNERSHIP_MARKER, b'another process')
        QApplication.clipboard().setMimeData(mime_data)
        self.assertTrue(clipboard_has_image())
        self.assertFalse(clipboard_image_is_own_copy())

    def test_text_clipboard_holds_no_image(self) -> None:
        """Clipboard content without image data counts as having no image."""
        mime_data = QMimeData()
        mime_data.setText('text')
        QApplication.clipboard().setMimeData(mime_data)
        self.assertFalse(clipboard_has_image())
        self.assertIsNone(get_clipboard_image())
        self.assertFalse(clipboard_image_is_own_copy())


if __name__ == '__main__':
    unittest.main()
