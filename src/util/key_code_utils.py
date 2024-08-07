"""Utilities for managing Qt keycodes and strings."""
from typing import Tuple, List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence

_MODIFIERS = {
    Qt.Key.Key_Control: Qt.KeyboardModifier.ControlModifier,
    Qt.Key.Key_Shift: Qt.KeyboardModifier.ShiftModifier,
    Qt.Key.Key_Alt: Qt.KeyboardModifier.AltModifier
}


def get_key_code(key_string: str) -> Qt.Key:
    """Get a key code for a given key string, or throw ValueError if the key string was invalid."""
    key = QKeySequence(key_string)
    if key.count() != 1 or key[0] == Qt.Key.Key_unknown:
        raise ValueError(f'Expected a single key string, got "{str}" (key count={key.count()})')
    return key[0]


def get_key_string(key: Qt.Key) -> str:
    """Gets the string representation of a given key."""
    return QKeySequence(key).toString()


def get_key_with_modifiers(key_string: str) -> Tuple[Qt.Key, Qt.KeyboardModifier]:
    """Converts a key string to a key code and a set of key modifiers."""
    assert ',' not in key_string, f'Expected single key with possible modifiers, got key list {key_string}'
    modifiers = Qt.KeyboardModifier.NoModifier
    keys = key_string.split('+')
    if len(keys) > 1:
        modifiers = get_modifiers(keys[:-1])
    key = get_key_code(keys[-1])
    return key, modifiers


def get_modifiers(modifier_str: str | List[str]) -> Qt.KeyboardModifier:
    """Return the modifiers represented by a string."""
    modifiers = Qt.KeyboardModifier.NoModifier
    if not isinstance(modifier_str, list):
        modifier_str = modifier_str.split('+')
    for mod_str in modifier_str:
        match mod_str:
            case 'Control' | 'Ctrl':
                modifiers = modifiers | Qt.KeyboardModifier.ControlModifier
            case 'Shift':
                modifiers = modifiers | Qt.KeyboardModifier.ShiftModifier
            case 'Alt':
                modifiers = modifiers | Qt.KeyboardModifier.AltModifier
            case _:
                raise RuntimeError(f'Unexpected modifier key string {mod_str}')
    return modifiers


def get_modifier_string(modifiers: Qt.KeyboardModifier) -> str:
    """Get the string representation of one or more keyboard modifiers."""
    mod_strings = []
    for code, name in ((Qt.KeyboardModifier.AltModifier, 'Alt'),
                       (Qt.KeyboardModifier.ShiftModifier, 'Shift'),
                       (Qt.KeyboardModifier.ControlModifier, 'Ctrl'),
                       (Qt.KeyboardModifier.MetaModifier, 'Meta')):
        if (code & modifiers) == code:
            mod_strings.append(name)
    return '+'.join(mod_strings)


def get_key_display_string(keys: QKeySequence) -> str:
    """Creates a display string representing a set of keys, replacing common symbols with appropriate characters."""
    text = keys.toString()
    symbol_map = {
        'Ctrl+': '⌃',
        'Alt+': '⎇',
        'Meta+': '⌘',
        'Shift+': '⇧',
        'Enter': '⏎',
        'Del': '⌫',
        'Home': '⇱',
        'End': '⇲',
        'PgUp': '⇞',
        'PgDown': '⇟',
        'Up': '↑',
        'Down': '↓',
        'Left': '←',
        'Right': '→'
    }
    for key, symbol in symbol_map.items():
        text = text.replace(key, symbol)
    return text
