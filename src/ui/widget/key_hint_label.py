"""Shows formatted key suggestions to the user."""
from typing import Optional


from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QResizeEvent
from PySide6.QtWidgets import QLabel, QWidget

from src.config.key_config import KeyConfig
from src.util.display_size import max_font_size
from src.util.key_code_utils import get_key_display_string


class KeyHintLabel(QLabel):
    """Shows formatted key suggestions to the user."""

    def __init__(self, keys: Optional[QKeySequence] = None, config_key: Optional[str] = None,
                 parent: Optional[QWidget] = None):
        super().__init__('', parent=parent)
        font = self.font()
        self._default_size = font.pointSize() - 1
        self._base_text = ''
        font.setPointSize(self._default_size)
        self.setFont(font)
        self.setTextFormat(Qt.TextFormat.RichText)

        if keys is None and config_key is not None:
            try:
                keys = KeyConfig().get_keycodes(config_key)
            except RuntimeError:
                keys = None
        self._update_text(keys)
        if config_key is not None:
            KeyConfig().connect(self, config_key, self._key_update_slot)

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Scale font as needed to stay in the bounds."""
        font = self.font()
        max_size = max(1, min(max_font_size(self._base_text, font, self.size()), self._default_size))
        if max_size != font.pointSize():
            font.setPointSize(max_size)
            self.setFont(font)

    def _update_text(self, key_codes: Optional[QKeySequence]) -> None:
        if key_codes is None:
            self._base_text = ''
            self.setText(self._base_text)
            return
        key_display_str = get_key_display_string(key_codes)
        self._base_text = key_display_str
        self.setText(f'<span><strong>{key_display_str}</strong></span>')

    def _key_update_slot(self, key_string: str) -> None:
        self._update_text(QKeySequence(key_string))
