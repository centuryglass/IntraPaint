"""A simple wrapper for QCheckBox to give it an interface consistent with other input widgets."""
from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QWidget


class CheckBox(QCheckBox):
    """A simple wrapper for QCheckBox to give it an interface consistent with other input widgets."""

    valueChanged = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.stateChanged.connect(lambda state: self.valueChanged.emit(bool(state)))

    def value(self) -> bool:
        """Return whether the checkbox is checked."""
        return self.isChecked()

    def setValue(self, new_value: bool) -> None:
        """Set whether the checkbox is checked."""
        self.setChecked(new_value)