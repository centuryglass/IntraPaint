"""Tests the icon rails: dock buttons that toggle docks and follow them between edges, the Generate button, and the
recent tools that fill only the space the rail has left."""
import sys
from unittest.mock import patch

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QLabel

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.controller.tool_controller import ToolController
from src.image.layers.image_stack import ImageStack
from src.ui.ink_style import PRIMARY_BUTTON_PROPERTY
from src.ui.window.dock_rail import SIDE_RAIL_WIDTH
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

    def test_rails_hide_while_the_image_selector_is_showing(self) -> None:
        """Every rail hides with the docks, and comes back with them."""
        self.window.set_image_selector_visible(True)
        self.assertTrue(self.right_rail.isHidden())
        self.window.set_image_selector_visible(False)
        self.assertTrue(self.right_rail.isVisible())
