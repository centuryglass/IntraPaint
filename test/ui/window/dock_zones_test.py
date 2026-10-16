"""Tests the named dock zones: zone detection, moving docks between zones and groups, and the dock context menu."""
import sys
from unittest.mock import patch

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QTabBar

from src.image.layers.image_stack import ImageStack
from src.ui.window.dock_zones import DockZone, MENU_HIDE_PANEL, MENU_MOVE_ALL_TO, MENU_MOVE_TO, \
    MENU_MOVE_TO_LOWER_GROUP, MENU_MOVE_TO_UPPER_GROUP, move_dock_to_zone, zone_of, zone_title
from src.ui.window.main_window import MainWindow
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

Area = Qt.DockWidgetArea


class DockZonesTest(IntraPaintTestCase):
    """Builds a MainWindow without AppController, with content in every dock but ControlNet."""

    def setUp(self) -> None:
        super().setUp()
        screen_patch = patch('src.ui.window.main_window.get_screen_size', return_value=QSize(4000, 3000))
        screen_patch.start()
        self.addCleanup(screen_patch.stop)
        test_size = QSize(64, 64)
        self.window = MainWindow(ImageStack(test_size, test_size, test_size, test_size))
        for dock in self.window.docks[:2] + self.window.docks[3:]:
            dock.set_content(QLabel(dock.windowTitle()))
        self.window.resize(1600, 1000)
        self.window.show()
        self.window.layout().activate()

    def tearDown(self) -> None:
        self.window.hide()
        super().tearDown()

    def _menu_entries(self, menu: QMenu) -> dict[str, object]:
        return {action.text(): action for action in menu.actions() if not action.isSeparator()}

    def _zone_actions(self, menu: QMenu, title: str) -> dict[str, object]:
        submenu = self._menu_entries(menu)[title].menu()
        return self._menu_entries(submenu)

    def _shown_tab_bars(self) -> list[QTabBar]:
        window = self.window
        return [bar for bar in window.findChildren(QTabBar, options=Qt.FindChildOption.FindDirectChildrenOnly)
                if not bar.isHidden() and bar.geometry().intersects(window.rect())]

    def test_zone_titles_are_distinct(self) -> None:
        """Every zone has its own name."""
        self.assertEqual(len({zone_title(zone) for zone in DockZone}), len(DockZone))

    def test_first_run_zone(self) -> None:
        """The first-run layout is in the Right zone."""
        for dock in self.window.docks:
            self.assertEqual(zone_of(self.window, dock), DockZone.RIGHT)

    def test_move_to_each_zone(self) -> None:
        """Moving a dock to a zone puts it in that zone, including the bottom rows."""
        window = self.window
        dock = window.layers_dock
        for zone in (DockZone.LEFT, DockZone.TOP, DockZone.BOTTOM_UPPER, DockZone.BOTTOM_LOWER, DockZone.RIGHT):
            move_dock_to_zone(window, dock, zone)
            window.layout().activate()
            expected = DockZone.BOTTOM_UPPER if zone == DockZone.BOTTOM_LOWER else zone
            self.assertEqual(zone_of(window, dock), expected, zone)
            self.assertTrue(dock.isVisible())

    def test_lower_row_is_created_and_removed(self) -> None:
        """Moving to the lower bottom row splits the bottom area, and moving the last dock out removes the row."""
        window = self.window
        move_dock_to_zone(window, window.tools_dock, DockZone.BOTTOM_UPPER)
        move_dock_to_zone(window, window.layers_dock, DockZone.BOTTOM_LOWER)
        window.layout().activate()
        self.assertEqual(zone_of(window, window.tools_dock), DockZone.BOTTOM_UPPER)
        self.assertEqual(zone_of(window, window.layers_dock), DockZone.BOTTOM_LOWER)
        self.assertLess(window.tools_dock.geometry().bottom(), window.layers_dock.geometry().top())
        self.assertGreaterEqual(window.layers_dock.width(), window.tools_dock.width())
        move_dock_to_zone(window, window.layers_dock, DockZone.RIGHT)
        window.layout().activate()
        self.assertEqual(zone_of(window, window.tools_dock), DockZone.BOTTOM_UPPER)
        move_dock_to_zone(window, window.navigation_dock, DockZone.BOTTOM_LOWER)
        window.layout().activate()
        self.assertEqual(zone_of(window, window.navigation_dock), DockZone.BOTTOM_LOWER)
        # No tab appears in two drawn tab bars, which would mean a stale bar over the window:
        texts = [bar.tabText(i) for bar in self._shown_tab_bars() for i in range(bar.count())]
        self.assertEqual(len(texts), len(set(texts)))

    def test_current_zone_is_checked_and_disabled(self) -> None:
        """The dock menu's Move to submenu checks and disables the dock's zone only."""
        window = self.window
        entries = self._zone_actions(window.dock_menu(window.tools_dock), MENU_MOVE_TO)
        self.assertEqual(list(entries), [zone_title(zone) for zone in DockZone])
        for zone in DockZone:
            action = entries[zone_title(zone)]
            self.assertEqual(action.isChecked(), zone == DockZone.RIGHT)
            self.assertEqual(action.isEnabled(), zone != DockZone.RIGHT)

    def test_menu_moves_dock(self) -> None:
        """Triggering a Move to entry moves the dock."""
        window = self.window
        entries = self._zone_actions(window.dock_menu(window.color_dock), MENU_MOVE_TO)
        entries[zone_title(DockZone.LEFT)].trigger()
        self.assertEqual(zone_of(window, window.color_dock), DockZone.LEFT)
        self.assertEqual(zone_of(window, window.layers_dock), DockZone.RIGHT)

    def test_move_all_tabs(self) -> None:
        """Move all tabs to moves every dock with content, from the dock menu and the window method."""
        window = self.window
        entries = self._zone_actions(window.dock_menu(window.tools_dock), MENU_MOVE_ALL_TO)
        entries[zone_title(DockZone.LEFT)].trigger()
        window.layout().activate()
        for dock in window.docks:
            if dock.is_available:
                self.assertEqual(zone_of(window, dock), DockZone.LEFT, dock.objectName())
        self.assertTrue(window.controlnet_dock.isHidden())
        window.move_all_docks_to_zone(DockZone.BOTTOM_LOWER)
        window.layout().activate()
        for dock in window.docks:
            if dock.is_available:
                self.assertEqual(zone_of(window, dock), DockZone.BOTTOM_UPPER, dock.objectName())

    def test_group_move(self) -> None:
        """A side-area dock can move between the upper and lower groups."""
        window = self.window
        menu = window.dock_menu(window.tools_dock)
        self.assertIn(MENU_MOVE_TO_LOWER_GROUP, self._menu_entries(menu))
        self._menu_entries(menu)[MENU_MOVE_TO_LOWER_GROUP].trigger()
        window.layout().activate()
        self.assertIn(window.layers_dock, window.tabifiedDockWidgets(window.tools_dock))
        self.assertIn(MENU_MOVE_TO_UPPER_GROUP, self._menu_entries(window.dock_menu(window.tools_dock)))
        self._menu_entries(window.dock_menu(window.tools_dock))[MENU_MOVE_TO_UPPER_GROUP].trigger()
        window.layout().activate()
        self.assertIn(window.generation_dock, window.tabifiedDockWidgets(window.tools_dock))
        self.assertNotIn(window.layers_dock, window.tabifiedDockWidgets(window.tools_dock))

    def test_group_move_needs_side_area(self) -> None:
        """Bottom-area docks have no group entry."""
        window = self.window
        move_dock_to_zone(window, window.tools_dock, DockZone.BOTTOM_UPPER)
        self.assertNotIn(MENU_MOVE_TO_LOWER_GROUP, self._menu_entries(window.dock_menu(window.tools_dock)))
        self.assertNotIn(MENU_MOVE_TO_UPPER_GROUP, self._menu_entries(window.dock_menu(window.tools_dock)))

    def test_hide_panel(self) -> None:
        """Hide panel closes the dock."""
        window = self.window
        self._menu_entries(window.dock_menu(window.navigation_dock))[MENU_HIDE_PANEL].trigger()
        self.assertTrue(window.navigation_dock.isHidden())
