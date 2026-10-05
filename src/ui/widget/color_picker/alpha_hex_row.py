"""An alpha slider and a hex color field.

The hex field accepts `#RGB`, `#RRGGBB` and `#AARRGGBB`, with or without the `#`. It shows `#rrggbb` for opaque colors
and `#aarrggbb` otherwise. Dragging the slider emits `color_changed`; releasing it, any other slider change, and a
valid hex entry also emit `color_committed`.
"""
import re
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QHBoxLayout, QSlider, QLineEdit, QLabel, QApplication

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.color_picker.alpha_hex_row'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


ALPHA_LABEL = _tr('Alpha:')
ALPHA_TOOLTIP = _tr('Opacity, from 0 (transparent) to 255 (opaque)')
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


class AlphaHexRow(QWidget):
    """An alpha slider and a hex color field."""

    color_changed = Signal(QColor)
    color_committed = Signal(QColor)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._color = QColor(Qt.GlobalColor.black)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._alpha_label = QLabel(ALPHA_LABEL)
        layout.addWidget(self._alpha_label)
        self._alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self._alpha_slider.setRange(0, 255)
        self._alpha_slider.setValue(255)
        self._alpha_slider.setToolTip(ALPHA_TOOLTIP)
        self._alpha_label.setBuddy(self._alpha_slider)
        self._alpha_slider.valueChanged.connect(self._alpha_slider_changed)
        self._alpha_slider.sliderReleased.connect(lambda: self.color_committed.emit(self.color()))
        layout.addWidget(self._alpha_slider, stretch=1)

        self._hex_field = QLineEdit()
        self._hex_field.setToolTip(HEX_TOOLTIP)
        self._hex_field.setMaxLength(9)
        self._hex_field.setFixedWidth(self._hex_field.fontMetrics().horizontalAdvance('#') * HEX_FIELD_CHARS)
        self._hex_field.editingFinished.connect(self._hex_field_edited)
        layout.addWidget(self._hex_field)
        self._update_hex_field()

    @property
    def alpha_slider(self) -> QSlider:
        """The alpha slider."""
        return self._alpha_slider

    @property
    def hex_field(self) -> QLineEdit:
        """The hex color field."""
        return self._hex_field

    def color(self) -> QColor:
        """Returns the displayed color."""
        return QColor(self._color)

    def set_color(self, color: QColor) -> None:
        """Displays a color without emitting signals."""
        self._color = QColor(color)
        self._alpha_slider.blockSignals(True)
        self._alpha_slider.setValue(color.alpha())
        self._alpha_slider.blockSignals(False)
        self._update_hex_field()

    def _update_hex_field(self) -> None:
        self._hex_field.setText(format_hex_color(self._color))

    def _alpha_slider_changed(self, alpha: int) -> None:
        if alpha == self._color.alpha():
            return
        self._color.setAlpha(alpha)
        self._update_hex_field()
        self.color_changed.emit(self.color())
        if not self._alpha_slider.isSliderDown():
            self.color_committed.emit(self.color())

    def _hex_field_edited(self) -> None:
        color = parse_hex_color(self._hex_field.text())
        if color is None or color == self._color:
            self._update_hex_field()
            return
        self.set_color(color)
        self.color_changed.emit(self.color())
        self.color_committed.emit(self.color())
