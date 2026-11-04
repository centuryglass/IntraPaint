"""Pins the main menu bar's structure and checks that each menu action's key config subcategory matches its menu."""
import sys
from typing import Any

from PySide6.QtWidgets import QApplication, QMenu

from src.config.key_config import KeyConfig
from src.controller.app_controller import AppController, MENU_FILE, MENU_EDIT, MENU_VIEW, MENU_IMAGE, MENU_LAYER, \
    MENU_SELECT, MENU_FILTERS, MENU_GENERATION, MENU_WINDOW, MENU_HELP
from src.util.arg_parser import build_arg_parser
from src.util.menu_builder import MENU_DATA_ATTR, IS_MENU_ACTION_ATTR
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

SNAPSHOT_PATH = 'test/resources/menu_snapshots/mock_mode_menu_bar.json'
SEPARATOR = '----'
SUBCATEGORY_FOR_MENU = {
    MENU_FILE: 'File Menu',
    MENU_EDIT: 'Edit Menu',
    MENU_VIEW: 'View Menu',
    MENU_IMAGE: 'Image Menu',
    MENU_LAYER: 'Layer Menu',
    MENU_SELECT: 'Select Menu',
    MENU_FILTERS: 'Filters Menu',
    MENU_GENERATION: 'Generation Menu',
    MENU_WINDOW: 'Window Menu',
    MENU_HELP: 'Help Menu'
}


def _menu_tree(menu: QMenu) -> list[Any]:
    """Lists a menu's visible entries in order: labels, separators, and {submenu title: entries} for submenus."""
    entries: list[Any] = []
    for action in menu.actions():
        if not action.isVisible():
            continue
        if action.isSeparator():
            entries.append(SEPARATOR)
        elif action.menu() is not None:
            submenu = action.menu()
            assert submenu is not None
            entries.append({action.text(): _menu_tree(submenu)})
        else:
            entries.append(action.text() + (' [checkable]' if action.isCheckable() else ''))
    # Qt collapses separators that touch each other or the menu's ends, so the snapshot does too:
    shown: list[Any] = []
    for entry in entries:
        if entry == SEPARATOR and (len(shown) == 0 or shown[-1] == SEPARATOR):
            continue
        shown.append(entry)
    if len(shown) > 0 and shown[-1] == SEPARATOR:
        shown.pop()
    return shown


class TestAppControllerMenus(IntraPaintTestCase):
    """Tests the menu bar built by `AppController`."""

    def setUp(self):
        super().setUp()
        args = build_arg_parser(include_edit_params=False).parse_args(['--window_size', '800x600', '--mode', 'mock'])
        args.mode = 'mock'
        args.server_url = ''
        args.fast_ngrok_connection = False
        self.controller = AppController(args)

    def test_menu_bar_structure(self):
        """The menu bar's menus, order, separators, submenus and checkable entries match the snapshot."""
        menu_bar = self.controller._window.menuBar()
        tree = {}
        order = []
        for menu_action in menu_bar.actions():
            menu = menu_action.menu()
            if menu is None or not menu_action.isVisible():
                continue
            order.append(menu_action.text())
            tree[menu_action.text()] = _menu_tree(menu)
        self.assert_json_matches_snapshot({'menu_order': order, 'menus': tree}, SNAPSHOT_PATH)

    def test_menu_action_subcategories_match_menus(self):
        """Each @menu_action's key config subcategory names the menu that holds it."""
        key_config = KeyConfig()
        checked = 0
        for attr_name in dir(self.controller):
            method = getattr(self.controller, attr_name, None)
            if not callable(method) or not getattr(method, IS_MENU_ACTION_ATTR, False):
                continue
            data = getattr(method, MENU_DATA_ATTR)
            top_menu = data.menu_name.split('.')[0]
            self.assertEqual(key_config.get_subcategory(data.config_key), SUBCATEGORY_FOR_MENU[top_menu],
                             f'{data.config_key} is in the {top_menu} menu')
            checked += 1
        self.assertGreater(checked, 50)

    def test_menu_titles_have_unique_mnemonics(self):
        """Each top-level menu title has one accelerator, and no two menus share it."""
        letters = []
        for title in SUBCATEGORY_FOR_MENU:
            self.assertEqual(title.count('&'), 1, title)
            letters.append(title[title.index('&') + 1].lower())
        self.assertEqual(len(set(letters)), len(letters))
