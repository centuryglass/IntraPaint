"""Tests how KeyHintLabel draws its keycap."""
import re
import sys

from PySide6.QtCore import QPoint
from shiboken6 import delete as sip_delete
from PySide6.QtGui import QImage, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.ui.widget.key_hint_label import KeyHintLabel
from src.util.visual.keycap import KEYCAP_DEPTH
from src.util.visual.text_drawing_utils import rich_text_key_hint
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class KeyHintLabelTest(IntraPaintTestCase):
    """Renders a KeyHintLabel at its preferred size."""

    def test_keycap_colors(self) -> None:
        """The keycap is filled with the window text color, with an ink outline and an ink shadow along its bottom."""
        label = KeyHintLabel('W')
        label.resize(label.sizeHint())
        palette = label.palette()
        ink = palette.color(QPalette.ColorRole.Shadow)
        image = label.grab().toImage()
        center_x = label.width() // 2
        self.assertEqual(image.pixelColor(QPoint(center_x, 0)), ink)
        self.assertEqual(image.pixelColor(QPoint(2, label.height() // 2)), palette.color(QPalette.ColorRole.WindowText))
        window = palette.color(QPalette.ColorRole.Window)
        bottom = max(y for y in range(label.height()) if image.pixelColor(QPoint(center_x, y)) != window)
        for y in range(bottom - KEYCAP_DEPTH, bottom + 1):
            self.assertEqual(image.pixelColor(QPoint(center_x, y)), ink)
        self.assertEqual(image.pixelColor(QPoint(center_x, bottom - KEYCAP_DEPTH - 1)),
                         palette.color(QPalette.ColorRole.WindowText))

    def test_config_connections_end_with_parent_deletion(self) -> None:
        """Deleting the label's parent removes its config registrations."""
        config_key = KeyConfig.SELECTION_ADD_MODIFIER
        parent = QWidget()
        label = KeyHintLabel(config_key=config_key, parent=parent)
        self.assertIn(label, KeyConfig()._connected[config_key])
        self.assertIn(label, AppConfig()._connected[AppConfig.KEY_HINT_FONT_SIZE])
        sip_delete(parent)
        self.assertNotIn(label, KeyConfig()._connected[config_key])
        self.assertNotIn(label, AppConfig()._connected[AppConfig.KEY_HINT_FONT_SIZE])

    def test_text_uses_shadow_color(self) -> None:
        """Key text is drawn in the shadow color, to contrast with the keycap fill."""
        self.assertIn(QApplication.palette().color(QPalette.ColorRole.Shadow).name(), KeyHintLabel('W').text())


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
                         palette.color(QPalette.ColorRole.WindowText))
        self.assertEqual(image.pixelColor(QPoint(image.width() // 2, image.height() - 1)),
                         palette.color(QPalette.ColorRole.Shadow))
