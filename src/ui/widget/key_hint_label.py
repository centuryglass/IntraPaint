"""Shows formatted key suggestions to the user, drawn as raised keycaps."""
from typing import Optional

from PySide6.QtCore import Qt, QRect, QRectF, QPoint, QSize
from PySide6.QtGui import QKeySequence, QPainter, QPaintEvent, QFont
from PySide6.QtWidgets import QLabel, QWidget

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.util.key_code_utils import get_key_with_modifiers, get_modifier_string, KEY_REQUIRES_SHIFT
from src.util.visual.keycap import (KEYCAP_PADDING, KEYCAP_DEPTH, draw_keycap, keycap_colors, keycap_font,
                                    keycap_size)
from src.util.visual.text_drawing_utils import find_text_size, get_key_display_string

# Modifier names and the symbols that replace them in compact key text, in the order they are tried:
MODIFIER_SYMBOLS = (('Shift', '⇧'), ('Ctrl', '⌃'), ('Alt', '⎇'), ('⌘', '⌘'))


def compact_key_text(text: str) -> str:
    """Returns formatted key text with each modifier name replaced by its symbol and no "+" after it, so "Shift+S"
    becomes "⇧S". Other key names are unchanged."""
    compact_combos = []
    for combo in text.split(', '):
        prefix = ''
        changed = True
        while changed:
            changed = False
            for name, symbol in MODIFIER_SYMBOLS:
                if combo == name:
                    prefix += symbol
                    combo = ''
                elif combo.startswith(f'{name}+'):
                    prefix += symbol
                    combo = combo[len(name) + 1:]
                    changed = True
        compact_combos.append(prefix + combo)
    return ', '.join(compact_combos)


class KeyHintLabel(QLabel):
    """Shows formatted key suggestions to the user, drawn as raised keycaps.

    The keycap is drawn by `src.util.visual.keycap`, in the colors from `keycap_colors`.
    """

    def __init__(self, keys: Optional[QKeySequence | Qt.KeyboardModifier | str] = None,
                 config_key: Optional[str] = None,
                 parent: Optional[QWidget] = None):
        super().__init__('', parent=parent)
        self._base_text = ''
        font = QFont()
        self._default_size = AppConfig().get(AppConfig.KEY_HINT_FONT_SIZE)
        font.setPointSize(self._default_size)
        self.setFont(font)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setContentsMargins(KEYCAP_PADDING.left(), KEYCAP_PADDING.top(), KEYCAP_PADDING.right(),
                                KEYCAP_PADDING.bottom() + KEYCAP_DEPTH)
        self._saved_size: Optional[QSize] = None
        self._compact = False
        self._key_codes: Optional[QKeySequence | Qt.KeyboardModifier | str] = None
        self._config_key = config_key
        if keys is None and config_key is not None:
            keys = KeyConfig().get(config_key)
        self._update_text(keys)
        if config_key is not None:
            KeyConfig().connect(self, config_key, self._key_update_slot)

        def _update_size(size: int) -> None:
            updated_font = QFont(self.font())
            updated_font.setPointSize(size)
            self.setFont(updated_font)
        AppConfig().connect(self, AppConfig.KEY_HINT_FONT_SIZE, _update_size)

    def deleteLater(self) -> None:
        """Disconnect from config before scheduling deletion."""
        AppConfig().disconnect(self, AppConfig.KEY_HINT_FONT_SIZE)
        if self._config_key is not None:
            KeyConfig().disconnect(self, self._config_key)
        super().deleteLater()

    def _key_font(self) -> QFont:
        """Returns the bold font the key text is drawn in."""
        return keycap_font(self.font())

    def sizeHint(self) -> QSize:
        """Returns the size of the key text in bold, plus the keycap's margins."""
        if self._saved_size is None:
            self._saved_size = keycap_size(find_text_size(self._base_text, self._key_font(), exact=False))
        return QSize(self._saved_size)

    def minimumSizeHint(self) -> QSize:
        """Returns the size hint, since a smaller label cuts off the keycap."""
        return self.sizeHint()

    def setText(self, text: str) -> None:
        """Update label text, clearing saved text size calculations."""
        self._saved_size = None
        super().setText(text)

    def setFont(self, font: QFont) -> None:
        """Update label font, clearing saved text size calculations."""
        self._saved_size = None
        super().setFont(font)

    def paintEvent(self, event: Optional[QPaintEvent]):
        """Draw the keycap behind the key text."""
        if self._base_text == '':
            super().paintEvent(event)
            return
        own_bounds = QRect(QPoint(), self.size())
        text_bounds = QRect(QPoint(), keycap_size(find_text_size(self._base_text, self._key_font(), exact=False)))
        alignment = self.alignment()
        if alignment & Qt.AlignmentFlag.AlignHCenter == Qt.AlignmentFlag.AlignHCenter:
            text_bounds.moveLeft((own_bounds.width() - text_bounds.width()) // 2)
        elif alignment & Qt.AlignmentFlag.AlignRight == Qt.AlignmentFlag.AlignRight:
            text_bounds.moveLeft(own_bounds.width() - text_bounds.width())
        if alignment & Qt.AlignmentFlag.AlignVCenter == Qt.AlignmentFlag.AlignVCenter:
            text_bounds.moveTop((own_bounds.height() - text_bounds.height()) // 2)
        elif alignment & Qt.AlignmentFlag.AlignBottom == Qt.AlignmentFlag.AlignBottom:
            text_bounds.moveTop(own_bounds.height() - text_bounds.height())
        text_bounds = text_bounds.intersected(own_bounds)
        fill, outline, _ = keycap_colors(self.palette())
        painter = QPainter(self)
        draw_keycap(painter, QRectF(text_bounds), fill, outline)
        painter.end()
        super().paintEvent(event)

    @staticmethod
    def _validate_and_format_keys(key_str: str) -> str:
        """Supports comma-separated key strings, where each key string is a plus-separated list where all items are
           distinct modifiers, except the last item which may also be a key code."""
        all_keys = key_str.split(',')
        formatted = []
        for key_substr in all_keys:
            try:
                key, modifiers = get_key_with_modifiers(key_substr)
                if key is not None and get_key_display_string(key, False) in KEY_REQUIRES_SHIFT:
                    modifiers = modifiers & ~Qt.KeyboardModifier.ShiftModifier
                if key is not None and key != Qt.Key.Key_unknown:
                    display_key = get_key_display_string(QKeySequence(key), False)
                    if modifiers == Qt.KeyboardModifier.NoModifier:
                        formatted.append(display_key)
                    else:
                        formatted.append(f'{get_modifier_string(modifiers)}+{display_key}')
                else:
                    formatted.append(get_modifier_string(modifiers))
            except (RuntimeError, ValueError):
                pass  # Invalid keys will be ignored
        return ', '.join(formatted)

    @property
    def compact(self) -> bool:
        """Whether modifiers show as symbols, such as "⇧S" for "Shift+S"."""
        return self._compact

    def set_compact(self, compact: bool) -> None:
        """Shows modifiers as symbols, or as names if `compact` is false."""
        if compact != self._compact:
            self._compact = compact
            self._update_text(self._key_codes)

    def _update_text(self, key_codes: Optional[QKeySequence | Qt.KeyboardModifier | str]) -> None:
        self._key_codes = key_codes
        if key_codes is None:
            self._base_text = ''
            self.setText(self._base_text)
            return
        if isinstance(key_codes, str):
            key_display_str = self._validate_and_format_keys(key_codes)
        elif isinstance(key_codes, QKeySequence):
            key_display_str = get_key_display_string(key_codes, False)
        elif isinstance(key_codes, Qt.KeyboardModifier):
            key_display_str = get_modifier_string(key_codes)
        else:
            raise TypeError(f'Unexpected key_codes value type {type(key_codes)} = {key_codes}')
        if self._compact:
            key_display_str = compact_key_text(key_display_str)
        key_substitutions = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&apos;'
        }
        self._base_text = key_display_str
        for invalid_str, replacement in key_substitutions.items():
            if invalid_str in key_display_str:
                key_display_str = key_display_str.replace(invalid_str, replacement)
        text_color = keycap_colors(self.palette())[2].name()
        self.setText(f'<span style="color: {text_color};"><strong>{key_display_str}</strong></span>')

    def _key_update_slot(self, key_string: str) -> None:
        self._update_text(key_string)
