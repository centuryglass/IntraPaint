"""Tests the icon rails: dock buttons that toggle docks and follow them between edges, the Generate button, and the
recent tools that fill only the space the rail has left."""
import sys
from unittest.mock import patch

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtWidgets import QApplication, QLabel

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.controller.tool_controller import ToolController
from src.image.layers.image_stack import ImageStack
from src.ui.ink_style import PRIMARY_BUTTON_PROPERTY
from src.ui.widget.key_hint_label import KeyHintLabel
from src.ui.widget.tool_button import ToolButton
from src.ui.window.dock_rail import RAIL_SPACING, RULE_SPACE, SIDE_RAIL_WIDTH
from src.ui.window.main_window import MainWindow
from src.util.application_state import AppStateTracker, APP_STATE_EDITING
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

LARGE_SCREEN = QSize(4000, 4000)
Area = Qt.DockWidgetArea


class DockRailTest(IntraPaintTestCase):
    """Builds a MainWindow with filled docks and a real tool controller, without AppController."""

    def setUp(self) -> None:
        super().setUp()
        screen_patch = patch('src.ui.window.main_window.get_screen_size', return_value=LARGE_SCREEN)
        screen_patch.start()
        self.addCleanup(screen_patch.stop)
        size = QSize(64, 64)
        image_stack = ImageStack(size, size, size, size)
        self.window = MainWindow(image_stack)
        self.window.tools_dock.set_content(QLabel('tools'))
        self.window.generation_dock.set_content(QLabel('generation'))
        self.tool_controller = ToolController(image_stack, self.window.image_panel.image_viewer, use_hotkeys=False)
        self.window.set_tool_controller(self.tool_controller)
        self.window.resize(1280, 720)
        self.window.show()
        self.window.layout().activate()
        self.right_rail = self.window.rails.rail(Area.RightDockWidgetArea)

    def tearDown(self) -> None:
        self.window.hide()
        super().tearDown()

    def _button(self, dock):
        return next(button for button in self.right_rail.buttons if button.dock is dock)

    def _fill_lower_docks(self) -> None:
        for dock in self.window.lower_docks:
            dock.set_content(QLabel(dock.windowTitle()))
        self.window.layout().activate()

    def _start(self, widget, side: bool = True) -> int:
        """Returns where a widget starts along a rail, in window coordinates."""
        position = widget.mapTo(self.window, QPoint(0, 0))
        return position.y() if side else position.x()

    def _end(self, widget, side: bool = True) -> int:
        return self._start(widget, side) + (widget.height() if side else widget.width())

    def test_buttons_line_up_with_their_groups(self) -> None:
        """Each tab group's buttons start where its open dock starts, with a rule before the second group."""
        self._fill_lower_docks()
        window = self.window
        groups = self.right_rail.groups
        self.assertEqual([[button.dock for button in group] for group in groups],
                         [window.upper_docks, window.lower_docks])
        first_start = self._start(groups[0][0])
        self.assertGreaterEqual(first_start, window.tools_dock.y())
        self.assertLess(first_start, window.tools_dock.y() + RULE_SPACE)
        self.assertEqual(self._start(groups[1][0]), window.layers_dock.y())
        self.assertEqual(len(self.right_rail.rules), 1)
        rule = self.right_rail.rules[0]
        self.assertLess(self._end(rule), window.layers_dock.y())
        self.assertGreater(self._start(rule), window.layers_dock.y() - RULE_SPACE)

    def test_buttons_follow_a_moved_split(self) -> None:
        """Resizing the split between two groups moves the second group's buttons with it."""
        self._fill_lower_docks()
        window = self.window
        layers_button = self.right_rail.groups[1][0]
        for height in (200, 400):
            window.resizeDocks([window.tools_dock], [height], Qt.Orientation.Vertical)
            window.layout().activate()
            self.assertEqual(self._start(layers_button), window.layers_dock.y(), height)

    def test_groups_split_side_by_side_line_up_in_a_strip_rail(self) -> None:
        """In the bottom area, a dock split to the right of another has its button start at its left edge."""
        self._fill_lower_docks()
        window = self.window
        bottom = Area.BottomDockWidgetArea
        window.addDockWidget(bottom, window.layers_dock, Qt.Orientation.Horizontal)
        window.addDockWidget(bottom, window.tools_dock, Qt.Orientation.Horizontal)
        window.resizeDocks([window.layers_dock, window.tools_dock], [600, 600], Qt.Orientation.Horizontal)
        window.rails.sync()
        window.layout().activate()
        groups = window.rails.rail(bottom).groups
        self.assertEqual([[button.dock for button in group] for group in groups],
                         [[window.layers_dock], [window.tools_dock]])
        self.assertGreater(window.tools_dock.x(), self._end(groups[0][0], side=False))
        self.assertEqual(self._start(groups[1][0], side=False), window.tools_dock.x())

    def test_a_group_near_the_rail_end_ends_there(self) -> None:
        """A dock too narrow for its button at the end of a strip rail has its button end at the rail's end."""
        self._fill_lower_docks()
        window = self.window
        bottom = Area.BottomDockWidgetArea
        window.addDockWidget(bottom, window.layers_dock, Qt.Orientation.Horizontal)
        window.addDockWidget(bottom, window.tools_dock, Qt.Orientation.Horizontal)
        window.resizeDocks([window.layers_dock, window.tools_dock], [1000, 20], Qt.Orientation.Horizontal)
        window.rails.sync()
        window.layout().activate()
        rail = window.rails.rail(bottom)
        layers_button, tools_button = rail.buttons[0], rail.buttons[1]
        self.assertGreater(self._start(tools_button, side=False), self._end(layers_button, side=False) + RULE_SPACE)
        self.assertLess(self._start(tools_button, side=False), window.tools_dock.x())
        self.assertLessEqual(self._end(tools_button, side=False), self._end(rail, side=False))

    def test_a_closed_group_follows_the_group_before_it(self) -> None:
        """A group with no open dock packs in after the previous group, keeping its buttons."""
        self._fill_lower_docks()
        self.window.layers_dock.hide()
        self.window.layout().activate()
        groups = self.right_rail.groups
        self.assertEqual(len(groups), 2)
        last_upper = [button for button in groups[0] if not button.isHidden()][-1]
        self.assertEqual(self._start(groups[1][0]), self._end(last_upper) + RULE_SPACE)

    def test_groups_that_dont_fit_their_docks_pack_without_overlap(self) -> None:
        """When the upper group's dock is shorter than its buttons, the next group's buttons come after them."""
        self._fill_lower_docks()
        window = self.window
        window.resizeDocks([window.tools_dock], [40], Qt.Orientation.Vertical)
        window.layout().activate()
        buttons = [button for button in self.right_rail.buttons if not button.isHidden()]
        for earlier, later in zip(buttons, buttons[1:]):
            self.assertLessEqual(self._end(earlier), self._start(later))

    def test_recent_tools_stop_before_the_next_group(self) -> None:
        """The recent tools follow the Tools group's buttons and end before the next group's rule."""
        self._fill_lower_docks()
        window = self.window
        strip = window.rails.recent_tools
        assert strip is not None
        upper = [button for button in self.right_rail.groups[0] if not button.isHidden()]
        self.assertEqual(self._start(strip), self._end(upper[-1]) + RAIL_SPACING)
        self.assertLessEqual(self._end(strip), self._start(self.right_rail.rules[0]))

    def test_side_rail_is_narrow_with_a_button_per_dock_with_content(self) -> None:
        """The right rail shows the Tools and Image Generation buttons, not ControlNet's, at the side rail width."""
        self.assertTrue(self.right_rail.isVisible())
        shown = [button.dock for button in self.right_rail.buttons if not button.isHidden()]
        self.assertEqual(shown, [self.window.tools_dock, self.window.generation_dock])
        for button in self.right_rail.buttons:
            if not button.isHidden():
                self.assertEqual(button.width(), SIDE_RAIL_WIDTH)

    def test_clicking_the_active_button_hides_its_dock_and_clicking_again_shows_it(self) -> None:
        """A button hides its dock while the dock is showing, and shows and raises it otherwise."""
        tools = self.window.tools_dock
        button = self._button(tools)
        self.assertTrue(tools.is_showing)
        self.assertTrue(button.isChecked())
        button.click()
        self.assertFalse(tools.is_showing)
        self.assertFalse(button.isChecked())
        button.click()
        self.assertTrue(tools.is_showing)
        self.assertTrue(button.isChecked())

    def test_clicking_a_button_raises_a_dock_behind_a_tab(self) -> None:
        """A dock hidden behind another tab comes to the front when its button is clicked."""
        generation = self.window.generation_dock
        self.assertFalse(generation.is_showing)
        self._button(generation).click()
        self.assertTrue(generation.is_showing)
        self.assertFalse(self.window.tools_dock.is_showing)

    def test_button_follows_its_dock_to_another_area(self) -> None:
        """Moving a dock to another window edge moves its button to that edge's rail, as an icon and name strip."""
        tools = self.window.tools_dock
        self.window.addDockWidget(Area.BottomDockWidgetArea, tools)
        tools.show()
        bottom_rail = self.window.rails.rail(Area.BottomDockWidgetArea)
        self.assertIn(tools, [button.dock for button in bottom_rail.buttons])
        self.assertNotIn(tools, [button.dock for button in self.right_rail.buttons])
        self.assertFalse(bottom_rail.is_side)
        self.assertTrue(bottom_rail.isVisible())

    def test_generate_button_shows_while_generation_dock_is_not_showing(self) -> None:
        """Generate is primary styled, names its key in the tooltip, and emits the window's generate signal."""
        generate = self.window.rails.generate_button
        self.assertTrue(generate.property(PRIMARY_BUTTON_PROPERTY))
        self.assertEqual(KeyConfig().get(KeyConfig.GENERATE_SHORTCUT), 'F4')
        self.assertIn('<img', generate.toolTip(), 'the tooltip shows the key as a keycap')
        self.assertFalse(self.window.generation_dock.is_showing)
        self.assertFalse(generate.isHidden())
        AppStateTracker.set_app_state(APP_STATE_EDITING)
        emitted = []
        self.window.generate_signal.connect(lambda: emitted.append(True))
        generate.click()
        self.assertEqual(emitted, [True])
        self._button(self.window.generation_dock).click()
        self.assertTrue(generate.isHidden())

    def test_recent_tools_fill_only_the_space_left_over(self) -> None:
        """The recent tools shown follow the rail's height up to the configured count, and never change the window's
        minimum size."""
        strip = self.window.rails.recent_tools
        assert strip is not None
        AppConfig().set(AppConfig.TOOLBAR_TOOL_BUTTON_COUNT, 6)
        self.window.layout().activate()
        self.assertEqual(len(strip.shown_tools), 6)
        minimum_with_six = self.window.minimumSizeHint()
        AppConfig().set(AppConfig.TOOLBAR_TOOL_BUTTON_COUNT, 1)
        self.window.layout().activate()
        self.assertEqual(len(strip.shown_tools), 1)
        self.assertEqual(self.window.minimumSizeHint(), minimum_with_six)
        AppConfig().set(AppConfig.TOOLBAR_TOOL_BUTTON_COUNT, 99)
        self.window.layout().activate()
        self.assertEqual(self.window.minimumSizeHint(), minimum_with_six)
        self.window.resize(1280, 560)
        self.window.layout().activate()
        fit = len(strip.shown_tools)
        self.window.resize(1280, 900)
        self.window.layout().activate()
        self.assertGreater(len(strip.shown_tools), fit)

    def test_recent_tool_buttons_hide_their_key_hints(self) -> None:
        """The 32 px recent tool buttons show no key hint, which would cover the icon."""
        strip = self.window.rails.recent_tools
        assert strip is not None
        for button in strip.findChildren(ToolButton):
            self.assertTrue(button.isHidden() or button.width() == SIDE_RAIL_WIDTH)
            self.assertTrue(button.findChild(KeyHintLabel).isHidden())

    def test_rails_hide_while_the_image_selector_is_showing(self) -> None:
        """Every rail hides with the docks, and comes back with them."""
        self.window.set_image_selector_visible(True)
        self.assertTrue(self.right_rail.isHidden())
        self.window.set_image_selector_visible(False)
        self.assertTrue(self.right_rail.isVisible())

