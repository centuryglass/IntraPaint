"""Shows formatted key suggestions to the user."""
from typing import Optional


from PySide6.QtCore import Qt, QRect, QPoint, QSize
from PySide6.QtGui import QKeySequence, QResizeEvent, QPainter, QPainterPath, QPaintEvent
from PySide6.QtWidgets import QLabel, QWidget

from src.config.key_config import KeyConfig
from src.util.visual.text_drawing_utils import find_text_size, max_font_size, get_key_display_string
from src.util.key_code_utils import get_key_with_modifiers, get_modifier_string
from src.util.math_utils import clamp


class KeyHintLabel(QLabel):
    """Shows formatted key suggestions to the user."""

    def __init__(self, keys: Optional[QKeySequence | Qt.KeyboardModifier | str] = None,
                 config_key: Optional[str] = None,
                 parent: Optional[QWidget] = None):
        super().__init__('', parent=parent)
        font = self.font()
        self._default_size = font.pointSize() - 1
        self._base_text = ''
        font.setPointSize(self._default_size)
        self.setFont(font)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setContentsMargins(3, 3, 3, 3)

        if keys is None and config_key is not None:
            keys = KeyConfig().get(config_key)
        self._update_text(keys)
        if config_key is not None:
            KeyConfig().connect(self, config_key, self._key_update_slot)

    def sizeHint(self) -> QSize:
        """Calculate size hint with adjusted margins"""
        return find_text_size(self._base_text, self.font(), exact=True) + QSize(6, 6)

    def paintEvent(self, event: Optional[QPaintEvent]):
        """Outline the key text."""
        own_bounds = QRect(QPoint(), self.size())
        text_bounds = QRect(QPoint(), find_text_size(self._base_text, self.font())).adjusted(0, 0, 5, 5)
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
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        path = QPainterPath()
        path.addRoundedRect(text_bounds.adjusted(0, 0, -1, -1), 3, 3)
        painter.drawPath(path)
        painter.end()
        super().paintEvent(event)

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Scale font as needed to stay in the bounds."""
        font = self.font()
        max_size = int(clamp(max_font_size(self._base_text, font, self.size()), 1, self._default_size))
        if max_size != font.pointSize():
            font.setPointSize(max_size)
            self.setFont(font)

    @staticmethod
    def _validate_and_format_keys(key_str: str) -> str:
        """Supports comma-separated key strings, where each key string is a plus-separated list where all items are
           distinct modifiers, except the last item which may also be a key code."""
        all_keys = key_str.split(',')
        formatted = []
        for key_substr in all_keys:
            try:
                key, modifiers = get_key_with_modifiers(key_substr)
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

    def _update_text(self, key_codes: Optional[QKeySequence | Qt.KeyboardModifier | str]) -> None:
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
        self._base_text = key_display_str
        self.setText(f'<span><strong>{key_display_str}</strong></span>')

    def _key_update_slot(self, key_string: str) -> None:
        self._update_text(key_string)

