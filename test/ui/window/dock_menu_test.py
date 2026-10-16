"""Tests the dock context menu: its entries, the moves it makes, and where right-clicking opens it."""
import sys
from unittest.mock import patch

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QAction, QContextMenuEvent
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QTabBar

from src.image.layers.image_stack import ImageStack
from src.ui.window.dock_menu import DockEdge, MENU_DOCK, MENU_FLOAT, MENU_HIDE_PANEL, MENU_MOVE_ALL_TO_EDGE, \
    MENU_MOVE_TO_EDGE, MENU_TAB_WITH, edge_title, group_label
from src.ui.window.main_window import MainWindow
from src.ui.window.panel_dock import PanelDock
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

Area = Qt.DockWidgetArea


class DockMenuTest(IntraPaintTestCase):
    """Builds a MainWindow without AppController, with content in every dock but ControlNet."""

    def setUp(self) -> None:
        super().setUp()
        screen_patch = patch('src.ui.window.main_window.get_screen_size', return_value=QSize(4000, 3000))
        screen_patch.start()
        self.addCleanup(screen_patch.stop)
        test_size = QSize(64, 64)
        self.window = MainWindow(ImageStack(test_size, test_size, test_size, test_size))
        for dock in self.window.docks:
            if dock is not self.window.controlnet_dock:
                dock.set_content(QLabel(dock.windowTitle()))
        self.window.resize(1600, 1000)
        self.window.show()
        self._activate()

    def tearDown(self) -> None:
        for dock in self.window.docks:
            dock.setFloating(False)
        self.window.hide()
        super().tearDown()

    def _activate(self) -> None:
        layout = self.window.layout()
        assert layout is not None
        layout.activate()

    @staticmethod
    def _entries(menu: QMenu) -> dict[str, QAction]:
        return {action.text(): action for action in menu.actions() if not action.isSeparator()}

    def _submenu(self, dock: PanelDock, title: str) -> QMenu:
        submenu = self._entries(self.window.dock_menu(dock))[title].menu()
        assert submenu is not None
        return submenu

    def _trigger(self, dock: PanelDock, *path: str) -> None:
        """Triggers a dock menu entry, given the titles leading to it."""
        menu = self.window.dock_menu(dock)
        for title in path[:-1]:
            submenu = self._entries(menu)[title].menu()
            assert submenu is not None
            menu = submenu
        self._entries(menu)[path[-1]].trigger()
        self._activate()

    @staticmethod
    def _group(dock: PanelDock) -> set[PanelDock]:
        return {dock, *dock.group_mates()}

    def _open_docks(self) -> set[PanelDock]:
        return {dock for dock in self.window.docks if not dock.isHidden()}

    def _shown_tab_bars(self) -> list[QTabBar]:
        return [bar for bar in self.window.findChildren(QTabBar, options=Qt.FindChildOption.FindDirectChildrenOnly)
                if not bar.isHidden()]

    def test_menu_entries(self) -> None:
        """An open docked dock's menu has every entry in order, with one edge per Move to edge entry."""
        menu = self.window.dock_menu(self.window.tools_dock)
        self.assertEqual(list(self._entries(menu)),
                         [MENU_TAB_WITH, MENU_MOVE_TO_EDGE, MENU_FLOAT, MENU_HIDE_PANEL, MENU_MOVE_ALL_TO_EDGE])
        for title in (MENU_MOVE_TO_EDGE, MENU_MOVE_ALL_TO_EDGE):
            self.assertEqual(list(self._entries(self._submenu(self.window.tools_dock, title))),
                             [edge_title(edge) for edge in DockEdge])

    def test_tab_with_lists_other_groups(self) -> None:
        """Tab with lists each other docked group by its open dock, counting its closed docks with content, and leaves
        out the dock's own group."""
        window = self.window
        expected_lower = group_label([window.layers_dock, window.color_dock, window.navigation_dock])
        self.assertEqual(list(self._entries(self._submenu(window.tools_dock, MENU_TAB_WITH))), [expected_lower])
        expected_upper = group_label([window.tools_dock, window.generation_dock])
        self.assertEqual(list(self._entries(self._submenu(window.color_dock, MENU_TAB_WITH))), [expected_upper])

    def test_tab_with_lists_a_group_with_no_open_dock(self) -> None:
        """A group whose docks are all closed is still a Tab with target, labeled by its first dock."""
        window = self.window
        window.layers_dock.hide()
        self._trigger(window.tools_dock, MENU_TAB_WITH,
                      group_label([window.layers_dock, window.color_dock, window.navigation_dock]))
        self.assertIn(window.layers_dock, self._group(window.tools_dock))
        self.assertTrue(window.tools_dock.is_showing)

    def test_tab_with_joins_group(self) -> None:
        """Tab with moves the dock into the target's group as its open dock, and closes the dock that was open."""
        window = self.window
        self._trigger(window.color_dock, MENU_TAB_WITH, group_label([window.tools_dock, window.generation_dock]))
        self.assertIn(window.tools_dock, self._group(window.color_dock))
        self.assertNotIn(window.layers_dock, self._group(window.color_dock))
        self.assertTrue(window.color_dock.is_showing)
        self.assertEqual(self._open_docks(), {window.color_dock, window.layers_dock})
        self.assertEqual(self._shown_tab_bars(), [])

    def test_tab_with_disabled_without_other_groups(self) -> None:
        """With every dock in one group, Tab with is disabled."""
        window = self.window
        window.move_all_docks_to_edge(DockEdge.LEFT)
        self._activate()
        tab_with = self._entries(window.dock_menu(window.tools_dock))[MENU_TAB_WITH]
        self.assertFalse(tab_with.isEnabled())

    def test_move_to_each_edge(self) -> None:
        """Move to edge docks the dock in that edge's area, outside its old group."""
        window = self.window
        dock = window.layers_dock
        for edge in (DockEdge.LEFT, DockEdge.TOP, DockEdge.BOTTOM, DockEdge.RIGHT):
            self._trigger(dock, MENU_MOVE_TO_EDGE, edge_title(edge))
            self.assertEqual(window.dockWidgetArea(dock), edge.value, edge)
            self.assertTrue(dock.is_showing, edge)
            self.assertEqual(self._group(dock), {dock}, edge)
            self.assertEqual(self._shown_tab_bars(), [], edge)

    def test_move_to_edge_spans_the_edge(self) -> None:
        """Moving to an edge that holds docks adds a strip running the full length of that edge."""
        window = self.window
        self._trigger(window.layers_dock, MENU_MOVE_TO_EDGE, edge_title(DockEdge.BOTTOM))
        self._trigger(window.tools_dock, MENU_MOVE_TO_EDGE, edge_title(DockEdge.BOTTOM))
        self.assertTrue(window.layers_dock.geometry().bottom() < window.tools_dock.geometry().top()
                        or window.tools_dock.geometry().bottom() < window.layers_dock.geometry().top())
        self.assertEqual(window.tools_dock.width(), window.layers_dock.width())
        # Right holds two stacked groups, and the new column spans both:
        self._trigger(window.navigation_dock, MENU_MOVE_TO_EDGE, edge_title(DockEdge.RIGHT))
        self.assertGreater(window.navigation_dock.height(), window.color_dock.height())
        self.assertGreater(window.navigation_dock.height(), window.generation_dock.height())

    def test_move_to_edge_goes_outermost(self) -> None:
        """A dock moved to an edge that holds docks lands on that edge's outer side, away from the canvas."""
        window = self.window
        moved = window.navigation_dock
        others = [window.tools_dock, window.layers_dock]
        outermost = {
            DockEdge.LEFT: lambda dock: -dock.geometry().left(),
            DockEdge.RIGHT: lambda dock: dock.geometry().right(),
            DockEdge.TOP: lambda dock: -dock.geometry().top(),
            DockEdge.BOTTOM: lambda dock: dock.geometry().bottom()
        }
        for edge, extent in outermost.items():
            for dock in others:
                self._trigger(dock, MENU_MOVE_TO_EDGE, edge_title(edge))
            self._trigger(moved, MENU_MOVE_TO_EDGE, edge_title(edge))
            self.assertEqual(window.dockWidgetArea(moved), edge.value, edge)
            for dock in others:
                self.assertEqual(window.dockWidgetArea(dock), edge.value, edge)
                self.assertGreater(extent(moved), extent(dock), (edge, dock.objectName()))
            self.assertTrue(moved.is_showing, edge)

    def test_move_to_edge_opens_closed_dock(self) -> None:
        """A closed dock opens when moved, as from its rail button."""
        window = self.window
        window.color_dock.hide()
        self.assertNotIn(MENU_HIDE_PANEL, self._entries(window.dock_menu(window.color_dock)))
        self._trigger(window.color_dock, MENU_MOVE_TO_EDGE, edge_title(DockEdge.LEFT))
        self.assertTrue(window.color_dock.is_showing)
        self.assertEqual(window.dockWidgetArea(window.color_dock), Area.LeftDockWidgetArea)

    def test_float_and_dock(self) -> None:
        """Float floats the dock, and a floating dock's menu offers Dock instead."""
        window = self.window
        self._trigger(window.navigation_dock, MENU_FLOAT)
        self.assertTrue(window.navigation_dock.isFloating())
        entries = self._entries(window.dock_menu(window.navigation_dock))
        self.assertNotIn(MENU_FLOAT, entries)
        self.assertNotIn(group_label([window.navigation_dock]), self._entries(entries[MENU_TAB_WITH].menu()))
        self._trigger(window.navigation_dock, MENU_DOCK)
        self.assertFalse(window.navigation_dock.isFloating())

    def test_moving_a_floating_dock_closes_nothing(self) -> None:
        """Moving a floating dock to an edge leaves the open dock of the group it floated from open."""
        window = self.window
        self._trigger(window.color_dock, MENU_FLOAT)
        self.assertFalse(window.layers_dock.isHidden())
        self._trigger(window.color_dock, MENU_MOVE_TO_EDGE, edge_title(DockEdge.LEFT))
        self.assertEqual(self._open_docks(), {window.tools_dock, window.layers_dock, window.color_dock})

    def test_hide_panel(self) -> None:
        """Hide panel closes the dock."""
        self._trigger(self.window.layers_dock, MENU_HIDE_PANEL)
        self.assertTrue(self.window.layers_dock.isHidden())

    def test_move_all_to_edge(self) -> None:
        """Move all panels to edge puts every dock with content in one group on that edge, with the first open dock
        open and the rest closed."""
        window = self.window
        window.tools_dock.hide()
        self._trigger(window.layers_dock, MENU_MOVE_ALL_TO_EDGE, edge_title(DockEdge.LEFT))
        available = [dock for dock in window.docks if dock.is_available]
        for dock in available:
            self.assertEqual(window.dockWidgetArea(dock), Area.LeftDockWidgetArea, dock.objectName())
        self.assertEqual(self._group(window.tools_dock), set(available))
        self.assertEqual(self._open_docks(), {window.layers_dock})
        window.move_all_docks_to_edge(DockEdge.BOTTOM)
        self._activate()
        for dock in available:
            self.assertEqual(window.dockWidgetArea(dock), Area.BottomDockWidgetArea, dock.objectName())
        self.assertEqual(self._open_docks(), {window.layers_dock})
        self.assertEqual(self._shown_tab_bars(), [])

    def test_rail_button_right_click_opens_menu(self) -> None:
        """Right-clicking a rail button opens its dock's menu, though the rail blocks context menus."""
        window = self.window
        rail = window.rails.rail_for(window.layers_dock)
        button = next(button for button in rail.buttons if button.dock is window.layers_dock)
        center = button.rect().center()
        event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, center, button.mapToGlobal(center))
        with patch.object(MainWindow, '_show_dock_menu') as show_menu:
            QApplication.sendEvent(button, event)
        show_menu.assert_called_once_with(window.layers_dock, button.mapToGlobal(center))

    def test_dock_at_title(self) -> None:
        """Right-click lookup finds the dock for its title area, and none over dock content."""
        window = self.window
        dock = window.layers_dock
        title_point = QPoint(dock.width() // 2, 2)
        self.assertIs(window.dock_at(dock, dock.mapToGlobal(title_point)), dock)
        content = window.layers_dock.content
        assert content is not None
        self.assertIsNone(window.dock_at(content, content.mapToGlobal(content.rect().center())))
