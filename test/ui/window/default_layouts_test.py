"""Tests the bundled default dock layouts in `src.ui.window.default_layouts` and how `MainWindow.reset_dock_layout`
picks between them."""
import sys
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QLabel

from src.image.layers.image_stack import ImageStack
from src.ui.window import default_layouts
from src.ui.window.default_layouts import LAYOUT_1080P, LAYOUT_4K_TALL, LAYOUT_SMALL, select_default_layout_state
from src.ui.window.main_window import MainWindow
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

BUNDLED_LAYOUTS = {'LAYOUT_1080P': LAYOUT_1080P, 'LAYOUT_4K_TALL': LAYOUT_4K_TALL, 'LAYOUT_SMALL': LAYOUT_SMALL}


class SelectDefaultLayoutTest(IntraPaintTestCase):
    """Tests `select_default_layout_state` alone."""

    def test_common_sizes_pick_their_layout(self) -> None:
        """A small screen gets the small layout, a 1080p screen the 1080p layout, and a tall portrait screen the tall
        layout."""
        cases = {
            QSize(800, 600): LAYOUT_SMALL,
            QSize(1024, 600): LAYOUT_SMALL,
            QSize(1280, 720): LAYOUT_SMALL,
            QSize(1920, 1080): LAYOUT_1080P,
            QSize(1080, 1920): LAYOUT_4K_TALL,
            QSize(2160, 3840): LAYOUT_4K_TALL
        }
        for size, expected in cases.items():
            with self.subTest(size=size):
                self.assertIs(select_default_layout_state(size.width(), size.height()), expected)

    def test_every_bundled_layout_is_listed(self) -> None:
        """`BUNDLED_LAYOUTS` names every layout constant, so the restore tests cover each one."""
        constants = {name for name in dir(default_layouts) if name.startswith('LAYOUT_')}
        self.assertEqual(constants, set(BUNDLED_LAYOUTS))


class DefaultLayoutWindowTest(IntraPaintTestCase):
    """Builds MainWindows without AppController, with content in every dock but ControlNet."""

    def setUp(self) -> None:
        super().setUp()
        screen = SimpleNamespace(size=QSize(1920, 1080))
        self._screen = screen
        screen_patch = patch('src.ui.window.main_window.get_screen_size', new=lambda *_: screen.size)
        screen_patch.start()
        self.addCleanup(screen_patch.stop)
        test_size = QSize(64, 64)
        self.image_stack = ImageStack(test_size, test_size, test_size, test_size)
        self.windows: list[MainWindow] = []

    def tearDown(self) -> None:
        for window in self.windows:
            window.hide()
        super().tearDown()

    def _new_window(self) -> MainWindow:
        window = MainWindow(self.image_stack)
        self.windows.append(window)
        for dock in window.docks:
            if dock is not window.controlnet_dock:
                dock.set_content(QLabel(dock.windowTitle()))
        return window

    def test_every_bundled_layout_restores(self) -> None:
        """Each bundled layout restores at the current `DOCK_STATE_VERSION`, docks every dock, and opens Tools and
        Layers. Bumping that version fails here until the layouts are regenerated."""
        window = self._new_window()
        window.resize(1920, 1080)
        window.show()
        for name, state in BUNDLED_LAYOUTS.items():
            with self.subTest(layout=name):
                self.assertTrue(window.apply_dock_state(state))
                window.layout().activate()
                for dock in window.docks:
                    self.assertFalse(dock.isFloating(), dock.objectName())
                    self.assertNotEqual(window.dockWidgetArea(dock), Qt.DockWidgetArea.NoDockWidgetArea,
                                        dock.objectName())
                self.assertTrue(window.tools_dock.is_showing)
                self.assertTrue(window.layers_dock.is_showing)

    def test_first_layout_follows_the_screen_and_reset_follows_the_window(self) -> None:
        """A new window picks its layout by the screen size, and resetting a shown window picks by the window size."""
        with patch('src.ui.window.main_window.select_default_layout_state',
                   wraps=select_default_layout_state) as select:
            self._screen.size = QSize(1920, 1080)
            window = self._new_window()
            select.assert_called_once_with(1920, 1080)
            window.resize(1024, 600)
            window.show()
            window.reset_dock_layout()
            select.assert_called_with(1024, 600)

    def test_reset_matches_the_selected_bundled_layout(self) -> None:
        """Resetting a shown window gives the same dock layout as applying the selected bundled layout directly."""
        window = self._new_window()
        window.resize(1024, 600)
        window.show()
        window.reset_dock_layout()
        window.layout().activate()
        reset_layout = self._dock_summary(window)
        self.assertTrue(window.apply_dock_state(LAYOUT_1080P))
        window.layout().activate()
        self.assertNotEqual(self._dock_summary(window), reset_layout)
        self.assertTrue(window.apply_dock_state(LAYOUT_SMALL))
        window.layout().activate()
        self.assertEqual(self._dock_summary(window), reset_layout)

    def test_unrestorable_layout_falls_back_to_the_procedural_layout(self) -> None:
        """When the selected layout can't be restored, reset logs a warning and builds the procedural layout: every
        dock in the right area on a landscape screen, with Tools and Layers open."""
        with patch('src.ui.window.main_window.select_default_layout_state', return_value='not a layout'), \
                self.assertLogs('src.ui.window.main_window', 'WARNING'):
            window = self._new_window()
        window.resize(1280, 720)
        window.show()
        window.layout().activate()
        for dock in window.docks:
            self.assertEqual(window.dockWidgetArea(dock), Qt.DockWidgetArea.RightDockWidgetArea)
        self.assertEqual({dock for dock in window.docks if not dock.isHidden()}, {window.tools_dock, window.layers_dock})

    @staticmethod
    def _dock_summary(window: MainWindow) -> dict[str, tuple]:
        """Returns each dock's area, open state and tab group, by object name."""
        return {dock.objectName(): (window.dockWidgetArea(dock), dock.isHidden(),
                                    frozenset(mate.objectName() for mate in dock.group_mates()))
                for dock in window.docks}
