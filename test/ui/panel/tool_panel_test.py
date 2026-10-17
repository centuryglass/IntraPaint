"""Tests the Tools dock's panel: buttons, grouping and sizes per grid size, the active tool header, and reset."""
import sys

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QWidget

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.tools.draw_tool import DrawTool
from src.tools.eyedropper_tool import EyedropperTool
from src.tools.free_selection_tool import FreeSelectionTool
from src.tools.generation_area_tool import GenerationAreaTool
from src.tools.text_tool import TextTool
from src.ui.layout.panel_size_class import GridSize, Orientation, choose_layout
from src.ui.panel.image_panel import ImagePanel
from src.ui.panel.tool_panel import ToolPanel, BUTTON_LAYOUTS, BUTTON_SPACING, MAX_STRIP_EDGE_LENGTH, \
    STRIP_NARROW_COLUMNS, strip_button_layout
from src.util.visual.text_drawing_utils import get_key_display_string
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class GridLayoutControlPanel(QWidget):
    """A tool control panel that declares grid layouts and records each one it is given."""

    LAYOUTS = (GridSize(1, 1), GridSize(2, 1), GridSize(3, 1), GridSize(1, 2))

    def __init__(self) -> None:
        super().__init__()
        self.received: list[tuple[Orientation, GridSize]] = []

    def grid_layouts(self) -> tuple[GridSize, ...]:
        """Returns `LAYOUTS`."""
        return self.LAYOUTS

    def set_grid_layout(self, orientation: Orientation, layout: GridSize) -> None:
        """Records the layout."""
        self.received.append((orientation, layout))

# A dock size at each count along the constrained axis, away from the boundaries:
HOST_SIZES = {
    (Orientation.SIDE, 1): QSize(200, 600),
    (Orientation.SIDE, 2): QSize(340, 600),
    (Orientation.SIDE, 3): QSize(500, 600),
    (Orientation.STRIP, 1): QSize(1200, 120),
    (Orientation.STRIP, 2): QSize(1200, 240),
    (Orientation.STRIP, 3): QSize(1200, 400),
}


def settle_layouts(root: QWidget) -> None:
    """Activates every layout under root, parents first, so geometry is final without running the event loop."""
    for widget in [root, *root.findChildren(QWidget)]:
        layout = widget.layout()
        if layout is not None and widget.isVisibleTo(root):
            layout.activate()


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

    def _set_host(self, orientation: Orientation, count: int) -> None:
        """Hosts the panel at the `HOST_SIZES` size with `count` cells along the constrained axis."""
        self._tool_panel.set_host_facts(orientation, HOST_SIZES[(orientation, count)])
        grid_size = self._tool_panel.grid_size
        assert grid_size is not None
        self.assertEqual(grid_size.constrained(orientation), count)

    def _activate_grid_layout_tool(self) -> GridLayoutControlPanel:
        tool = self._tool(DrawTool)
        control_panel = GridLayoutControlPanel()
        tool.get_control_panel = lambda: control_panel
        self._tool_panel.add_tool_button(tool)
        self._tool_panel.setup_active_tool(tool)
        return control_panel

    def _host_and_settle(self, orientation: Orientation, size: QSize) -> None:
        self._tool_panel.set_host_facts(orientation, size)
        self._tool_panel.resize(size)
        settle_layouts(self._tool_panel)

    def test_grid_layout_measures_tool_control_area(self) -> None:
        """The grid size comes from the tool control area, so a strip three columns wide at the dock is
        two columns once the buttons take their share."""
        self._activate_grid_layout_tool()
        self._host_and_settle(Orientation.STRIP, QSize(450, 240))
        self.assertEqual(self._tool_panel.grid_size, GridSize(3, 2))
        grid_size = self._tool_panel.tool_control_grid_size
        assert grid_size is not None
        self.assertEqual(grid_size.columns, 2)

    def test_grid_layout_forwarded_on_change(self) -> None:
        """A grid-aware control panel gets the chosen layout on activation, and again only when the orientation or
        chosen layout changes."""
        control_panel = self._activate_grid_layout_tool()
        self.assertEqual(len(control_panel.received), 1)
        for orientation, size in ((Orientation.STRIP, QSize(1400, 240)), (Orientation.SIDE, QSize(340, 900))):
            with self.subTest(orientation=orientation):
                self._host_and_settle(orientation, size)
                grid_size = self._tool_panel.tool_control_grid_size
                assert grid_size is not None
                expected = choose_layout(grid_size, GridLayoutControlPanel.LAYOUTS, orientation)
                self.assertEqual(control_panel.received[-1], (orientation, expected))
        self.assertEqual(control_panel.received[-1], (Orientation.SIDE, GridSize(1, 2)))
        count = len(control_panel.received)
        self._host_and_settle(Orientation.SIDE, QSize(345, 905))
        self.assertEqual(len(control_panel.received), count)

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

    def test_header_follows_tool_switch_at_every_named_size(self) -> None:
        """After a tool switch, the header names the new tool and its key at every named size but Strip Short, where
        a dim line under the buttons names it. The description shows at every size but Side Compact and Strip Short.
        """
        draw_tool = self._tool(DrawTool)
        text_tool = self._tool(TextTool)
        for tool in (draw_tool, text_tool):
            self._tool_panel.add_tool_button(tool)
        self._tool_panel.setup_active_tool(draw_tool)
        text_keys = get_key_display_string(KeyConfig().get(text_tool.get_activation_config_key()), rich_text=False)
        header = self._tool_panel.header
        short_label = self._tool_panel._short_label  # pylint: disable=protected-access
        for orientation, count in HOST_SIZES:
            with self.subTest(orientation=orientation, count=count):
                self._set_host(orientation, count)
                self._tool_panel.setup_active_tool(text_tool)
                strip_short = (orientation, count) == (Orientation.STRIP, 1)
                self.assertEqual(header.isVisibleTo(self._tool_panel), not strip_short)
                self.assertEqual(short_label.isVisibleTo(self._tool_panel), strip_short)
                self.assertEqual(header.name(), text_tool.label)
                self.assertEqual(header.key_badge.text, text_keys)
                self.assertIn(text_tool.label, short_label.text())
                self.assertIn(text_keys, short_label.text())
                expected_description = '' if count == 1 else text_tool.get_tooltip_text()
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

    def _add_tools(self) -> list:
        tools = [self._tool(DrawTool), self._tool(EyedropperTool), self._tool(TextTool), self._tool(FreeSelectionTool),
                 self._tool(GenerationAreaTool)]
        for tool in tools:
            self._tool_panel.add_tool_button(tool)
        return tools

    def _grid_shape(self) -> tuple[int, int]:
        """Returns the number of rows and columns the buttons fill."""
        grid = self._tool_panel._button_grid_layout  # pylint: disable=protected-access
        positions = [grid.getItemPosition(i)[:2] for i in range(grid.count())]
        return max(row for row, _ in positions) + 1, max(column for _, column in positions) + 1

    def test_button_size_and_grid_per_constrained_count(self) -> None:
        """Each count along the constrained axis sets the button size and buttons per row from `BUTTON_LAYOUTS`, at a
        height too short for a three-column strip grid."""
        tools = self._add_tools()
        for (orientation, count), layout in BUTTON_LAYOUTS.items():
            with self.subTest(orientation=orientation, count=count):
                self._set_host(orientation, count)
                if orientation == Orientation.STRIP and count != 1:
                    self._tool_panel.resize(QSize(1200, 60))
                for button in self._tool_panel.tool_buttons:
                    self.assertEqual(button.size(), QSize(layout.edge_length, layout.edge_length))
                columns = min(layout.columns, len(tools))
                self.assertEqual(self._grid_shape(), (-(-len(tools) // columns), columns))

    def test_tall_strip_uses_three_larger_columns(self) -> None:
        """A strip tall enough for three columns of buttons at least the default size uses them, growing the buttons
        up to `MAX_STRIP_EDGE_LENGTH` with key hints at that size."""
        tools = self._add_tools()
        self._set_host(Orientation.STRIP, 3)
        self._tool_panel.resize(QSize(1200, 400))
        self.assertEqual(self._grid_shape(), (-(-len(tools) // STRIP_NARROW_COLUMNS), STRIP_NARROW_COLUMNS))
        for button in self._tool_panel.tool_buttons:
            self.assertEqual(button.width(), MAX_STRIP_EDGE_LENGTH)

    def test_strip_button_layout(self) -> None:
        """Three columns once their buttons are at least the default size, capped at `MAX_STRIP_EDGE_LENGTH`."""
        default = BUTTON_LAYOUTS[(Orientation.STRIP, 2)]
        self.assertEqual(strip_button_layout(16, 100, default), default)
        fitted = strip_button_layout(16, 6 * 30 + 5 * BUTTON_SPACING, default)
        self.assertEqual((fitted.columns, fitted.edge_length, fitted.key_hints), (STRIP_NARROW_COLUMNS, 30, False))
        tall = strip_button_layout(16, 1000, default)
        self.assertEqual((tall.edge_length, tall.key_hints), (MAX_STRIP_EDGE_LENGTH, True))

    def test_header_icon_lines_up_with_first_button_column(self) -> None:
        """The header's icon is centered over the first column of buttons, in both orientations."""
        self._add_tools()
        self._tool_panel.setup_active_tool(self._tool_panel.tool_buttons[0].connected_tool)
        header = self._tool_panel.header
        icon_label = header._icon_label  # pylint: disable=protected-access
        for orientation, count in ((Orientation.SIDE, 2), (Orientation.STRIP, 2)):
            with self.subTest(orientation=orientation):
                self._set_host(orientation, count)
                self._tool_panel.resize(HOST_SIZES[(orientation, count)])
                settle_layouts(self._tool_panel)
                button = self._tool_panel.tool_buttons[0]
                button_center = button.mapTo(self._tool_panel, button.rect().center()).x()
                icon_center = icon_label.mapTo(self._tool_panel, icon_label.rect().center()).x()
                self.assertLessEqual(abs(button_center - icon_center), 1)

    def test_side_header_sits_under_buttons(self) -> None:
        """Side panels show the header between the buttons and the controls, and strip panels above both."""
        self._add_tools()
        header = self._tool_panel.header
        grid = self._tool_panel._button_grid  # pylint: disable=protected-access
        for orientation, count in ((Orientation.SIDE, 2), (Orientation.STRIP, 2)):
            with self.subTest(orientation=orientation):
                self._set_host(orientation, count)
                self._tool_panel.resize(HOST_SIZES[(orientation, count)])
                settle_layouts(self._tool_panel)
                header_top = header.mapTo(self._tool_panel, header.rect().topLeft()).y()
                grid_top = grid.mapTo(self._tool_panel, grid.rect().topLeft()).y()
                if orientation == Orientation.SIDE:
                    self.assertGreater(header_top, grid_top)
                else:
                    self.assertLess(header_top, grid_top)

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
        self._set_host(Orientation.STRIP, 1)
        header = self._tool_panel.header
        self.assertTrue(header.more_button.isVisibleTo(self._tool_panel))
        reset_button = self._tool_panel._short_reset_button  # pylint: disable=protected-access
        self.assertIs(header.popover.content, reset_button.parentWidget())
        cache = Cache()
        default_size = cache.get_default(Cache.DRAW_TOOL_BRUSH_SIZE)
        cache.set(Cache.DRAW_TOOL_BRUSH_SIZE, default_size + 3)
        reset_button.click()
        self.assertEqual(cache.get(Cache.DRAW_TOOL_BRUSH_SIZE), default_size)

        self._set_host(Orientation.STRIP, 2)
        self.assertFalse(header.more_button.isVisibleTo(self._tool_panel))
        self.assertTrue(header.reset_button.isVisibleTo(self._tool_panel))
