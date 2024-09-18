import os
import sys
import unittest

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.tools.draw_tool import DrawTool
from src.ui.panel.image_panel import ImagePanel
from src.ui.panel.tool_panel import ToolPanel

app = QApplication.instance() or QApplication(sys.argv)


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
        self._tool_panel = ToolPanel()
        self._tool_panel.show()

    def test_add_remove_tool_button(self) -> None:
        """It should be possible to add and remove a tool button"""
        self.assertEqual(len(self._tool_panel._tool_widgets), 0)
        test_tool = DrawTool(self._image_stack, self._image_panel.image_viewer)
        self._tool_panel.add_tool_button(test_tool)
        self.assertEqual(len(self._tool_panel._tool_widgets), 1)
        self._tool_panel.remove_tool_button(test_tool)
        self.assertEqual(len(self._tool_panel._tool_widgets), 0)

    def test_avoid_duplicate_tools(self) -> None:
        """Adding the same tool or type of tool more than once should be blocked."""
        self.assertEqual(len(self._tool_panel._tool_widgets), 0)
        test_tool_1 = DrawTool(self._image_stack, self._image_panel.image_viewer)
        self._tool_panel.add_tool_button(test_tool_1)
        self.assertEqual(len(self._tool_panel._tool_widgets), 1)
        self._tool_panel.add_tool_button(test_tool_1)
        self.assertEqual(len(self._tool_panel._tool_widgets), 1)
        test_tool_2 = DrawTool(self._image_stack, self._image_panel.image_viewer)
        self._tool_panel.add_tool_button(test_tool_2)
        self.assertEqual(len(self._tool_panel._tool_widgets), 1)

    def test_add_utility_widget_tab(self) -> None:
        """ToolPanel should accept arbitrary panel widgets for the utility tab box."""
        self.assertEqual(len(self._tool_panel._utility_tab_panels), 0)
        self.assertEqual(self._tool_panel._utility_tab_panel.count(), 0)
        panel = QWidget()
        panel_name = 'test panel'
        self.assertFalse(panel.isVisible())
        self._tool_panel.add_utility_widget_tab(panel, panel_name)
        self.assertTrue(panel.isVisible())
        self.assertEqual(len(self._tool_panel._utility_tab_panels), 1)
        self.assertEqual(self._tool_panel._utility_tab_panel.count(), 1)
        self.assertEqual(self._tool_panel._utility_tab_panel.currentWidget(), panel)

    def test_activate_tool(self) -> None:
        """ToolPanel should show the panel widget and mark the button as active when a tool is activated."""
        test_tool = DrawTool(self._image_stack, self._image_panel.image_viewer)
        self._tool_panel.add_tool_button(test_tool)
        tool_button_1 = self._tool_panel._tool_widgets[test_tool.label]
        tool_button_2 = self._tool_panel._toolbar_tool_widgets[test_tool.label]
        self.assertEqual(self._tool_panel._tool_control_label.text(), '')
        self.assertIsNone(self._tool_panel._active_tool_panel)
        self.assertFalse(tool_button_1.is_active)
        self.assertFalse(tool_button_2.is_active)
        control_panel = test_tool.get_control_panel()
        assert control_panel is not None
        self.assertFalse(control_panel.isVisible())

        self._tool_panel.setup_active_tool(test_tool)
        self.assertEqual(self._tool_panel._tool_control_label.text(),
                         f'{test_tool.label} - {test_tool.get_tooltip_text()}')
        self.assertEqual(self._tool_panel._active_tool_panel, control_panel)
        self.assertTrue(tool_button_1.is_active)
        self.assertTrue(tool_button_2.is_active)
        self.assertTrue(control_panel.isVisible())
