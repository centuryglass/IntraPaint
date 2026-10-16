"""Tests the dock context menu: its entries, the moves it makes, and where right-clicking opens it."""
import sys
from unittest.mock import patch

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
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

    def _group(self, dock: PanelDock) -> set[PanelDock]:
        return {dock, *self.window.tabifiedDockWidgets(dock)}

    def _drawn_tab_texts(self) -> list[str]:
        """Returns the tab texts of every dock tab bar drawn inside the window. Qt parks spare bars outside it."""
        window = self.window
        bars = [bar for bar in window.findChildren(QTabBar, options=Qt.FindChildOption.FindDirectChildrenOnly)
                if not bar.isHidden() and bar.geometry().intersects(window.rect())]
        return [bar.tabText(i) for bar in bars for i in range(bar.count())]

    def test_menu_entries(self) -> None:
        """An open docked dock's menu has every entry in order, with one edge per Move to edge entry."""
        menu = self.window.dock_menu(self.window.tools_dock)
        self.assertEqual(list(self._entries(menu)),
                         [MENU_TAB_WITH, MENU_MOVE_TO_EDGE, MENU_FLOAT, MENU_HIDE_PANEL, MENU_MOVE_ALL_TO_EDGE])
        for title in (MENU_MOVE_TO_EDGE, MENU_MOVE_ALL_TO_EDGE):
            self.assertEqual(list(self._entries(self._submenu(self.window.tools_dock, title))),
                             [edge_title(edge) for edge in DockEdge])

    def test_tab_with_lists_other_groups(self) -> None:
        """Tab with lists each other docked group by its front dock, and leaves out the dock's own group."""
        window = self.window
        expected_lower = group_label([window.layers_dock, window.color_dock, window.navigation_dock])
        self.assertEqual(list(self._entries(self._submenu(window.tools_dock, MENU_TAB_WITH))), [expected_lower])
        expected_upper = group_label([window.tools_dock, window.generation_dock])
        self.assertEqual(list(self._entries(self._submenu(window.color_dock, MENU_TAB_WITH))), [expected_upper])

    def test_tab_with_joins_group(self) -> None:
        """Tab with moves the dock into the target's group, in front."""
        window = self.window
        self._trigger(window.color_dock, MENU_TAB_WITH, group_label([window.tools_dock, window.generation_dock]))
        self.assertIn(window.tools_dock, self._group(window.color_dock))
        self.assertNotIn(window.layers_dock, self._group(window.color_dock))
        self.assertTrue(window.color_dock.is_showing)
        self.assertEqual(sorted(self._drawn_tab_texts()),
                         sorted(dock.windowTitle() for dock in (window.tools_dock, window.generation_dock,
                                                                window.color_dock, window.layers_dock,
                                                                window.navigation_dock)))

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
            self.assertNotIn(dock.windowTitle(), self._drawn_tab_texts(), edge)

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

    def test_emptied_group_draws_no_tab_bar(self) -> None:
        """Moving every open dock out of a group that still holds a closed dock leaves no tab bar behind."""
        window = self.window
        self._trigger(window.tools_dock, MENU_MOVE_TO_EDGE, edge_title(DockEdge.LEFT))
        self._trigger(window.generation_dock, MENU_MOVE_TO_EDGE, edge_title(DockEdge.LEFT))
        self.assertEqual(sorted(self._drawn_tab_texts()),
                         sorted(dock.windowTitle() for dock in window.lower_docks))

    def test_hide_panel(self) -> None:
        """Hide panel closes the dock."""
        self._trigger(self.window.navigation_dock, MENU_HIDE_PANEL)
        self.assertTrue(self.window.navigation_dock.isHidden())

    def test_move_all_to_edge(self) -> None:
        """Move all panels to edge puts every dock with content in one group on that edge, and closed docks stay
        closed."""
        window = self.window
        window.color_dock.hide()
        self._trigger(window.tools_dock, MENU_MOVE_ALL_TO_EDGE, edge_title(DockEdge.LEFT))
        available = [dock for dock in window.docks if dock.is_available]
        for dock in available:
            self.assertEqual(window.dockWidgetArea(dock), Area.LeftDockWidgetArea, dock.objectName())
        self.assertTrue(window.color_dock.isHidden())
        self.assertTrue(window.controlnet_dock.isHidden())
        # tabifiedDockWidgets leaves out closed docks, so the closed dock is checked once reopened:
        window.color_dock.show()
        self._activate()
        for dock in available:
            self.assertIn(dock, self._group(window.tools_dock))
        window.move_all_docks_to_edge(DockEdge.BOTTOM)
        self._activate()
        for dock in available:
            self.assertEqual(window.dockWidgetArea(dock), Area.BottomDockWidgetArea, dock.objectName())
        self.assertEqual(sorted(self._drawn_tab_texts()), sorted(dock.windowTitle() for dock in available))

    def test_dock_at_rail_button_and_tab(self) -> None:
        """Right-click lookup finds the dock for a rail button and for a dock tab, and none over dock content."""
        window = self.window
        rail = window.rails.rail_for(window.layers_dock)
        button = next(button for button in rail.buttons if button.dock is window.layers_dock)
        self.assertIs(window.dock_at(button, button.mapToGlobal(button.rect().center())), window.layers_dock)
        bar = next(bar for bar in window.findChildren(QTabBar, options=Qt.FindChildOption.FindDirectChildrenOnly)
                   if not bar.isHidden() and window.color_dock.windowTitle() in
                   [bar.tabText(i) for i in range(bar.count())])
        index = [bar.tabText(i) for i in range(bar.count())].index(window.color_dock.windowTitle())
        self.assertIs(window.dock_at(bar, bar.mapToGlobal(bar.tabRect(index).center())), window.color_dock)
        content = window.layers_dock.content
        assert content is not None
        self.assertIsNone(window.dock_at(content, content.mapToGlobal(content.rect().center())))
