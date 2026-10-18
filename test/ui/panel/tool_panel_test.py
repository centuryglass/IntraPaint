"""Tests the Tools dock's panel: buttons, grouping and button forms by fit, the active tool header, reset, and the
space a fit-aware tool control panel gets."""
import sys

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.tools.draw_tool import DrawTool
from src.tools.eyedropper_tool import EyedropperTool
from src.tools.free_selection_tool import FreeSelectionTool
from src.tools.generation_area_tool import GenerationAreaTool
from src.tools.text_tool import TextTool
from src.ui.layout.panel_fit import HYSTERESIS, Orientation
from src.ui.panel.image_panel import ImagePanel
from src.ui.panel.tool_panel import ToolPanel, ButtonLayout, BUTTON_SPACING, MAX_STRIP_EDGE_LENGTH, SIDE_BUTTON_FORMS, \
    STRIP_BUTTON_FORMS, STRIP_MAX_COLUMNS, STRIP_NARROW_COLUMNS, strip_button_layout
from src.util.visual.text_drawing_utils import get_key_display_string
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

SIDE = Orientation.SIDE
STRIP = Orientation.STRIP
# Sample host sizes, named by shape:
HOST_SIZES = {
    'side_narrow': (SIDE, QSize(200, 600)),
    'side_regular': (SIDE, QSize(300, 600)),
    'side_wide': (SIDE, QSize(500, 600)),
    'side_tall_narrow': (SIDE, QSize(200, 1400)),
    'strip_short': (STRIP, QSize(1200, 60)),
    'strip_regular': (STRIP, QSize(1200, 240)),
    'strip_tall': (STRIP, QSize(1200, 400)),
}


class FitControlPanel(QWidget):
    """A tool control panel that plans its own layout, recording each call."""

    def __init__(self) -> None:
        super().__init__()
        self.base_sizes: list[Orientation] = []
        self.spaces: list[tuple[Orientation, QSize]] = []
        self.setMinimumSize(100, 100)

    def fit_base_size(self, orientation: Orientation) -> QSize:
        """Records the call and returns the fixed minimum."""
        self.base_sizes.append(orientation)
        return self.minimumSize()

    def set_fit_space(self, orientation: Orientation, size: QSize) -> None:
        """Records the space."""
        self.spaces.append((orientation, size))


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

    def _host(self, orientation: Orientation, size: QSize) -> None:
        """Reports an orientation and size as the dock would, sizes the panel to match, then settles its layouts."""
        self._tool_panel.set_host_facts(orientation, size)
        self._tool_panel.resize(size)
        settle_layouts(self._tool_panel)

    def _host_named(self, name: str) -> None:
        self._host(*HOST_SIZES[name])

    def _side_width_for(self, layout: ButtonLayout) -> int:
        """Returns the narrowest side panel with room across for a row of buttons in `layout`."""
        columns = min(layout.columns, len(self._tool_panel.tool_buttons))
        margins = self._tool_panel._body_layout.contentsMargins()  # pylint: disable=protected-access
        return columns * layout.edge_length + (columns - 1) * BUTTON_SPACING + margins.left() + margins.right()

    def test_fit_content_gets_base_size_then_the_space_left_over(self) -> None:
        """A fit-aware control panel is measured at its base size in each orientation the panel plans, then gets the
        space beside the buttons and under the header."""
        tool = self._tool(DrawTool)
        control_panel = FitControlPanel()
        tool.get_control_panel = lambda: control_panel
        self._tool_panel.add_tool_button(tool)
        self._tool_panel.setup_active_tool(tool)
        for name in ('side_regular', 'strip_regular'):
            with self.subTest(size=name):
                orientation, size = HOST_SIZES[name]
                control_panel.base_sizes.clear()
                self._host(orientation, size)
                self.assertEqual(self._tool_panel.orientation, orientation)
                self.assertEqual(control_panel.base_sizes[-1], orientation)
                space_orientation, space = control_panel.spaces[-1]
                self.assertEqual(space_orientation, orientation)
                box = self._tool_panel._tool_control_box  # pylint: disable=protected-access
                self.assertEqual(space, self._tool_panel.tool_control_space())
                if orientation == SIDE:
                    self.assertLess(space.height(), size.height() - self._tool_panel.header.height())
                    self.assertEqual(space.width(), box.width())
                else:
                    self.assertLess(space.width(), size.width() - self._tool_panel._strip_column.width())  # pylint: disable=protected-access
                    self.assertEqual(space.height(), box.height())

    def test_plans_leave_no_layout_work_for_the_event_loop(self) -> None:
        """After a resize, every widget already has its final geometry, so a paint before the posted layout requests
        run can't show a half-applied layout."""
        self._add_tools()
        self._tool_panel.setup_active_tool(self._tool_panel.tool_buttons[0].connected_tool)
        for name, (orientation, size) in HOST_SIZES.items():
            with self.subTest(size=name):
                self._tool_panel.resize(size)
                self._tool_panel.set_host_facts(orientation, size)
                widgets = [widget for widget in self._tool_panel.findChildren(QWidget)
                           if widget.isVisibleTo(self._tool_panel)]
                planned = [widget.geometry() for widget in widgets]
                settle_layouts(self._tool_panel)
                settled = [widget.geometry() for widget in widgets]
                moved = [type(widget).__name__ for widget, before, after in zip(widgets, planned, settled)
                         if before != after]
                self.assertEqual(moved, [])
                # A scroll bar that doesn't match its range would change the body's width after the next paint:
                scroll_area = self._tool_panel.findChild(QScrollArea)
                for bar in (scroll_area.horizontalScrollBar(), scroll_area.verticalScrollBar()):
                    self.assertEqual(bar.isVisibleTo(scroll_area), bar.maximum() > bar.minimum())

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

    def test_header_follows_tool_switch_at_every_sample_size(self) -> None:
        """After a tool switch, the header names the new tool, its key and its description at every sample size but
        the short strip, where the header collapses and a dim line under the buttons names the tool."""
        draw_tool = self._tool(DrawTool)
        text_tool = self._tool(TextTool)
        for tool in (draw_tool, text_tool):
            self._tool_panel.add_tool_button(tool)
        self._tool_panel.setup_active_tool(draw_tool)
        text_keys = get_key_display_string(KeyConfig().get(text_tool.get_activation_config_key()), rich_text=False)
        header = self._tool_panel.header
        short_label = self._tool_panel._short_label  # pylint: disable=protected-access
        for name in HOST_SIZES:
            with self.subTest(size=name):
                self._host_named(name)
                self._tool_panel.setup_active_tool(text_tool)
                collapsed = name == 'strip_short'
                self.assertEqual(self._tool_panel.header_collapsed, collapsed)
                self.assertEqual(header.isVisibleTo(self._tool_panel), not collapsed)
                self.assertEqual(short_label.isVisibleTo(self._tool_panel), collapsed)
                self.assertEqual(header.name(), text_tool.label)
                self.assertEqual(header.key_badge.text, text_keys)
                self.assertIn(text_tool.label, short_label.text())
                self.assertIn(text_keys, short_label.text())
                if not collapsed:
                    self.assertEqual(header.description(), text_tool.get_tooltip_text())
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

    def test_side_buttons_take_the_largest_form_that_fits_across(self) -> None:
        """A side panel uses the largest of `SIDE_BUTTON_FORMS` whose row of buttons fits its width, whatever its
        height. Shrinking switches at the boundary, and growing only `HYSTERESIS` pixels past it."""
        tools = self._add_tools()
        for index, layout in enumerate(SIDE_BUTTON_FORMS):
            width = self._side_width_for(layout)
            for height in (600, 1400):
                with self.subTest(edge_length=layout.edge_length, height=height):
                    self._host(SIDE, QSize(width + 100, height))
                    self._host(SIDE, QSize(width, height))
                    self.assertEqual(self._tool_panel.button_layout, layout)
                    for button in self._tool_panel.tool_buttons:
                        self.assertEqual(button.size(), QSize(layout.edge_length, layout.edge_length))
                    self.assertEqual(self._grid_shape(), (1, len(tools)))
                    if index + 1 < len(SIDE_BUTTON_FORMS):
                        self._host(SIDE, QSize(width - 1, height))
                        self.assertEqual(self._tool_panel.button_layout, SIDE_BUTTON_FORMS[index + 1])
                        self._host(SIDE, QSize(width + HYSTERESIS - 1, height))
                        self.assertEqual(self._tool_panel.button_layout, SIDE_BUTTON_FORMS[index + 1])
                        self._host(SIDE, QSize(width + HYSTERESIS, height))
                        self.assertEqual(self._tool_panel.button_layout, layout)

    def test_short_strip_uses_one_dense_row(self) -> None:
        """A strip too short for larger buttons uses the smallest strip form."""
        self._add_tools()
        self._host_named('strip_short')
        self.assertEqual(self._tool_panel.button_layout, STRIP_BUTTON_FORMS[-1])

    def test_tall_strip_uses_two_larger_columns(self) -> None:
        """A strip tall enough for two columns of buttons at least the default size uses them, growing the buttons
        up to `MAX_STRIP_EDGE_LENGTH` with key hints at that size."""
        tools = self._add_tools()
        self._host_named('strip_tall')
        self.assertEqual(self._grid_shape(), (-(-len(tools) // STRIP_NARROW_COLUMNS), STRIP_NARROW_COLUMNS))
        for button in self._tool_panel.tool_buttons:
            self.assertEqual(button.width(), MAX_STRIP_EDGE_LENGTH)

    def test_strip_button_layout(self) -> None:
        """Three columns once their buttons are at least the default size, capped at `MAX_STRIP_EDGE_LENGTH`, and two
        columns only when the buttons keep that size."""
        default = STRIP_BUTTON_FORMS[0]
        self.assertEqual(strip_button_layout(16, 100, default), default)
        three = strip_button_layout(16, 6 * 30 + 5 * BUTTON_SPACING, default)
        self.assertEqual((three.columns, three.edge_length, three.key_hints), (STRIP_MAX_COLUMNS, 30, False))
        two = strip_button_layout(16, 8 * MAX_STRIP_EDGE_LENGTH + 7 * BUTTON_SPACING, default)
        self.assertEqual((two.columns, two.edge_length), (STRIP_NARROW_COLUMNS, MAX_STRIP_EDGE_LENGTH))
        shrunk = strip_button_layout(16, 8 * (MAX_STRIP_EDGE_LENGTH - 1) + 7 * BUTTON_SPACING, default)
        self.assertEqual((shrunk.columns, shrunk.edge_length), (STRIP_MAX_COLUMNS, MAX_STRIP_EDGE_LENGTH))
        tall = strip_button_layout(16, 1000, default)
        self.assertEqual((tall.edge_length, tall.key_hints), (MAX_STRIP_EDGE_LENGTH, True))

    def test_header_icon_lines_up_with_first_button_column(self) -> None:
        """The header's icon is centered over the first column of buttons, in both orientations."""
        self._add_tools()
        self._tool_panel.setup_active_tool(self._tool_panel.tool_buttons[0].connected_tool)
        header = self._tool_panel.header
        icon_label = header._icon_label  # pylint: disable=protected-access
        for name in ('side_regular', 'strip_regular'):
            with self.subTest(size=name):
                self._host_named(name)
                orientation = HOST_SIZES[name][0]
                button = self._tool_panel.tool_buttons[0]
                button_center = button.mapTo(self._tool_panel, button.rect().center()).x()
                icon_center = icon_label.mapTo(self._tool_panel, icon_label.rect().center()).x()
                self.assertLessEqual(abs(button_center - icon_center), 1)

    def test_side_header_sits_under_buttons(self) -> None:
        """Side panels show the header between the buttons and the controls, and strip panels above both."""
        self._add_tools()
        header = self._tool_panel.header
        grid = self._tool_panel._button_grid  # pylint: disable=protected-access
        for name in ('side_regular', 'strip_regular'):
            with self.subTest(size=name):
                self._host_named(name)
                orientation = HOST_SIZES[name][0]
                header_top = header.mapTo(self._tool_panel, header.rect().topLeft()).y()
                grid_top = grid.mapTo(self._tool_panel, grid.rect().topLeft()).y()
                if orientation == SIDE:
                    self.assertGreater(header_top, grid_top)
                else:
                    self.assertLess(header_top, grid_top)

    def test_reset_restores_active_tool_keys(self) -> None:
        """Reset restores the active tool's declared keys, and leaves the shared brush color alone."""
        draw_tool = self._tool(DrawTool)
        self._tool_panel.add_tool_button(draw_tool)
        self._tool_panel.setup_active_tool(draw_tool)
        self._host_named('side_regular')
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

    def test_short_strip_moves_reset_into_more_popover(self) -> None:
        """While a short strip collapses the header, the More button shows a popover with the reset button, which
        resets the active tool."""
        draw_tool = self._tool(DrawTool)
        self._tool_panel.add_tool_button(draw_tool)
        self._tool_panel.setup_active_tool(draw_tool)
        self._host_named('strip_short')
        header = self._tool_panel.header
        self.assertTrue(header.more_button.isVisibleTo(self._tool_panel))
        reset_button = self._tool_panel._short_reset_button  # pylint: disable=protected-access
        self.assertIs(header.popover.content, reset_button.parentWidget())
        cache = Cache()
        default_size = cache.get_default(Cache.DRAW_TOOL_BRUSH_SIZE)
        cache.set(Cache.DRAW_TOOL_BRUSH_SIZE, default_size + 3)
        reset_button.click()
        self.assertEqual(cache.get(Cache.DRAW_TOOL_BRUSH_SIZE), default_size)

        self._host_named('strip_regular')
        self.assertFalse(header.more_button.isVisibleTo(self._tool_panel))
        self.assertTrue(header.reset_button.isVisibleTo(self._tool_panel))
