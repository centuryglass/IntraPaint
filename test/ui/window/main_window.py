"""Test main window layout and functionality."""
import os
import sys
import unittest
from unittest.mock import Mock, patch

from PyQt5.QtCore import QSize, QRect, QPoint, Qt
from PyQt5.QtWidgets import QApplication

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
        self._app_config = AppConfig('test/resources/app_config_test.json')
        self._key_config = KeyConfig('test/resources/key_config_test.json')
        self._cache = Cache('test/resources/cache_test.json')
        test_size = QSize(512, 512)
        self._image_stack = ImageStack(test_size, test_size, test_size, test_size)
        self._controller = Mock()
        self.window = MainWindow(self._image_stack, self._controller)
        self.window.show()

    @patch('src.util.display_size.get_screen_size', new_callable=lambda: QSize(800, 600))
    def test_panel_layout(self, _) -> None:
        """Test orientation/layout changes as window size changes."""
        large_vertical = QSize(2000, 4000)
        large_horizontal = QSize(4000, 2000)
        small_horizontal = QSize(1024, 768)
        assert self.window is not None
        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.window.geometry().isEmpty())
        self.assertFalse(self.window._control_panel.isVisible())
        self.assertTrue(self.window._reactive_widget.isVisible())

        # Large vertical: vertical orientation, no tabs, horizontal toolbar
        self.window.setGeometry(QRect(QPoint(), large_vertical))
        self.assertEqual(self.window._main_widget.count(), 1)
        self.assertEqual(self.window._orientation, Qt.Orientation.Vertical)
        self.assertTrue(self.window._control_panel.isVisible())

        self.assertTrue(self.window._reactive_widget.isVisible())

        # check size assumptions:
        width_buffer = 800 // 30
        height_buffer = 600 // 30
        min_w_ctrl_panel = self.window._min_control_panel_size.width()
        min_h_ctrl_panel = self.window._min_vertical_window_size.height() + self.window._min_horizontal_tool_panel_size.height() \
                           + self.window._min_control_panel_size.height()
        w_show_ctrl_panel = min_w_ctrl_panel + width_buffer * 2
        h_show_ctrl_panel = min_h_ctrl_panel + height_buffer * 2
        self.assertEqual(self.window.width(), large_vertical.width())
        self.assertGreaterEqual(self.window.width(), w_show_ctrl_panel)
        self.assertGreaterEqual(self.window.height(), h_show_ctrl_panel)
        tab_names = [self.window._main_widget.tabText(i) for i in range(self.window._main_widget.count())]
        self.assertTrue(CONTROL_TAB_NAME not in tab_names)
        self.assertNotEqual(self.window._min_control_panel_size, QSize(0, 0))
        self.assertNotEqual(self.window._min_horizontal_tool_panel_size, QSize(0, 0))
        self.assertNotEqual(self.window.size(), QSize(0, 0))
        self.assertNotEqual(self.window._control_panel.size(), QSize(0, 0))
        self.assertNotEqual(self.window._tool_panel.size(), QSize(0, 0))

        # check layout item states:
        self.assertEqual(self.window._control_panel.layer_parent(), self.window._main_page_tab)
        self.assertEqual(self.window._tool_panel.layer_parent(), self.window._reactive_widget)
        self.assertFalse(self.window._tool_panel._generate_button.isVisible())
        self.assertEqual(self.window._tool_panel.orientation, Qt.Orientation.Horizontal)

        # Large horizontal:
        self.window.setGeometry(QRect(QPoint(), large_horizontal))
        self.assertEqual(self.window.size(), large_horizontal)
        self.assertEqual(self.window._main_widget.count(), 1)
        self.assertEqual(self.window._orientation, Qt.Orientation.Horizontal)
        self.assertTrue(self.window._reactive_widget is not None)
        self.assertTrue(self.window._reactive_widget.isVisible())
        self.assertEqual(self.window._reactive_widget, self.window._tool_panel.layer_parent())
        self.assertTrue(self.window._tool_panel.isVisible())
        self.assertFalse(self.window._tool_panel._generate_button.isVisible())
        self.assertEqual(self.window._tool_panel.orientation, Qt.Orientation.Vertical)

        # Small horizontal:
        self.window.setGeometry(QRect(QPoint(), small_horizontal))
        self.assertEqual(self.window._main_widget.count(), 2)
        self.assertTrue(self.window._orientation, Qt.Orientation.Horizontal)
        self.assertFalse(self.window._control_panel.isVisible())
        self.assertFalse(self.window._tool_panel.geometry().isEmpty())
        self.assertTrue(self.window._tool_panel._generate_button.isVisible())
        self.assertEqual(self.window._reactive_widget, self.window._tool_panel.layer_parent())
        self.assertEqual(self.window._tool_panel.orientation, Qt.Orientation.Vertical)