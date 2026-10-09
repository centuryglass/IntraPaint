"""Tests that Ink text areas have rounded corners, like the other input fields."""
import sys

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QTextEdit

from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class TextAreaFrameTest(IntraPaintTestCase):
    """The text area's square viewport must not show at the frame's corners."""

    def _assert_rounded(self, text_area: QPlainTextEdit | QTextEdit) -> None:
        text_area.resize(120, 60)
        image = text_area.grab().toImage()
        window = QApplication.palette().color(QPalette.ColorRole.Window)
        base = QApplication.palette().color(QPalette.ColorRole.Base)
        for x, y in ((0, 0), (image.width() - 1, 0), (0, image.height() - 1),
                     (image.width() - 1, image.height() - 1)):
            self.assertEqual(window.name(), image.pixelColor(x, y).name(), f'outline corner at {x},{y}')
        for x, y in ((1, 1), (image.width() - 2, 1), (1, image.height() - 2),
                     (image.width() - 2, image.height() - 2)):
            self.assertNotEqual(base.name(), image.pixelColor(x, y).name(), f'viewport corner at {x},{y}')
        self.assertEqual(base.name(), image.pixelColor(image.width() // 2, image.height() // 2).name())

    def test_plain_text_edit_has_rounded_corners(self) -> None:
        self._assert_rounded(QPlainTextEdit())

    def test_text_edit_has_rounded_corners(self) -> None:
        self._assert_rounded(QTextEdit())
