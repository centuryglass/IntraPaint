"""Tests how MainWindow places tabs in its tab boxes, moves them between boxes, and shows dividers."""
import sys
from unittest.mock import patch

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from src.config.cache import Cache
from src.image.layers.image_stack import ImageStack
from src.ui.layout.draggable_tabs.tab import Tab
from src.ui.layout.draggable_tabs.tab_box import TabBox
from src.ui.window.main_window import MainWindow, TabBoxID, ACTION_NAME_MOVE_LEFT, ACTION_NAME_MOVE_RIGHT, \
    ACTION_NAME_MOVE_UP, ACTION_NAME_MOVE_DOWN, ACTION_NAME_MOVE_ALL, AUTO_TAB_MOVE_THRESHOLD, \
    USE_LOWER_CONTROL_TAB_THRESHOLD
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

LARGE_SCREEN = QSize(4000, 4000)


def finish_open(box: TabBox) -> None:
    """Completes a pending open without waiting on the tab bar's open-delay timer."""
    box._tab_bar._finish_tab_open()  # pylint: disable=protected-access


def _content(min_size: QSize = QSize(0, 0)) -> QWidget:
    content = QLabel('content')
    content.setMinimumSize(min_size)
    return content


class MainWindowTabLayoutTest(IntraPaintTestCase):
    """Builds a MainWindow without AppController, on a screen large enough for any window size used."""

    def setUp(self) -> None:
        super().setUp()
        screen_patch = patch('src.ui.window.main_window.get_screen_size', return_value=LARGE_SCREEN)
        screen_patch.start()
        self.addCleanup(screen_patch.stop)
        test_size = QSize(64, 64)
        self.image_stack = ImageStack(test_size, test_size, test_size, test_size)
        self.window = MainWindow(self.image_stack)
        self.window.resize(1000, 800)
        self.window.show()

    def tearDown(self) -> None:
        for box_id in TabBoxID:
            self._box(box_id)._tab_bar._tab_open_timer.stop()  # pylint: disable=protected-access
        self.window.hide()
        super().tearDown()

    def _box(self, box_id: TabBoxID) -> TabBox:
        return self.window._get_tab_box(box_id)  # pylint: disable=protected-access

    def _box_of(self, tab: Tab) -> TabBoxID:
        found = [box_id for box_id in TabBoxID if self._box(box_id).contains_widget(tab)]
        self.assertEqual(len(found), 1)
        return found[0]

    @staticmethod
    def _trigger(tab: Tab, action_name: str) -> None:
        matches = [action for action in tab.actions() if action.text() == action_name]
        assert len(matches) == 1, f'expected one "{action_name}" action, found {len(matches)}'
        matches[0].trigger()

    @staticmethod
    def _action_names(tab: Tab) -> set[str]:
        return {action.text() for action in tab.actions()}

    def test_default_box_depends_on_window_height(self) -> None:
        """Without a box ID, tabs go right, then to the lower box, then the bottom box as the window gets taller."""
        expected = ((AUTO_TAB_MOVE_THRESHOLD, TabBoxID.RIGHT_TAB_BOX_ID),
                    (AUTO_TAB_MOVE_THRESHOLD + 1, TabBoxID.LOWER_TAB_BOX_ID),
                    (USE_LOWER_CONTROL_TAB_THRESHOLD + 1, TabBoxID.BOTTOM_TAB_BOX_ID))
        for height, box_id in expected:
            self.window.resize(1000, height)
            self.assertEqual(self.window.height(), height)
            tab = Tab(f'tab at {height}', _content())
            self.window.add_tab(tab)
            self.assertEqual(self._box_of(tab), box_id, f'height {height}')

    def test_explicit_box(self) -> None:
        """A box ID overrides the height rule."""
        tab = Tab('tab', _content())
        self.window.add_tab(tab, TabBoxID.TOP_TAB_BOX_ID)
        self.assertEqual(self._box_of(tab), TabBoxID.TOP_TAB_BOX_ID)

    def test_move_actions_match_box(self) -> None:
        """Each box offers only the moves that lead somewhere else."""
        expected = {
            TabBoxID.RIGHT_TAB_BOX_ID: {ACTION_NAME_MOVE_LEFT, ACTION_NAME_MOVE_UP, ACTION_NAME_MOVE_DOWN},
            TabBoxID.LEFT_TAB_BOX_ID: {ACTION_NAME_MOVE_RIGHT, ACTION_NAME_MOVE_UP, ACTION_NAME_MOVE_DOWN},
            TabBoxID.TOP_TAB_BOX_ID: {ACTION_NAME_MOVE_LEFT, ACTION_NAME_MOVE_RIGHT, ACTION_NAME_MOVE_DOWN},
            TabBoxID.LOWER_TAB_BOX_ID: {ACTION_NAME_MOVE_LEFT, ACTION_NAME_MOVE_RIGHT, ACTION_NAME_MOVE_UP,
                                        ACTION_NAME_MOVE_DOWN},
            TabBoxID.BOTTOM_TAB_BOX_ID: {ACTION_NAME_MOVE_LEFT, ACTION_NAME_MOVE_RIGHT, ACTION_NAME_MOVE_UP},
        }
        for box_id, names in expected.items():
            tab = Tab(f'{box_id} tab', _content())
            self.window.add_tab(tab, box_id)
            self.assertEqual(self._action_names(tab), names, box_id)

    def test_move_actions_walk_between_boxes(self) -> None:
        """Move actions carry a tab around every box, updating its actions and the cached box at each step."""
        tab = Tab('tab', _content())
        self.window.add_tab(tab, TabBoxID.RIGHT_TAB_BOX_ID)
        steps = ((ACTION_NAME_MOVE_LEFT, TabBoxID.LEFT_TAB_BOX_ID),
                 (ACTION_NAME_MOVE_UP, TabBoxID.TOP_TAB_BOX_ID),
                 (ACTION_NAME_MOVE_DOWN, TabBoxID.LOWER_TAB_BOX_ID),
                 (ACTION_NAME_MOVE_DOWN, TabBoxID.BOTTOM_TAB_BOX_ID),
                 (ACTION_NAME_MOVE_UP, TabBoxID.LOWER_TAB_BOX_ID),
                 (ACTION_NAME_MOVE_RIGHT, TabBoxID.RIGHT_TAB_BOX_ID))
        for action_name, box_id in steps:
            self._trigger(tab, action_name)
            self.assertEqual(self._box_of(tab), box_id)
            self.assertEqual(Cache().get(Cache.CONTROLNET_TAB_BAR), box_id)

    def test_move_all_tabs_here(self) -> None:
        """The tab bar's "move all" action gathers every tab into that box."""
        tabs = []
        for box_id in TabBoxID:
            tab = Tab(f'{box_id} tab', _content())
            self.window.add_tab(tab, box_id)
            tabs.append(tab)
        top_box = self._box(TabBoxID.TOP_TAB_BOX_ID)
        # pylint: disable-next=protected-access
        move_all = [action for action in top_box._tab_bar.actions() if action.text() == ACTION_NAME_MOVE_ALL]
        self.assertEqual(len(move_all), 1)
        move_all[0].trigger()
        self.assertEqual(set(top_box.tabs), set(tabs))
        for box_id in TabBoxID:
            if box_id != TabBoxID.TOP_TAB_BOX_ID:
                self.assertEqual(self._box(box_id).count, 0)

    def test_remove_tab_from_any_box(self) -> None:
        """remove_tab finds the tab in whichever box holds it."""
        tab = Tab('tab', _content())
        self.window.add_tab(tab, TabBoxID.LEFT_TAB_BOX_ID)
        self.window.remove_tab(tab)
        self.assertFalse(any(self._box(box_id).contains_widget(tab) for box_id in TabBoxID))

    def test_divider_shows_only_for_open_box_with_tabs(self) -> None:
        """A box's divider is hidden while the box is empty or closed."""
        divider = self.window._top_divider  # pylint: disable=protected-access
        box = self._box(TabBoxID.TOP_TAB_BOX_ID)
        self.assertTrue(divider.isHidden())
        tab = Tab('tab', _content())
        self.window.add_tab(tab, TabBoxID.TOP_TAB_BOX_ID)
        finish_open(box)
        self.assertFalse(divider.isHidden())
        box.is_open = False
        self.assertTrue(divider.isHidden())
        box.is_open = True
        finish_open(box)
        self.window.remove_tab(tab)
        self.assertTrue(divider.isHidden())

    def test_opening_a_tall_box_closes_side_boxes(self) -> None:
        """Opening a top box whose content would overflow the window height closes the open side box."""
        self.window.resize(1000, 600)
        right_box = self._box(TabBoxID.RIGHT_TAB_BOX_ID)
        self.window.add_tab(Tab('side', _content(QSize(100, 100))), TabBoxID.RIGHT_TAB_BOX_ID)
        finish_open(right_box)
        self.assertTrue(right_box.is_open)
        self.window.add_tab(Tab('tall', _content(QSize(100, 450))), TabBoxID.TOP_TAB_BOX_ID)
        self.assertFalse(right_box.is_open)

    def test_opening_a_short_box_keeps_side_boxes(self) -> None:
        """Opening a top box that fits leaves the side box open."""
        self.window.resize(1000, 600)
        right_box = self._box(TabBoxID.RIGHT_TAB_BOX_ID)
        self.window.add_tab(Tab('side', _content(QSize(100, 100))), TabBoxID.RIGHT_TAB_BOX_ID)
        finish_open(right_box)
        self.window.add_tab(Tab('short', _content(QSize(100, 50))), TabBoxID.TOP_TAB_BOX_ID)
        self.assertTrue(right_box.is_open)
