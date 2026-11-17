"""Named dock layouts, stored in the `Cache.SAVED_LAYOUTS` dict.

Each value is a dict holding the layout text from `MainWindow.save_dock_state` under `STATE_KEY`, so fields can be added
later without migrating saved layouts. Rename and delete change a copy of the dict and set it back, since the config
classes have no inner-key deletion.
"""
from typing import Any

from src.config.cache import Cache

STATE_KEY = 'state'
DEFAULT_NAME_PREFIX = 'Layout '


def _layouts() -> dict[str, dict[str, Any]]:
    return dict(Cache().get(Cache.SAVED_LAYOUTS))


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if cleaned == '':
        raise ValueError('A layout name cannot be empty')
    return cleaned


def layout_names() -> list[str]:
    """Returns every saved layout name, sorted case-insensitively."""
    return sorted(_layouts(), key=lambda name: (name.casefold(), name))


def default_layout_name() -> str:
    """Returns the first "Layout N" name that no saved layout uses."""
    used = set(_layouts())
    number = 1
    while f'{DEFAULT_NAME_PREFIX}{number}' in used:
        number += 1
    return f'{DEFAULT_NAME_PREFIX}{number}'


def has_layout(name: str) -> bool:
    """Returns whether a layout is saved under the name, after trimming it."""
    return name.strip() in _layouts()


def save_layout(name: str, state: str) -> None:
    """Saves the layout text under the trimmed name, replacing any layout with that name.

    Raises
    ------
    ValueError
        If the name is empty after trimming.
    """
    name = _clean_name(name)
    layouts = _layouts()
    layouts[name] = {STATE_KEY: state}
    Cache().set(Cache.SAVED_LAYOUTS, layouts)


def rename_layout(old_name: str, new_name: str) -> None:
    """Re-keys a layout. The new name replaces any layout already using it.

    Raises
    ------
    ValueError
        If the new name is empty after trimming.
    KeyError
        If no layout is saved under `old_name`.
    """
    new_name = _clean_name(new_name)
    layouts = _layouts()
    layout = layouts.pop(old_name)
    layouts[new_name] = layout
    Cache().set(Cache.SAVED_LAYOUTS, layouts)


def delete_layout(name: str) -> None:
    """Removes the named layout, and does nothing if there isn't one."""
    layouts = _layouts()
    if layouts.pop(name, None) is not None:
        Cache().set(Cache.SAVED_LAYOUTS, layouts)


def get_layout_state(name: str) -> str:
    """Returns the layout text saved under the name.

    Raises
    ------
    KeyError
        If no layout is saved under the name.
    """
    return str(_layouts()[name][STATE_KEY])
