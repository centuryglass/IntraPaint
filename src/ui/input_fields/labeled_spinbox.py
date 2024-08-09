"""
Minimal wrapper class for creating a labeled spinbox widget.
"""
from typing import Optional
from PySide6.QtWidgets import QWidget, QDoubleSpinBox, QLabel, QHBoxLayout
from src.ui.input_fields.big_int_spinbox import BigIntSpinbox


class LabeledSpinbox(QWidget):
    """LabeledSpinbox is a labeled numeric spinbox widget that automatically initializes with the correct data type.
    """

    def __init__(self,
                 parent: Optional[QWidget],
                 label_text: str,
                 tooltip: str,
                 min_value: int | float,
                 default_value: int | float,
                 max_value: int | float) -> None:
        """Initializes the spinbox, sets label text, and establishes type, initial value, and accepted range.

        Parameters
        ----------
        parent : QWidget or None
            Optional parent widget.
        label_text : str
            Label text to be shown to the left of the widget.
        tooltip : str
            Tooltip to show when the mouse hovers over the widget.
        min_value : int or float
            Minimum value allowed within the spinbox.
        default_value : int or float
            Initial spinbox value.
        max_value : int or float
            Maximum value allowed within the spinbox.
        """
        super().__init__(parent)
        self.setToolTip(tooltip)
        self._layout = QHBoxLayout()
        self._label = QLabel(self)
        self._label.setText(label_text)
        self.spinbox = QDoubleSpinBox(self) if isinstance(default_value, float) else BigIntSpinbox(self)
        self.spinbox.setRange(min_value, max_value)
        self.spinbox.setValue(default_value)
        self._layout.addWidget(self._label, 1)
        self._layout.addWidget(self.spinbox, 2)
        self.setLayout(self._layout)
