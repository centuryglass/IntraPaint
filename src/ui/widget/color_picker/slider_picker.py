"""The RGB / HSV / OKLCH slider block with an alpha slider and hex field below it."""
from typing import Optional

from PySide6.QtWidgets import QWidget

from src.ui.widget.color_picker.alpha_hex_panel import AlphaHexPanel
from src.ui.widget.color_picker.color_slider_block import ColorSliderBlock


class SliderPicker(AlphaHexPanel):
    """The RGB / HSV / OKLCH slider block with an alpha slider and hex field below it."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        self._slider_block = ColorSliderBlock()
        super().__init__(self._slider_block, parent, control_stretch=0)

    @property
    def slider_block(self) -> ColorSliderBlock:
        """The component sliders."""
        return self._slider_block
