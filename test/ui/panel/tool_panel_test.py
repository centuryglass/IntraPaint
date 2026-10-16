"""Tests the Tools dock's panel: buttons, grouping and sizes per size class, the active tool header, and reset."""
import sys

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.tools.draw_tool import DrawTool
from src.tools.eyedropper_tool import EyedropperTool
from src.tools.free_selection_tool import FreeSelectionTool
from src.tools.generation_area_tool import GenerationAreaTool
from src.tools.text_tool import TextTool
from src.ui.layout.panel_size_class import Orientation, SizeClass
from src.ui.panel.image_panel import ImagePanel
from src.ui.panel.tool_panel import ToolPanel, BUTTON_LAYOUTS
from src.util.visual.text_drawing_utils import get_key_display_string
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

# A dock size inside each size class, away from the boundaries:
HOST_SIZES = {
    (Orientation.SIDE, SizeClass.COMPACT): QSize(200, 600),
    (Orientation.SIDE, SizeClass.REGULAR): QSize(340, 600),
    (Orientation.SIDE, SizeClass.WIDE): QSize(500, 600),
    (Orientation.STRIP, SizeClass.COMPACT): QSize(1200, 120),
    (Orientation.STRIP, SizeClass.REGULAR): QSize(1200, 240),
    (Orientation.STRIP, SizeClass.WIDE): QSize(1200, 400),
}


class ToolPanelTest(IntraPaintTestCase):
    """Tool panel GUI testing"""

    def setUp(self) -> None:
        super().setUp()
        test_size = QSize(512, 512)
        self._image_stack = ImageStack(test_size, test_size, test_size, test_size)
        self._image_panel = ImagePanel(self._image_stack)
        self._tool_panel = ToolPanel()
        self._tool_panel.show()

    def _tool(self, tool_class):
        if tool_class is EyedropperTool:
            return tool_class(self._image_stack)
        return tool_class(self._image_stack, self._image_panel.image_viewer)

    def _set_host(self, orientation: Orientation, size_class: SizeClass) -> None:
        self._tool_panel.set_host_facts(orientation, HOST_SIZES[(orientation, size_class)])
        self.assertEqual(self._tool_panel.size_class, size_class)

    def test_add_remove_tool_button(self) -> None:
        """It should be possible to add and remove a tool button"""
        self.assertEqual(len(self._tool_panel.tool_buttons), 0)
        test_tool = DrawTool(self._image_stack, self._image_panel.image_viewer)
        self._tool_panel.add_tool_button(test_tool)
        self.assertEqual(len(self._tool_panel.tool_buttons), 1)
        self._tool_panel.remove_tool_button(test_tool)
        self.assertEqual(len(self._tool_panel.tool_buttons), 0)

    def test_avoid_duplicate_tools(self) -> None:
        """Adding the same tool or type of tool more than once should be blocked."""
        test_tool_1 = DrawTool(self._image_stack, self._image_panel.image_viewer)
        self._tool_panel.add_tool_button(test_tool_1)
        self._tool_panel.add_tool_button(test_tool_1)
        self.assertEqual(len(self._tool_panel.tool_buttons), 1)
        test_tool_2 = DrawTool(self._image_stack, self._image_panel.image_viewer)
        self._tool_panel.add_tool_button(test_tool_2)
        self.assertEqual(len(self._tool_panel.tool_buttons), 1)

    def test_activate_tool(self) -> None:
        """Activating a tool shows its control panel, marks its button and names it in the header with its key."""
        test_tool = DrawTool(self._image_stack, self._image_panel.image_viewer)
        self._tool_panel.add_tool_button(test_tool)
        tool_button = self._tool_panel.tool_buttons[0]
        self.assertEqual(self._tool_panel.header.name(), '')
        self.assertFalse(tool_button.is_active)
        control_panel = test_tool.get_control_panel()
        assert control_panel is not None
        self.assertFalse(control_panel.isVisible())

        self._tool_panel.setup_active_tool(test_tool)
        self.assertEqual(self._tool_panel.header.name(), test_tool.label)
        keys = KeyConfig().get(test_tool.get_activation_config_key())
        self.assertEqual(self._tool_panel.header.key_badge.text, get_key_display_string(keys, rich_text=False))
        self.assertTrue(tool_button.is_active)
        self.assertTrue(control_panel.isVisible())

    def test_header_follows_tool_switch_in_every_size_class(self) -> None:
        """After a tool switch, the header names the new tool and its key in every size class but Strip Short, where
        a dim line under the buttons names it instead. Only Side Wide adds the tool's description."""
        draw_tool = self._tool(DrawTool)
        text_tool = self._tool(TextTool)
        for tool in (draw_tool, text_tool):
            self._tool_panel.add_tool_button(tool)
        self._tool_panel.setup_active_tool(draw_tool)
        text_keys = get_key_display_string(KeyConfig().get(text_tool.get_activation_config_key()), rich_text=False)
        header = self._tool_panel.header
        short_label = self._tool_panel._short_label  # pylint: disable=protected-access
        for orientation, size_class in HOST_SIZES:
            with self.subTest(orientation=orientation, size_class=size_class):
                self._set_host(orientation, size_class)
                self._tool_panel.setup_active_tool(text_tool)
                strip_short = (orientation, size_class) == (Orientation.STRIP, SizeClass.COMPACT)
                self.assertEqual(header.isVisibleTo(self._tool_panel), not strip_short)
                self.assertEqual(short_label.isVisibleTo(self._tool_panel), strip_short)
                self.assertEqual(header.name(), text_tool.label)
                self.assertEqual(header.key_badge.text, text_keys)
                self.assertIn(text_tool.label, short_label.text())
                self.assertIn(text_keys, short_label.text())
                expected_description = text_tool.get_tooltip_text() \
                    if (orientation, size_class) == (Orientation.SIDE, SizeClass.WIDE) else ''
                self.assertEqual(header.description(), expected_description)
                self._tool_panel.setup_active_tool(draw_tool)

    def test_buttons_are_grouped_with_generation_area_last(self) -> None:
        """Buttons follow `BaseTool.TOOL_GROUP` order, keeping the order they were added in within a group."""
        added = [self._tool(GenerationAreaTool), self._tool(FreeSelectionTool), self._tool(DrawTool),
                 self._tool(TextTool), self._tool(EyedropperTool)]
        for tool in added:
            self._tool_panel.add_tool_button(tool)
        shown = [type(button.connected_tool) for button in self._tool_panel.tool_buttons]
        self.assertEqual(shown, [DrawTool, EyedropperTool, TextTool, FreeSelectionTool, GenerationAreaTool])

    def test_button_size_and_grid_per_size_class(self) -> None:
        """Each size class sets the button size and the number of buttons per row from `BUTTON_LAYOUTS`."""
        tools = [self._tool(DrawTool), self._tool(EyedropperTool), self._tool(TextTool), self._tool(FreeSelectionTool),
                 self._tool(GenerationAreaTool)]
        for tool in tools:
            self._tool_panel.add_tool_button(tool)
        rows = self._tool_panel._button_rows  # pylint: disable=protected-access
        for (orientation, size_class), layout in BUTTON_LAYOUTS.items():
            with self.subTest(orientation=orientation, size_class=size_class):
                self._set_host(orientation, size_class)
                for button in self._tool_panel.tool_buttons:
                    self.assertEqual(button.size(), QSize(layout.edge_length, layout.edge_length))
                expected_rows = -(-len(tools) // layout.columns)
                self.assertEqual(rows.count(), expected_rows)

    def test_reset_restores_active_tool_keys(self) -> None:
        """Reset restores the active tool's declared keys, and leaves the shared brush color alone."""
        draw_tool = self._tool(DrawTool)
        self._tool_panel.add_tool_button(draw_tool)
        self._tool_panel.setup_active_tool(draw_tool)
        cache = Cache()
        default_size = cache.get_default(Cache.DRAW_TOOL_BRUSH_SIZE)
        cache.set(Cache.DRAW_TOOL_BRUSH_SIZE, default_size + 7)
        color = cache.get(Cache.LAST_BRUSH_COLOR)
        self.assertTrue(self._tool_panel.header.reset_button.isVisibleTo(self._tool_panel))
        self._tool_panel.header.reset_button.click()
        self.assertEqual(cache.get(Cache.DRAW_TOOL_BRUSH_SIZE), default_size)
        self.assertEqual(cache.get(Cache.LAST_BRUSH_COLOR), color)

    def test_reset_hidden_without_reset_keys(self) -> None:
        """A tool that declares no reset keys hides the reset button."""
        text_tool = self._tool(TextTool)
        self._tool_panel.add_tool_button(text_tool)
        self._tool_panel.setup_active_tool(text_tool)
        self.assertFalse(self._tool_panel.header.reset_button.isVisibleTo(self._tool_panel))

    def test_strip_short_moves_reset_into_more_popover(self) -> None:
        """In Strip Short, the More button shows a popover with the reset button, which resets the active tool."""
        draw_tool = self._tool(DrawTool)
        self._tool_panel.add_tool_button(draw_tool)
        self._tool_panel.setup_active_tool(draw_tool)
        self._set_host(Orientation.STRIP, SizeClass.COMPACT)
        header = self._tool_panel.header
        self.assertTrue(header.more_button.isVisibleTo(self._tool_panel))
        reset_button = self._tool_panel._short_reset_button  # pylint: disable=protected-access
        self.assertIs(header.popover.content, reset_button.parentWidget())
        cache = Cache()
        default_size = cache.get_default(Cache.DRAW_TOOL_BRUSH_SIZE)
        cache.set(Cache.DRAW_TOOL_BRUSH_SIZE, default_size + 3)
        reset_button.click()
        self.assertEqual(cache.get(Cache.DRAW_TOOL_BRUSH_SIZE), default_size)

        self._set_host(Orientation.STRIP, SizeClass.REGULAR)
        self.assertFalse(header.more_button.isVisibleTo(self._tool_panel))
        self.assertTrue(header.reset_button.isVisibleTo(self._tool_panel))
