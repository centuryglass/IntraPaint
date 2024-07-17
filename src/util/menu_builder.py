"""Defines the @menu_action decorator and the MenuBuilder class for more convenient PyQt6 menu initialization."""
import inspect
from functools import wraps
from inspect import signature
from typing import Callable, Any, Optional, TypeVar, Dict, List

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMainWindow, QMenu

from src.config.key_config import KeyConfig
from src.util.application_state import AppStateTracker
from src.util.shared_constants import INT_MAX

GenericFn = TypeVar('GenericFn', bound=Callable[..., Any])


def menu_action(menu_name: str, config_key: str, priority: int = INT_MAX,
                valid_app_states: Optional[List[str]] = None,
                condition_check: Optional[Callable[[Any], bool]] = None) -> Callable[[GenericFn], GenericFn]:
    """Decorator used to associate a class method with a menu item and optionally disable it when busy.

    Parameters
    ----------
    menu_name: str
        Name of the menu where the method action will be added
    config_key: str
        AppConfig key for the menu item's label, tooltip, and shortcut.
    priority: int, default=MAX_INT
        Order to place this item in its menu. Items with the lowest values are added first.
    valid_app_states: string list, optional
        If present, the menu option will only be enabled when the application is in one of the specified states.
    condition_check: Optional function returning bool
        If not none, this function will be evaluated when the menu is initialized, and the menu option will not
        be added unless it returns true. The parameter passed in will be object initializing the menus.
    """

    def _decorator(func):
        @wraps(func)
        def _wrapper(*args, **kwargs):
            # Discard any unwanted signal parameters that the function won't accept:
            params = signature(func).parameters
            num_positional_params = 0
            for param in params.values():
                if param.kind == inspect.Parameter.KEYWORD_ONLY:
                    break
                num_positional_params += 1
            args = args[:num_positional_params]
            return func(*args, **kwargs)
        setattr(_wrapper, 'menu_name', menu_name)
        setattr(_wrapper, 'config_key', config_key)
        setattr(_wrapper, 'valid_app_states', valid_app_states)
        setattr(_wrapper, 'is_menu_action', True)
        setattr(_wrapper, 'priority', priority)
        setattr(_wrapper, 'condition_check', condition_check)
        return _wrapper
    return _decorator


class MenuBuilder:
    """Provides the build_menus method to initialize menus from annotated methods."""

    def __init__(self) -> None:
        self._menus: Dict[str, QMenu] = {}
        self._actions: Dict[str, List[QAction]] = {}

    def add_menu_action(self,
                        window: QMainWindow,
                        menu_name: str,
                        new_action: Callable[..., None],
                        config_key: Optional[str] = None,
                        title: Optional[str] = None,
                        tooltip: Optional[str] = None,
                        keybinding: Optional[str] = None) -> Optional[QAction]:
        """Adds a new menu action to a window, or return an existing action with the same name.

        Parameters
        ----------
        window: QMainWindow
            The new menu action will be added to this window.
        menu_name: str
            Name of the menu where the action will be added. If the menu does not yet exist, it will be created.
        new_action: Callable
            Function to run when the option is selected.
        config_key: str, optional
            If provided, will be used to load menu item info from KeyConfig. Config data will override title, tooltip
            and keybinding parameters only when those parameters are null or empty.
        title: str, optional
            Displayed title for the new menu option. If None, config_key cannot be None.
        tooltip: str, optional
            Tooltip to display over the new menu option.
        keybinding: str, optional
            A hotkey that should trigger this menu option.
        """
        menu_bar = window.menuBar()
        assert menu_bar is not None
        if menu_name in self._menus:
            menu: Optional[QMenu] = self._menus[menu_name]
        else:
            # Check if menu exists but was added elsewhere:
            menu = None
            for action in menu_bar.actions():
                possible_menu = action.menu()
                if possible_menu is not None and possible_menu.title() == title:
                    menu = possible_menu
                    break
            if menu is None:
                menu = QMenu(menu_name)
                menu_bar.addMenu(menu)
            self._menus[menu_name] = menu
            self._actions[menu_name] = []
        assert menu is not None
        try:
            if config_key is not None:
                config = KeyConfig()
                if title is None or title == '':
                    title = config.get_label(config_key)
                if tooltip is None or tooltip == '':
                    tooltip = config.get_tooltip(config_key)
                if keybinding is None or keybinding == '':
                    keybinding = config.get(config_key)
            if title is None or title == '':
                raise RuntimeError('Missing menu action title')
        except RuntimeError:
            print(f'Warning: could not load menu option {config_key}, skipping...')
            return None
        _menu_set_visible(menu, True)
        for existing_action in self._actions[menu_name]:
            if existing_action.text() == title:
                return existing_action
        action = QAction(title)
        if tooltip is not None and tooltip != '':
            action.setToolTip(tooltip)
        if keybinding is not None and keybinding != '':
            action.setShortcut(keybinding)
        action.triggered.connect(lambda: new_action())
        if config_key is not None and config_key != '':
            KeyConfig().connect(self, config_key, lambda key_str: action.setShortcut(key_str))

        menu.addAction(action)
        self._actions[menu_name].append(action)
        return action

    @property
    def menu_names(self) -> List[str]:
        """Access the list of created menu names."""
        return list(self._menus.keys())

    def menu_actions(self, menu_name: str) -> List[QAction]:
        """Access all actions within a particular menu."""
        if menu_name not in self._actions:
            raise KeyError(f'Menu {menu_name} not found.')
        return [*self._actions[menu_name]]

    def remove_menu_action(self, window: QMainWindow, menu_name: str, action_name: str) -> None:
        """Removes an action from the menu."""
        menu_bar = window.menuBar()
        assert menu_bar is not None
        if menu_name not in self._menus:
            return
        menu = self._menus[menu_name]
        for action in menu.actions():
            if action.text() == action_name:
                menu.removeAction(action)
                self._actions[menu_name].remove(action)
                action.deleteLater()
                break
        if len(menu.actions()) == 0:
            _menu_set_visible(menu, False)

    # noinspection PyUnresolvedReferences
    def build_menus(self, window: QMainWindow) -> None:
        """Add all @menu_action methods from this class to the window as menu items."""
        menu_actions = []
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if callable(attr) and getattr(attr, 'is_menu_action', False):
                menu_actions.append(attr)
        menu_actions.sort(key=lambda method: method.priority)

        menu_bar = window.menuBar()
        assert menu_bar is not None
        for menu_action_method in menu_actions:
            menu_name = menu_action_method.menu_name
            key = menu_action_method.config_key
            title = KeyConfig().get_label(key)
            # Check if the action already exists. If so, remove it if checks are no longer passing.
            if menu_name in self._menus:
                for existing_action in self._actions[menu_name]:
                    if existing_action.text() == title:
                        if menu_action_method.condition_check is not None and menu_action_method.condition_check(
                                self) is False:
                            self.remove_menu_action(window, menu_name, title)
                        continue
            # If not blocked by condition checks, create and add the new item:
            if menu_action_method.condition_check is not None and menu_action_method.condition_check(self) is False:
                continue
            action = self.add_menu_action(window, menu_name, menu_action_method, key)
            if action is not None and menu_action_method.valid_app_states is not None:
                AppStateTracker.set_enabled_states(action, menu_action_method.valid_app_states)

    def clear_menus(self) -> None:
        """Remove all @menu_action methods that this class added to the menu"""
        for menu_name, menu in self._menus.items():
            while len(self._actions[menu_name]) > 0:
                action = self._actions[menu.title()].pop()
                menu.removeAction(action)
                action.deleteLater()
            if len(menu.actions()) == 0:
                _menu_set_visible(menu, False)


def _menu_set_visible(menu: QMenu, visible: bool) -> None:
    main_menu_action = menu.menuAction()
    assert main_menu_action is not None
    main_menu_action.setVisible(visible)
