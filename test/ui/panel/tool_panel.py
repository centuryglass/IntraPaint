import unittest
import sys
import os
from unittest.mock import Mock

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.ui.panel.image_panel import ImagePanel
from src.ui.panel.tool_panel import ToolPanel

app = QApplication(sys.argv)


class ToolPanelTest(unittest.TestCase):
    """Tool panel GUI testing"""

    def setUp(self) -> None:
        while os.path.basename(os.getcwd()) not in ('IntraPaint', ''):
            os.chdir('..')
        assert os.path.basename(os.getcwd()) == 'IntraPaint'
        self._app_config = AppConfig('test/resources/app_config_test.json')
        self._key_config = KeyConfig('test/resources/key_config_test.json')
        self._cache = Cache('test/resources/cache_test.json')
        test_size = QSize(512, 512)
        self._image_stack = ImageStack(test_size, test_size, test_size, test_size)
        self._image_panel = ImagePanel(self._image_stack)
        self._generate = Mock()
        self._tool_panel = ToolPanel(self._image_stack, self._image_panel, self._generate)
        self._tool_panel.show()

    def test_generate_button(self) -> None:
        """Test generate button behavior."""
        # Behavior after init:
        self._generate.assert_not_called()
        self.assertTrue(self._tool_panel.isVisible())
        self.assertTrue(not self._tool_panel._generate_button.isVisible())
        self._tool_panel.show_generate_button(True)
        self.assertTrue(self._tool_panel._generate_button.isVisible())
        self.assertEqual(self._tool_panel.orientation, Qt.Orientation.Vertical)
        self.assertEqual(self._tool_panel._generate_button.text(), 'Generate')
        QTest.mouseClick(self._tool_panel._generate_button, Qt.LeftButton)
        self._generate.assert_called()
        self._generate.reset_mock()

        # Behavior after orientation change:
        self._tool_panel.set_orientation(Qt.Orientation.Horizontal)
        self.assertTrue(self._tool_panel._generate_button.isVisible())
        self.assertEqual(self._tool_panel.orientation, Qt.Orientation.Horizontal)
        self.assertEqual(self._tool_panel._generate_button.text(), 'G\ne\nn\ne\nr\na\nt\ne')
        QTest.mouseClick(self._tool_panel._generate_button, Qt.LeftButton)
        self._generate.assert_called()
        self._generate.reset_mock()

        # Hiding button works:
        self._tool_panel.show_generate_button(False)
        self.assertTrue(not self._tool_panel._generate_button.isVisible())

        # Button remains hidden after orientation changes:
        self._tool_panel.set_orientation(Qt.Orientation.Vertical)
        self.assertTrue(not self._tool_panel._generate_button.isVisible())
        self._tool_panel.set_orientation(Qt.Orientation.Horizontal)
        self.assertTrue(not self._tool_panel._generate_button.isVisible())

        # Button can be revealed again:
        self._tool_panel.show_generate_button(True)
        self.assertTrue(self._tool_panel._generate_button.isVisible())

        # Button still works after the hide+show sequence:
        QTest.mouseClick(self._tool_panel._generate_button, Qt.LeftButton)
        self._generate.assert_called()
        self._generate.reset_mock()