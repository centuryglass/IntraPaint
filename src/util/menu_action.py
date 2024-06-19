"""Defines the @menu_action decorator and the MenuBuilder class for more convenient PyQt5 menu initialization."""
import functools
from typing import Callable, Any, Optional, TypeVar, Dict

from PyQt5.QtWidgets import QMainWindow, QAction, QMenu

from src.config.key_config import KeyConfig
from src.util.shared_constants import INT_MAX

GenericFn = TypeVar('GenericFn', bound=Callable[..., Any])


def menu_action(menu_name: str, config_key: str, priority: int = INT_MAX,
                ignore_when_busy=False,
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
    ignore_when_busy: bool
        If true, the method will be disabled when the application is busy.
    condition_check: Optional function returning bool
        If not none, this function will be evaluated when the menu is initialized, and the menu option will not
        be added unless it returns true. The parameter passed in will be object initializing the menus.
    """

    def _decorator(func):
        @functools.wraps(func)
        def _wrapper(self, **kwargs):
            if not ignore_when_busy or not self.is_busy():
                return func(self, **kwargs)
            return None

        _wrapper.menu_name = menu_name
        _wrapper.config_key = config_key
        _wrapper.ignore_when_busy = ignore_when_busy
        _wrapper.is_menu_action = True
        _wrapper.priority = priority
        _wrapper.condition_check = condition_check
        return _wrapper
    return _decorator


class MenuBuilder:
    """Provides the build_menus method to initialize menus from annotated methods."""

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
        menus: Dict[str, QMenu] = {}
        for menu_action_method in menu_actions:
            if menu_action_method.condition_check is not None and menu_action_method.condition_check(self) is False:
                continue
            menu_name = menu_action_method.menu_name
            if menu_name in menus:
                menu = menus[menu_name]
            else:
                menu = menu_bar.addMenu(menu_name)
                menus[menu_name] = menu
            config = KeyConfig.instance()
            try:
                title = config.get_label(menu_action_method.config_key)
                tooltip = config.get_tooltip(menu_action_method.config_key)
                shortcut = config.get(menu_action_method.config_key)
            except RuntimeError:
                print(f'Warning: could not load menu option {menu_action_method.config_key}, skipping...')
                continue
            action = QAction(title, window)
            if len(tooltip) > 0:
                action.setToolTip(tooltip)
            if len(shortcut) > 0:
                action.setShortcut(shortcut)
            action.triggered.connect(menu_action_method)
            config.connect(self, menu_action_method.config_key, lambda key_str: action.setShortcut(key_str))
            menu.addAction(action)
