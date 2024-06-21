"""Shows formatted key suggestions to the user."""
from typing import Optional


from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence, QResizeEvent
from PyQt5.QtWidgets import QLabel, QWidget

from src.util.display_size import max_font_size
from src.util.key_code_utils import get_key_display_string


class KeyHintLabel(QLabel):
    """Shows formatted key suggestions to the user."""

    def __init__(self, keys: QKeySequence, parent: Optional[QWidget] = None):
        super().__init__('', parent=parent)
        font = self.font()
        self._default_size = font.pointSize() - 1
        font.setPointSize(self._default_size)
        self.setFont(font)
        self.setTextFormat(Qt.TextFormat.RichText)
        key_str = get_key_display_string(keys)
        self._base_text = key_str
        self.setText(f'<span><strong>{key_str}</strong></span>')

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Scale font as needed to stay in the bounds."""
        font = self.font()
        max_size = max(1, min(max_font_size(self._base_text, font, self.size()), self._default_size))
        if max_size != font.pointSize():
            font.setPointSize(max_size)
            self.setFont(font)
