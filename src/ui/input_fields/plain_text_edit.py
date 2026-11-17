"""A simple wrapper for QPlainTextEdit to give it an interface consistent with other input widgets."""
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QPlainTextEdit, QWidget


class PlainTextEdit(QPlainTextEdit):
    """A simple wrapper for QPlainTextEdit to give it an interface consistent with other input widgets."""

    valueChanged = Signal(str)
    focus_lost = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.textChanged.connect(lambda: self.valueChanged.emit(self.toPlainText()))
        self.setTabChangesFocus(True)

    def value(self) -> str:
        """Return the text value."""
        return self.toPlainText()

    # noinspection PyPep8Naming
    def setValue(self, new_value: str) -> None:
        """Update the text value."""
        self.setPlainText(new_value)

    def focusOutEvent(self, event: Optional[QFocusEvent]) -> None:  # pylint: disable=invalid-name
        """Signals when the text box loses keyboard focus."""
        super().focusOutEvent(event)
        self.focus_lost.emit()
