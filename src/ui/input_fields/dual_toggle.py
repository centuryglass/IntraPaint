"""
A fancier Qt toggle button implementation that allows selecting between two options.
"""
from typing import Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt
from src.ui.input_fields.option_toggle import OptionToggle


class DualToggle(OptionToggle):
    """A fancier Qt toggle button implementation that allows selecting between two options."""

    def __init__(self,
                 parent: Optional[QWidget],
                 options: list[str],
                 orientation: Qt.Orientation = Qt.Orientation.Horizontal,
                 display_names: Optional[list[str]] = None):
        """__init__.

        Parameters
        ----------
        parent : QWidget or None
            Optional parent widget.
        options : list of str
            Option names. Must be length 2, other lengths will raise ValueError.
        orientation : Qt.Orientation
            Horizontal or vertical orientation.
        display_names : list of str, optional
            Text to show on each button instead of the option string. The value is still the option string.
        """
        if len(options) != 2:
            raise ValueError(f"DualToggle expects two options, got {options}")
        super().__init__(parent, options, 2 if orientation == Qt.Orientation.Horizontal else 1, orientation,
                         display_names)

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Choose between side-by-side buttons with horizontal text, and stacked buttons with vertical text."""
        self._label_orientation(orientation)
        self._set_columns(2 if orientation == Qt.Orientation.Horizontal else 1)

    def toggle(self) -> None:
        """Selects whatever option isn't currently selected."""
        if self._selected is None:
            return
        self.setValue(self._options[1] if self._selected == self._options[0] else self._options[0])
