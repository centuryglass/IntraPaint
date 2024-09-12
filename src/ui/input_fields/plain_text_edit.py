"""A simple wrapper for QPlainTextEdit to give it an interface consistent with other input widgets."""
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPlainTextEdit, QWidget


class PlainTextEdit(QPlainTextEdit):
    """A simple wrapper for QPlainTextEdit to give it an interface consistent with other input widgets."""

    valueChanged = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.textChanged.connect(lambda: self.valueChanged.emit(self.toPlainText()))

    def value(self) -> str:
        """Return the text value."""
        return self.toPlainText()

    # noinspection PyPep8Naming
    def setValue(self, new_value: str) -> None:
        """Update the text value."""
        self.setPlainText(new_value)
