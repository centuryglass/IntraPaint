"""The OKHSV ring + square picker with an alpha slider and hex field below it."""
from typing import Optional

from PySide6.QtWidgets import QWidget

from src.ui.widget.color_picker.alpha_hex_panel import AlphaHexPanel
from src.ui.widget.color_picker.okhsv_ring_square import OkhsvRingSquare


class WheelPicker(AlphaHexPanel):
    """The OKHSV ring + square picker with an alpha slider and hex field below it."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        self._ring_square = OkhsvRingSquare()
        super().__init__(self._ring_square, parent)

    @property
    def ring_square(self) -> OkhsvRingSquare:
        """The hue ring and saturation/value square."""
        return self._ring_square
