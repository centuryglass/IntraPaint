"""Adds a configurable key binding to a widget's tooltip, and keeps it current when the binding changes.

Rich tooltips show a title, a dim description line, and the binding as one keycap per key, drawn by
`rich_text_key_hints`. Plain tooltips append the binding in parentheses, formatted by `get_key_display_string`.
"""
from typing import Callable, List, Optional

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from src.config.key_config import KeyConfig
from src.util.visual.text_drawing_utils import get_key_display_string, rich_text_key_hints

# Share of the tooltip text color in the description's color, with the rest from the tooltip background:
DIM_TEXT_WEIGHT = 0.65


def shortcut_tooltip_text(text: str, keys: str) -> str:
    """Returns tooltip text followed by a key binding in parentheses, or the text alone if no key is bound."""
    if keys == '':
        return text
    return f'{text} ({get_key_display_string(keys, rich_text=False)})'


def rich_shortcut_tooltip_text(title: str, keys: str, description: str = '',
                               extra_hints: Optional[List[str]] = None) -> str:
    """Returns rich tooltip text with `title`, then an optional dim `description`, then the keycaps for `keys`.
       `extra_hints` are keycap strings from `rich_text_key_hints`, shown after `keys` and joined by slashes.
       Returns `title` unchanged if there is nothing else to show."""
    extra_hints = [] if extra_hints is None else extra_hints
    if description == '' and keys == '' and len(extra_hints) == 0:
        return title
    palette = QApplication.palette()
    text_color = palette.color(QPalette.ColorRole.ToolTipText)
    base_color = palette.color(QPalette.ColorRole.ToolTipBase)
    dim = QColor.fromRgbF(*(text_color.getRgbF()[i] * DIM_TEXT_WEIGHT + base_color.getRgbF()[i] * (1 - DIM_TEXT_WEIGHT)
                            for i in range(3))).name()
    escaped_title = title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    lines = [f'<b>{escaped_title}</b>']
    if description != '':
        escaped_description = description.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        lines.append(f'<span style="color: {dim};">{escaped_description}</span>')
    if keys != '':
        lines.append(rich_text_key_hints(keys))
    if len(extra_hints) > 0:
        lines.append('&nbsp;/&nbsp;'.join(extra_hints))
    return '<br/>'.join(lines)


class _PaletteWatcher(QObject):
    """Calls a function when the application palette changes, so inline keycap images take the new theme."""

    def __init__(self, widget: QWidget, refresh: Callable[[], None]) -> None:
        super().__init__(widget)
        self._refresh = refresh
        widget.installEventFilter(self)

    def eventFilter(self, _watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Refreshes on application palette changes, and never consumes events."""
        if event.type() == QEvent.Type.ApplicationPaletteChange:
            self._refresh()
        return False


def set_shortcut_tooltip(widget: QWidget, text: str, config_key: Optional[str], description: str = '',
                         rich_text: bool = True) -> None:
    """Sets a widget's tooltip to `text` plus the key binding stored at `config_key`, updating it if the binding
       or the application palette changes.

    Parameters
    ----------
    widget: QWidget
        The widget to set the tooltip on.
    text: str
        The tooltip title.
    config_key: Optional[str]
        The `KeyConfig` key holding the binding to show, or None to show none.
    description: str, default=''
        A sentence describing the widget, shown under the title. Ignored if `rich_text` is false.
    rich_text: bool, default=True
        Whether to draw the binding as keycaps instead of a parenthesized suffix.
    """
    key_config = KeyConfig()

    def _keys() -> str:
        return '' if config_key is None else key_config.get(config_key)

    def _refresh() -> None:
        if rich_text:
            widget.setToolTip(rich_shortcut_tooltip_text(text, _keys(), description))
        else:
            widget.setToolTip(shortcut_tooltip_text(text, _keys()))

    _refresh()
    if rich_text:
        _PaletteWatcher(widget, _refresh)
    if config_key is None:
        return
    key_config.connect(widget, config_key, lambda _keys_value: _refresh())
    widget.destroyed.connect(lambda: KeyConfig().disconnect(widget, config_key))


def set_step_shortcut_tooltip(widget: QWidget, text: str, decrease_config_key: Optional[str],
                              increase_config_key: Optional[str], description: str = '') -> None:
    """Sets a stepped input's tooltip to `text` plus keycaps for the keys that step its value down and up, updating it
       if either binding or the application palette changes. A missing or empty binding is left out."""
    key_config = KeyConfig()
    config_keys = (decrease_config_key, increase_config_key)

    def _refresh(_keys: Optional[str] = None) -> None:
        bound = [key_config.get(key) for key in config_keys if key is not None and key_config.get(key) != '']
        hints = [rich_text_key_hints(keys) for keys in bound]
        widget.setToolTip(rich_shortcut_tooltip_text(text, '', description, hints))

    _refresh()
    _PaletteWatcher(widget, _refresh)
    for key in config_keys:
        if key is not None:
            key_config.connect(widget, key, _refresh)
    widget.destroyed.connect(lambda: [KeyConfig().disconnect(widget, key) for key in config_keys if key is not None])
