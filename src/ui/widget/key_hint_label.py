"""Shows formatted key suggestions to the user."""
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QLabel, QWidget

from src.util.key_code_utils import get_key_display_string


class KeyHintLabel(QLabel):
    """Shows formatted key suggestions to the user."""

    def __init__(self, keys: QKeySequence, parent: Optional[QWidget] = None):
        super().__init__('', parent=parent)
        self.setTextFormat(Qt.TextFormat.RichText)
        key_str = get_key_display_string(keys)
        self.setText(f'<span><strong><sup>{key_str}</sup></strong></span>')
