"""The OKHSV ring + square picker with an alpha slider and hex field below it.

`color_changed` fires while browsing (dragging); `color_committed` fires on a finished choice: mouse release, a slider
release or a valid hex entry.
"""
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout

from src.ui.widget.color_picker.alpha_hex_row import AlphaHexRow
from src.ui.widget.color_picker.okhsv_ring_square import OkhsvRingSquare


class WheelPicker(QWidget):
    """The OKHSV ring + square picker with an alpha slider and hex field below it."""

    color_changed = Signal(QColor)
    color_committed = Signal(QColor)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._color = QColor(Qt.GlobalColor.black)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        self._ring_square = OkhsvRingSquare(self)
        layout.addWidget(self._ring_square, stretch=1)
        self._alpha_hex_row = AlphaHexRow(self)
        layout.addWidget(self._alpha_hex_row)

        self._ring_square.color_changed.connect(self._ring_square_changed)
        self._alpha_hex_row.color_changed.connect(self._alpha_hex_changed)
        self._ring_square.color_committed.connect(self.color_committed)
        self._alpha_hex_row.color_committed.connect(self.color_committed)
        self.set_color(QColor(Qt.GlobalColor.black))

    @property
    def ring_square(self) -> OkhsvRingSquare:
        """The hue ring and saturation/value square."""
        return self._ring_square

    @property
    def alpha_hex_row(self) -> AlphaHexRow:
        """The alpha slider and hex field."""
        return self._alpha_hex_row

    def selected_color(self) -> QColor:
        """Returns the selected color."""
        return QColor(self._color)

    def set_color(self, color: QColor) -> None:
        """Sets the selected color without emitting signals."""
        self._color = color.toRgb()
        self._ring_square.set_color(color)
        self._alpha_hex_row.set_color(color)

    def _ring_square_changed(self, color: QColor) -> None:
        self._color = color.toRgb()
        self._alpha_hex_row.set_color(color)
        self.color_changed.emit(color)

    def _alpha_hex_changed(self, color: QColor) -> None:
        self._color = color.toRgb()
        self._ring_square.set_color(color)
        self.color_changed.emit(color)
