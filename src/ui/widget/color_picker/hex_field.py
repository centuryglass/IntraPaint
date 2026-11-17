"""An editable hex color field.

The field accepts `#RGB`, `#RRGGBB` and `#AARRGGBB`, with or without the `#`. It shows `#rrggbb` for opaque colors and
`#aarrggbb` otherwise. A valid entry emits `color_entered`, and an invalid one restores the shown color.
"""
import re
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLineEdit, QWidget

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.color_picker.hex_field'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


HEX_TOOLTIP = _tr('Hex color: #RGB, #RRGGBB, or #AARRGGBB with alpha first')

HEX_PATTERN = re.compile(r'^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$')
HEX_FIELD_CHARS = 10


def parse_hex_color(text: str) -> Optional[QColor]:
    """Returns the color for `#RGB`, `#RRGGBB` or `#AARRGGBB` text (the `#` optional), or None for anything else."""
    match = HEX_PATTERN.match(text.strip())
    if match is None:
        return None
    return QColor(f'#{match.group(1)}')


def format_hex_color(color: QColor) -> str:
    """Returns `#rrggbb` for an opaque color and `#aarrggbb` otherwise."""
    if color.alpha() == 255:
        return color.name(QColor.NameFormat.HexRgb)
    return color.name(QColor.NameFormat.HexArgb)


class HexField(QLineEdit):
    """An editable hex color field. `set_color` shows a color without emitting `color_entered`."""

    color_entered = Signal(QColor)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._color = QColor(Qt.GlobalColor.black)
        self.setToolTip(HEX_TOOLTIP)
        self.setMaxLength(9)
        self.setFixedWidth(self.fontMetrics().horizontalAdvance('#') * HEX_FIELD_CHARS)
        self.editingFinished.connect(self._edited)
        self.setText(format_hex_color(self._color))

    def color(self) -> QColor:
        """Returns the shown color."""
        return QColor(self._color)

    def set_color(self, color: QColor) -> None:
        """Shows a color without emitting signals."""
        self._color = QColor(color)
        self.setText(format_hex_color(self._color))

    def _edited(self) -> None:
        color = parse_hex_color(self.text())
        if color is None or color == self._color:
            self.setText(format_hex_color(self._color))
            return
        self.set_color(color)
        self.color_entered.emit(self.color())
