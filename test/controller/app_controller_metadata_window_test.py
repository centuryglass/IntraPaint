"""Tests that Image > Image metadata opens a metadata window that follows the open file's metadata."""
import os
import sys
import tempfile

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from src.controller.app_controller import AppController
from src.util.arg_parser import build_arg_parser
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class AppControllerMetadataWindowTest(IntraPaintTestCase):
    """Opens the window from a mock-mode controller."""

    def setUp(self) -> None:
        super().setUp()
        args = build_arg_parser(include_edit_params=False).parse_args(['--window_size', '800x600', '--mode', 'mock'])
        args.mode = 'mock'
        args.server_url = ''
        args.fast_ngrok_connection = False
        self.controller = AppController(args)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def test_window_follows_loaded_file(self) -> None:
        """The window is reused, and shows the metadata of each file loaded while it is open."""
        path = os.path.join(self.temp_dir.name, 'plain.png')
        image = QImage(QSize(8, 8), QImage.Format.Format_ARGB32)
        image.fill(QColor('red'))
        self.assertTrue(image.save(path))
        self.controller.show_metadata_window()
        window = self.controller._metadata_window
        assert window is not None
        self.controller._image_io.metadata.text['note'] = 'first'
        self.controller.show_metadata_window()
        self.assertIs(window, self.controller._metadata_window)
        self.controller.load_image(path)
        self.assertNotIn('note', window._metadata.text)
        self.assertIs(window._metadata, self.controller._image_io.metadata)
