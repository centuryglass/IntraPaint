"""Formats key bindings for display, with one keycap label per alternative binding.

Every key hint gets its labels from `key_hint_labels`: keycap widgets, inline tooltip keycaps and plain-text hints
alike. A binding's keys share one label joined by "+", such as "Shift+S", and each alternative binding of a config
value such as "Shift+S,K" gets its own label. Keycap rows and text put `KEYCAP_SEPARATOR` between alternatives.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence

from src.util.key_code_utils import KEY_REQUIRES_SHIFT, get_modifier_string, key_alternatives
from src.util.visual.keycap import KEYCAP_SEPARATOR, keycap_row_size
from src.util.visual.text_drawing_utils import get_key_display_string, rich_text_key_hint

# Modifier names as config values may spell them, mapped to the name key hints show:
_MODIFIER_NAMES = {'ctrl': 'Ctrl', 'control': 'Ctrl', 'shift': 'Shift', 'alt': 'Alt', 'meta': 'Meta', 'super': 'Meta'}

# Modifier display names and the symbols that replace them in compact labels:
MODIFIER_SYMBOLS = {'Shift': '⇧', 'Ctrl': '⌃', 'Alt': '⎇', '⌘': '⌘'}

KeyHintSource = str | QKeySequence | Qt.Key | Qt.KeyboardModifier


def binding_keys(binding: str) -> list[str]:
    """Splits one binding such as "Ctrl+Shift+Z" into its key names, keeping a trailing "+" key whole."""
    if binding == '+':
        return ['+']
    if binding.endswith('++'):
        return [key for key in binding[:-2].split('+') if key != ''] + ['+']
    return [key for key in binding.split('+') if key != '']


def _binding_label(binding: str, compact: bool) -> str:
    keys = [_MODIFIER_NAMES.get(key.lower(), key.upper() if len(key) == 1 else key) for key in binding_keys(binding)]
    if len(keys) > 1 and keys[-1] in KEY_REQUIRES_SHIFT:
        keys = [key for key in keys[:-1] if key != 'Shift'] + keys[-1:]
    keys = [get_key_display_string(key, rich_text=False) for key in keys]
    if not compact:
        return '+'.join(keys)
    symbols = ''.join(MODIFIER_SYMBOLS[key] for key in keys if key in MODIFIER_SYMBOLS)
    return symbols + '+'.join(key for key in keys if key not in MODIFIER_SYMBOLS)


def key_hint_labels(keys: Optional[KeyHintSource], compact: bool = False) -> list[str]:
    """Returns one keycap label per alternative binding in `keys`, or an empty list if nothing is bound.

    Parameters
    ----------
    keys: str, QKeySequence, Qt.Key, Qt.KeyboardModifier, or None
        A config value such as "Shift+S,K", where commas separate alternative bindings, or a single key or modifier.
    compact: bool, default=False
        Whether modifiers show as symbols with no "+" after them, so "Shift+S" becomes "⇧S".
    """
    if keys is None:
        return []
    if isinstance(keys, Qt.KeyboardModifier):
        keys = get_modifier_string(keys)
    elif isinstance(keys, Qt.Key):
        keys = QKeySequence(keys).toString()
    elif isinstance(keys, QKeySequence):
        keys = keys.toString()
    return [_binding_label(binding, compact) for binding in key_alternatives(keys)]


def key_hint_text(keys: Optional[KeyHintSource], compact: bool = False) -> str:
    """Returns the plain-text form of `key_hint_labels`, joined by `KEYCAP_SEPARATOR`, such as "Shift+S, K"."""
    return KEYCAP_SEPARATOR.join(key_hint_labels(keys, compact))


def shortest_key_label(labels: list[str]) -> list[str]:
    """Returns a list holding the shortest of `labels`, or the first of those tied for shortest, or an empty list if
    there are none."""
    return [min(labels, key=len)] if len(labels) > 0 else []


def fitted_key_hint_labels(keys: Optional[KeyHintSource], font: QFont, max_width: int) -> list[str]:
    """Returns the first of three forms of `key_hint_labels` whose keycap row in the keycap `font` fits `max_width`:
    all labels, all labels compact, then only the shortest compact label, which is returned even if it doesn't fit.

    Places too small for a binding's full keycaps use this, so the shorter forms are the same everywhere."""
    labels = key_hint_labels(keys)
    if keycap_row_size(labels, font).width() <= max_width:
        return labels
    labels = key_hint_labels(keys, compact=True)
    if keycap_row_size(labels, font).width() <= max_width:
        return labels
    return shortest_key_label(labels)


def rich_text_key_hints(keys: Optional[KeyHintSource]) -> str:
    """Returns an inline keycap image for each of `key_hint_labels`, with `KEYCAP_SEPARATOR` between them, or the empty
    string if nothing is bound."""
    return KEYCAP_SEPARATOR.replace(' ', '&nbsp;').join(rich_text_key_hint(label) for label in key_hint_labels(keys))
