"""Pins how the application style draws each standard control in every state, as text-free golden images.

`scripts/capture_ui.py` saves the same images with state and variant labels, which helps when checking a changed one.
"""
import sys

from PySide6.QtWidgets import QApplication

from test.base_test_case import IntraPaintTestCase
from test.ui.ui_capture import GALLERY_CONTROLS, render_gallery_control

app = QApplication.instance() or QApplication(sys.argv)

GOLDEN_DIR = 'test/resources/test_images/style_gallery'


class StyleGalleryTest(IntraPaintTestCase):
    """Compares each gallery control with its golden image."""

    def test_controls_match_goldens(self) -> None:
        """Each gallery control renders the same pixels as its golden image."""
        for control in GALLERY_CONTROLS:
            with self.subTest(control=control.name):
                self.assert_image_matches_golden(render_gallery_control(control), f'{GOLDEN_DIR}/{control.name}.png')
