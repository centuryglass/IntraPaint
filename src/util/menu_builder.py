"""Defines the @menu_action decorator and the MenuBuilder class for more convenient Qt6 menu initialization."""
import inspect
import logging
from functools import wraps
from inspect import signature
from typing import Callable, Any, Optional, TypeVar

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QMenu, QMenuBar

from src.config.key_config import KeyConfig
from src.util.application_state import AppStateTracker
from src.util.shared_constants import INT_MAX

GenericFn = TypeVar('GenericFn', bound=Callable[..., Any])

IS_MENU_ACTION_ATTR = '_is_menu_action'
MENU_DATA_ATTR = '_menu_data'

logger = logging.getLogger(__name__)


def menu_action(menu_name: str, config_key: str, priority: int = INT_MAX,
                valid_app_states: Optional[list[str]] = None,
                condition_check: Optional[Callable[[Any], bool]] = None) -> Callable[[GenericFn], GenericFn]:
    """Decorator used to associate a class method with a menu item and optionally disable it when busy.

    Parameters
    ----------
    menu_name: str
        Name of the menu where the method action will be added
    config_key: str
        KeyConfig key for the menu item's label, tooltip, and shortcut.
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
        menu_data = MenuData(menu_name, config_key, priority, valid_app_states, condition_check)
        setattr(_wrapper, IS_MENU_ACTION_ATTR, True)
        setattr(_wrapper, MENU_DATA_ATTR, menu_data)
        return _wrapper
    return _decorator


class MenuBuilder:
    """Provides the build_menus method to initialize menus from annotated methods."""

    def __init__(self) -> None:
        self._menus: dict[str, QMenu] = {}
        self._menu_window: Optional[QMainWindow] = None

    @property
    def menu_window(self) -> Optional[QMainWindow]:
        """Returns the associated window where this object may add or remove menus."""
        return self._menu_window

    @menu_window.setter
    def menu_window(self, window: QMainWindow) -> None:
        self._menu_window = window

    def add_menu_action(self,
                        menu_name: str,
                        new_action: Callable[..., None],
                        config_key: Optional[str] = None,
                        title: Optional[str] = None,
                        tooltip: Optional[str] = None,
                        keybinding: Optional[str] = None) -> Optional[QAction]:
        """Adds a new menu action to a window, or return an existing action with the same name.

        Parameters
        ----------
        menu_name: str
            Name of the menu where the action will be added. If the menu does not yet exist, it will be created. Nested
            menus can be selected by splitting menu names with periods, e.g. "menu.submenu".
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
        assert self._menu_window is not None, 'Assign a window before adding menu actions'
        menu = self._find_or_add_menu(menu_name)
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
        except RuntimeError as err:
            logger.error(f'Failed to load menu option {config_key}: {err}')
            return None
        _menu_set_visible(menu, True)
        existing_action = self._find_action(menu, title)
        if existing_action is not None:
            if not existing_action.isVisible():
                existing_action.setVisible(True)
                existing_action.setEnabled(True)
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
        return action

    def set_action_enabled(self, menu_name: str, action_name: str, enabled: bool) -> None:
        """Enables or disables a menu action."""
        action = self._find_action(menu_name, action_name)
        if action is not None:
            action.setEnabled(enabled)

    @property
    def menu_names(self) -> list[str]:
        """Access the list of created menu names."""
        return list(self._menus.keys())

    def menu_actions(self, menu_name: str) -> list[QAction]:
        """Access all actions within a particular menu."""
        menu = self._find_or_add_menu(menu_name, False)
        if menu is None:
            return []
        return menu.actions()

    def remove_menu_action(self, menu_name: str, action_name: str) -> None:
        """Removes an action from the menu."""
        assert self._menu_window is not None, 'Assign a window before removing menu actions'
        menu = self._find_or_add_menu(menu_name, False)
        if menu is None:
            return
        action = self._find_action(menu, action_name)
        if action is None:
            return
        if action.isEnabled():
            action.setEnabled(False)
            action.setVisible(False)
            AppStateTracker.disconnect_from_state(action)
        if len([act for act in menu.actions() if act.isEnabled()]) == 0:
            _menu_set_visible(menu, False)

    # noinspection PyUnresolvedReferences
    def build_menus(self) -> None:
        """Add all @menu_action methods from this class to the window as menu items."""
        assert self._menu_window is not None, 'Assign a window before building menus'
        action_definitions: list[tuple['MenuData', Callable[..., None]]] = self._get_action_definitions()
        menu_bar = self._menu_window.menuBar()
        assert menu_bar is not None
        for menu_data, menu_action_method in action_definitions:
            menu_name = menu_data.menu_name
            key = menu_data.config_key
            title = KeyConfig().get_label(key)

            # Make sure any condition check passes before adding/restoring the menu item:
            if menu_data.condition_check is not None and menu_data.condition_check(self) is False:
                # Blocked by the condition check, disable the action if it's already present:
                existing_action = self._find_action(menu_name, title)
                if existing_action is not None:
                    self.remove_menu_action(menu_name, title)
                continue

            # Condition check passed, add or restore menu item:
            action = self.add_menu_action(menu_name, menu_action_method, key)
            if action is not None and menu_data.valid_app_states is not None:
                AppStateTracker.set_enabled_states(action, menu_data.valid_app_states)

    def clear_menus(self) -> None:
        """Remove all @menu_action methods that this class added to the menu"""
        action_definitions: list[tuple['MenuData', Callable[..., None]]] = self._get_action_definitions()
        for menu_data, menu_action_method in action_definitions:
            action_name = KeyConfig().get_label(menu_data.config_key)
            self.remove_menu_action(menu_data.menu_name, action_name)

    def get_action_for_method(self, method: Callable[..., None]) -> QAction:
        """Returns the menu action defined by a method, or None if that action isn't present."""
        assert self._menu_window is not None, 'Assign a window before finding menus'
        if not callable(method) or not getattr(method, IS_MENU_ACTION_ATTR, False):
            raise TypeError(f'Invalid method: {method}')
        menu_data = getattr(method, MENU_DATA_ATTR, None)
        assert isinstance(menu_data, MenuData)
        action_name = KeyConfig().get_label(menu_data.config_key)
        action = self._find_action(menu_data.menu_name, action_name)
        if action is None:
            raise ValueError('Failed to find menu action for method')
        return action

    def _find_or_add_menu(self, menu_name: str, create_if_missing: bool = True) -> Optional[QMenu]:
        assert self._menu_window is not None, 'Assign a window before finding menus'
        if menu_name in self._menus:
            return self._menus[menu_name]
        menu_bar = self._menu_window.menuBar()
        assert menu_bar is not None
        menu_iter: QMenuBar | QMenu = menu_bar
        full_menu_name = ''
        for submenu_name in menu_name.split('.'):
            if len(full_menu_name) > 0:
                full_menu_name += '.'
            full_menu_name += submenu_name
            next_menu: Optional[QMenu] = None
            if full_menu_name in self._menus:
                next_menu = self._menus[full_menu_name]
            else:
                for action in menu_iter.actions():
                    possible_menu: Optional[QMenu] = action.menu()
                    if _action_has_title(possible_menu, submenu_name):
                        next_menu = possible_menu
                        if full_menu_name not in self._menus:
                            assert next_menu is not None
                            self._menus[full_menu_name] = next_menu
                        break
                if next_menu is None:
                    if not create_if_missing:
                        return None
                    next_menu = menu_iter.addMenu(submenu_name)
                    assert next_menu is not None
                    self._menus[full_menu_name] = next_menu
            assert next_menu is not None
            menu_iter = next_menu
        assert menu_iter == self._menus[menu_name]
        return menu_iter

    def _find_action(self, menu: Optional[str | QMenu], action_name: str) -> Optional[QAction]:
        if isinstance(menu, str):
            menu = self._find_or_add_menu(menu, False)
        if menu is None:
            return None
        assert isinstance(menu, QMenu)
        for action in menu.actions():
            if _action_has_title(action, action_name):
                return action
        return None

    def _get_action_definitions(self) -> list[tuple['MenuData', Callable[..., None]]]:
        action_definitions: list[tuple['MenuData', Callable[..., None]]] = []
        for attr_name in dir(self):
            if not hasattr(self, attr_name):
                continue
            attr = getattr(self, attr_name)
            if callable(attr) and getattr(attr, IS_MENU_ACTION_ATTR, False):
                data = getattr(attr, MENU_DATA_ATTR, None)
                assert isinstance(data, MenuData)
                action_definitions.append((data, attr))
        action_definitions.sort(key=lambda action: action[0].priority)
        return action_definitions


def _menu_set_visible(menu: QMenu, visible: bool) -> None:
    main_menu_action = menu.menuAction()
    assert main_menu_action is not None
    main_menu_action.setVisible(visible)


def _action_has_title(action: Optional[QAction | QMenu], title: str) -> bool:
    if action is None:
        return False
    if isinstance(action, QAction):
        action_title = action.text()
    else:
        assert isinstance(action, QMenu)
        action_title = action.title()
    return action_title.replace('&', '') == title


class MenuData:
    """Defines how a method is used to construct a menu item."""

    def __init__(self,
                 menu_name: str,
                 config_key: str,
                 priority: int,
                 valid_app_states: Optional[list[str]],
                 condition_check: Optional[Callable[[Any], bool]]):
        self.menu_name = menu_name
        self.config_key = config_key
        self.priority = priority
        self.valid_app_states = valid_app_states
        self.condition_check = condition_check
