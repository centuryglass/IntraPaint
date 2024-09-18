"""Utilities for managing Qt keycodes and strings, and displaying input hints."""
from typing import Tuple, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

from src.util.visual.text_drawing_utils import get_key_display_string


KEY_REQUIRES_SHIFT = '~!@#$%^&*()_+{}|:<>?"'


def get_key_code(key_string: str) -> Qt.Key:
    """Get a key code for a given key string, or throw ValueError if the key string was invalid."""
    key = QKeySequence(key_string)
    # noinspection PyUnresolvedReferences
    if key.count() != 1 or key[0] == Qt.Key.Key_unknown:
        raise ValueError(f'Expected a single key string, got "{str}" (key count={key.count()})')
    # noinspection PyUnresolvedReferences
    return key[0].key()


def get_key_string(key: Qt.Key) -> str:
    """Gets the string representation of a given key."""
    return QKeySequence(key).toString()


def get_key_with_modifiers(key_string: str) -> Tuple[Optional[Qt.Key], Qt.KeyboardModifier]:
    """Converts a key string to a key code and a set of key modifiers."""
    assert ',' not in key_string, f'Expected single key with possible modifiers, got key list {key_string}'
    modifiers = Qt.KeyboardModifier.NoModifier
    keys = key_string.split('+')
    if len(keys) > 1:
        modifiers = get_modifiers(keys[:-1])
    try:
        key = get_key_code(keys[-1])
    except ValueError:
        modifiers = get_modifiers(keys)
        key = None
    if keys[-1] in KEY_REQUIRES_SHIFT:
        modifiers = modifiers | Qt.KeyboardModifier.ShiftModifier
    return key, modifiers


def get_modifiers(modifier_str: str | List[str]) -> Qt.KeyboardModifier:
    """Return the modifiers represented by a string."""
    modifiers = Qt.KeyboardModifier.NoModifier
    if not isinstance(modifier_str, list):
        modifier_str = modifier_str.split('+')
    for mod_str in modifier_str:
        match mod_str.lower():
            case 'control' | 'ctrl':
                modifiers = modifiers | Qt.KeyboardModifier.ControlModifier
            case 'shift':
                modifiers = modifiers | Qt.KeyboardModifier.ShiftModifier
            case 'alt':
                modifiers = modifiers | Qt.KeyboardModifier.AltModifier
            case _:
                raise ValueError(f'Unexpected modifier key string {mod_str}')
    return modifiers


def get_modifier_string(modifiers: Qt.KeyboardModifier) -> str:
    """Get the string representation of one or more keyboard modifiers."""
    mod_strings = []
    for code, name in ((Qt.KeyboardModifier.AltModifier, 'Alt'),
                       (Qt.KeyboardModifier.ShiftModifier, 'Shift'),
                       (Qt.KeyboardModifier.ControlModifier, 'Ctrl'),
                       (Qt.KeyboardModifier.MetaModifier, 'Meta')):
        if (code & modifiers) == code:
            mod_strings.append(get_key_display_string(name, rich_text=False))
    return '+'.join(mod_strings)
