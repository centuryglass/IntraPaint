"""Tests how KeyHintLabel draws its keycap."""
import re
import sys

from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage, QPalette
from PySide6.QtWidgets import QApplication

from src.ui.widget.key_hint_label import KeyHintLabel
from src.util.visual.keycap import KEYCAP_DEPTH, KEYCAP_FILL, KEYCAP_TEXT
from src.util.visual.text_drawing_utils import rich_text_key_hint
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class KeyHintLabelTest(IntraPaintTestCase):
    """Renders a KeyHintLabel at its preferred size."""

    def test_keycap_colors(self) -> None:
        """The keycap is filled white, with an ink outline and an ink shadow along its bottom."""
        label = KeyHintLabel('W')
        label.resize(label.sizeHint())
        palette = label.palette()
        ink = palette.color(QPalette.ColorRole.Shadow)
        image = label.grab().toImage()
        center_x = label.width() // 2
        self.assertEqual(image.pixelColor(QPoint(center_x, 0)), ink)
        self.assertEqual(image.pixelColor(QPoint(2, label.height() // 2)), KEYCAP_FILL)
        window = palette.color(QPalette.ColorRole.Window)
        bottom = max(y for y in range(label.height()) if image.pixelColor(QPoint(center_x, y)) != window)
        for y in range(bottom - KEYCAP_DEPTH, bottom + 1):
            self.assertEqual(image.pixelColor(QPoint(center_x, y)), ink)
        self.assertEqual(image.pixelColor(QPoint(center_x, bottom - KEYCAP_DEPTH - 1)),
                         KEYCAP_FILL)

    def test_text_is_black(self) -> None:
        """Key text is black, to contrast with the white keycap fill."""
        self.assertIn(KEYCAP_TEXT.name(), KeyHintLabel('W').text())


class KeycapImageTest(IntraPaintTestCase):
    """Checks that inline keycap images share the label's look."""

    def test_image_matches_label(self) -> None:
        """A keycap image has the label's fill and outline colors."""
        path = re.search(r'src="([^"]+)"', rich_text_key_hint('W'))
        assert path is not None
        image = QImage(path.group(1))
        palette = QApplication.palette()
        self.assertEqual(image.pixelColor(QPoint(image.width() // 2, 0)), palette.color(QPalette.ColorRole.Shadow))
        self.assertEqual(image.pixelColor(QPoint(2, image.height() // 2 - 1)),
                         KEYCAP_FILL)
        self.assertEqual(image.pixelColor(QPoint(image.width() // 2, image.height() - 1)),
                         palette.color(QPalette.ColorRole.Shadow))
