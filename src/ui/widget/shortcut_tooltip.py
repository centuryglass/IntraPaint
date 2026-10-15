"""Adds a configurable key binding to a widget's tooltip, and keeps it current when the binding changes.

Rich tooltips show a title, a dim description line, any input hints, and the binding as one keycap per key, drawn by
`rich_text_key_hint`. Plain tooltips append the binding in parentheses, formatted by `get_key_display_string`.
"""
from typing import Callable, Optional

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


def rich_shortcut_tooltip_text(title: str, keys: str, description: str = '', input_hint: str = '') -> str:
    """Returns rich tooltip text with `title`, then an optional dim `description` and `input_hint`, then the keycaps
       for `keys`. Returns `title` unchanged if there is nothing else to show."""
    if description == '' and input_hint == '' and keys == '':
        return title
    palette = QApplication.palette()
    text_color = palette.color(QPalette.ColorRole.ToolTipText)
    base_color = palette.color(QPalette.ColorRole.ToolTipBase)
    dim = QColor.fromRgbF(*(text_color.getRgbF()[i] * DIM_TEXT_WEIGHT + base_color.getRgbF()[i] * (1 - DIM_TEXT_WEIGHT)
                            for i in range(3))).name()
    escaped_title = title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    lines = [f'<b>{escaped_title}</b>']
    for line in (description.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), input_hint):
        if line != '':
            lines.append(f'<span style="color: {dim};">{line}</span>')
    if keys != '':
        lines.append(rich_text_key_hints(keys))
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
                         input_hint: Optional[Callable[[], str]] = None, rich_text: bool = True) -> None:
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
    input_hint: Optional[Callable[[], str]], default=None
        Returns rich text describing mouse and modifier input, shown under the description. Ignored if `rich_text`
        is false.
    rich_text: bool, default=True
        Whether to draw the binding as keycaps instead of a parenthesized suffix.
    """
    key_config = KeyConfig()

    def _keys() -> str:
        return '' if config_key is None else key_config.get(config_key)

    def _refresh() -> None:
        if rich_text:
            hint = '' if input_hint is None else input_hint()
            widget.setToolTip(rich_shortcut_tooltip_text(text, _keys(), description, hint))
        else:
            widget.setToolTip(shortcut_tooltip_text(text, _keys()))

    _refresh()
    if rich_text:
        _PaletteWatcher(widget, _refresh)
    if config_key is None:
        return
    key_config.connect(widget, config_key, lambda _keys_value: _refresh())
    widget.destroyed.connect(lambda: KeyConfig().disconnect(widget, config_key))
