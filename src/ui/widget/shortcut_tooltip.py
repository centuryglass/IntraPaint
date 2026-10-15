"""Adds a configurable key binding to a widget's tooltip, and keeps it current when the binding changes.

Key text goes through `get_key_display_string`, the same formatting `KeyHintLabel` and the tool input hints use.
"""
from typing import Optional

from PySide6.QtWidgets import QWidget

from src.config.key_config import KeyConfig
from src.util.visual.text_drawing_utils import get_key_display_string


def shortcut_tooltip_text(text: str, keys: str) -> str:
    """Returns tooltip text followed by a key binding in parentheses, or the text alone if no key is bound."""
    if keys == '':
        return text
    return f'{text} ({get_key_display_string(keys, rich_text=False)})'


def set_shortcut_tooltip(widget: QWidget, text: str, config_key: Optional[str]) -> None:
    """Sets a widget's tooltip to `text` plus the key binding stored at `config_key`, updating it if the binding
       changes. A `config_key` of None leaves `text` as the whole tooltip."""
    if config_key is None:
        widget.setToolTip(text)
        return
    key_config = KeyConfig()
    widget.setToolTip(shortcut_tooltip_text(text, key_config.get(config_key)))

    def _update_tooltip(keys: str) -> None:
        widget.setToolTip(shortcut_tooltip_text(text, keys))

    key_config.connect(widget, config_key, _update_tooltip)
    widget.destroyed.connect(lambda: KeyConfig().disconnect(widget, config_key))


def set_step_shortcut_tooltip(widget: QWidget, text: str, decrease_config_key: Optional[str],
                              increase_config_key: Optional[str]) -> None:
    """Sets a stepped input's tooltip to `text` plus the keys that step its value down and up, updating it if either
       binding changes. A missing or empty binding is left out."""
    key_config = KeyConfig()
    config_keys = (decrease_config_key, increase_config_key)

    def _update_tooltip(_keys: Optional[str] = None) -> None:
        bound = [get_key_display_string(key_config.get(key), rich_text=False) for key in config_keys
                 if key is not None and key_config.get(key) != '']
        widget.setToolTip(f"{text} ({' / '.join(bound)})" if len(bound) > 0 else text)

    _update_tooltip()
    for key in config_keys:
        if key is not None:
            key_config.connect(widget, key, _update_tooltip)
    widget.destroyed.connect(lambda: [KeyConfig().disconnect(widget, key) for key in config_keys if key is not None])
