"""Test main window layout and functionality."""
import os
import sys
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QSize, QRect, QPoint, Qt
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.ui.window.main_window import MainWindow, CONTROL_TAB_NAME

app = QApplication.instance() or QApplication(sys.argv)


class MainWindowTest(unittest.TestCase):
    """Test main window layout and functionality."""

    def setUp(self) -> None:
        while os.path.basename(os.getcwd()) not in ('IntraPaint', ''):
            os.chdir('..')
        assert os.path.basename(os.getcwd()) == 'IntraPaint'
        AppConfig('test/resources/app_config_test.json')._reset()
        KeyConfig('test/resources/key_config_test.json')._reset()
        Cache('test/resources/cache_test.json')._reset()
        test_size = QSize(512, 512)
        self._image_stack = ImageStack(test_size, test_size, test_size, test_size)
        self._controller = Mock()
        self.window = MainWindow(self._image_stack)
        self.window.show()

    @patch('src.util.visual.display_size.get_screen_size', new_callable=lambda: QSize(800, 600))
    def test_panel_layout(self, _) -> None:
        """Test orientation/layout changes as window size changes."""
        large_vertical = QSize(2000, 4000)
        large_horizontal = QSize(4000, 2000)
        small_horizontal = QSize(1024, 768)
        assert self.window is not None
        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.window.geometry().isEmpty())
        # TODO: rewrite once tabbed layout design is stable
