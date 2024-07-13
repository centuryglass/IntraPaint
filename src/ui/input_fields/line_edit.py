"""A simple wrapper for QLineEdit to give it an interface consistent with other input widgets."""
from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLineEdit, QWidget


class LineEdit(QLineEdit):
    """A simple wrapper for QLineEdit to give it an interface consistent with other input widgets."""

    valueChanged = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.textChanged.connect(self.valueChanged.emit)

    def value(self) -> str:
        """Return the text value."""
        return self.text()

    def setValue(self, new_value: str) -> None:
        """Update the text value."""
        self.setText(new_value)
