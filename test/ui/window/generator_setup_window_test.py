"""Tests the status text `GeneratorSetupWindow` shows for the selected generator."""
import sys
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from src.controller.image_generation.null_generator import NullGenerator
from src.controller.image_generation.test_generator import TestGenerator
from src.image.layers.image_stack import ImageStack
from src.ui.window.generator_setup_window import GeneratorSetupWindow
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class GeneratorSetupWindowTest(IntraPaintTestCase):
    """Selects generators in a GeneratorSetupWindow built without AppController."""

    def setUp(self) -> None:
        super().setUp()
        size = QSize(64, 64)
        image_stack = ImageStack(size, size, size, size)
        main_window = MagicMock()
        self.window = GeneratorSetupWindow()
        self.null_generator = NullGenerator(main_window, image_stack)
        self.other_generator = TestGenerator(main_window, image_stack)
        self.window.add_generator(self.null_generator)
        self.window.add_generator(self.other_generator)

    def _status_text(self) -> str:
        return self.window._status.toPlainText()  # pylint: disable=protected-access

    def test_unavailable_generator_without_status_shows_fallback(self) -> None:
        """An unavailable generator that reported nothing still gets an unavailable message."""
        with patch.object(self.other_generator, 'is_available', return_value=False):
            self.window.select_generator(self.other_generator)
        self.assertIn('This image generator is not available', self._status_text())
