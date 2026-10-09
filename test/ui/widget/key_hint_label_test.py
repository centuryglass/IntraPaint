"""Tests how KeyHintLabel draws its keycap."""
import sys

from PySide6.QtCore import QPoint
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from src.ui.widget.key_hint_label import KeyHintLabel, KEYCAP_DEPTH
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class KeyHintLabelTest(IntraPaintTestCase):
    """Renders a KeyHintLabel at its preferred size."""

    def test_keycap_colors(self) -> None:
        """The keycap is filled with the button color, with an ink outline and an ink shadow along its bottom."""
        label = KeyHintLabel('W')
        label.resize(label.sizeHint())
        palette = label.palette()
        ink = palette.color(QPalette.ColorRole.Shadow)
        image = label.grab().toImage()
        center_x = label.width() // 2
        self.assertEqual(image.pixelColor(QPoint(center_x, 0)), ink)
        self.assertEqual(image.pixelColor(QPoint(2, label.height() // 2)), palette.color(QPalette.ColorRole.Button))
        window = palette.color(QPalette.ColorRole.Window)
        bottom = max(y for y in range(label.height()) if image.pixelColor(QPoint(center_x, y)) != window)
        for y in range(bottom - KEYCAP_DEPTH, bottom + 1):
            self.assertEqual(image.pixelColor(QPoint(center_x, y)), ink)
        self.assertEqual(image.pixelColor(QPoint(center_x, bottom - KEYCAP_DEPTH - 1)),
                         palette.color(QPalette.ColorRole.Button))

    def test_text_uses_button_text_role(self) -> None:
        """Key text is drawn in the button text color, to contrast with the keycap fill."""
        self.assertEqual(KeyHintLabel('W').foregroundRole(), QPalette.ColorRole.ButtonText)
