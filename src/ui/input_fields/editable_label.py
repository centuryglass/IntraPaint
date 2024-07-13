"""A label that can be double-clicked for editing."""
from typing import Optional

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QLineEdit, QToolButton, QStyle

from src.util.image_utils import get_standard_qt_icon


class EditableLabel(QWidget):
    """A label that can be double-clicked for editing."""

    text_changed = pyqtSignal(str)

    def __init__(self, text: str = '', parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._label = QLabel(text)
        self._field = QLineEdit(text)
        self._cancel_button = QToolButton()
        self._cancel_button.setIcon(get_standard_qt_icon(QStyle.StandardPixmap.SP_DialogNoButton))
        self._cancel_button.clicked.connect(self.discard_changes)
        self._confirm_button = QToolButton()
        self._confirm_button.setIcon(get_standard_qt_icon(QStyle.StandardPixmap.SP_DialogOkButton))
        self._confirm_button.clicked.connect(self.apply_changes)
        self._layout.addWidget(self._label)

    def text(self) -> str:
        """Return the label text, ignoring unconfirmed input."""
        return self._label.text()

    def set_text(self, text: str) -> None:
        """Update the label/input text."""
        self._label.setText(text)
        self._field.setText(text)

    def setAlignment(self, alignment: Qt.AlignmentFlag) -> None:
        """Set the text alignment."""
        self._label.setAlignment(alignment)
        self._field.setAlignment(alignment)

    def setWordWrap(self, enable_word_wrap: bool) -> None:
        """Enable or disable word wrap (outside of editing mode)."""
        self._label.setWordWrap(enable_word_wrap)

    def is_requesting_input(self) -> bool:
        """Returns whether the label is in input mode."""
        return self._field.isVisible()

    def apply_changes(self) -> None:
        """Update the label text with the contents of the input field."""
        if not self.is_requesting_input():
            return
        if self._field.text() != self._label.text():
            self._label.setText(self._field.text())
            self.text_changed.emit(self._label.text())
        self._switch_to_display_mode()
        parent = self.parent()
        if parent is not None:
            parent.update()

    def discard_changes(self) -> None:
        """Stop editing the label and restore the previous text."""
        if not self.is_requesting_input():
            return
        if self._field.text() != self._label.text():
            self._field.setText(self._label.text())
        self._switch_to_display_mode()

    def mouseDoubleClickEvent(self, _) -> None:
        """Start editing when double-clicked."""
        if not self.is_requesting_input():
            self._switch_to_input_mode()

    def keyPressEvent(self, event: Optional[QKeyEvent]) -> None:
        """Confirm input with enter/return, cancel with escape."""
        if event is not None and self.is_requesting_input():
            if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
                self.apply_changes()
                return
            if event.key() == Qt.Key.Key_Escape:
                self.discard_changes()
                return
        super().keyPressEvent(event)

    def _switch_to_display_mode(self) -> None:
        for widget in (self._field, self._cancel_button, self._confirm_button):
            self._layout.removeWidget(widget)
            widget.setVisible(False)
            widget.setEnabled(False)
        self._layout.addWidget(self._label)
        self._label.setVisible(True)
        self._label.setEnabled(True)
        self.update()

    def _switch_to_input_mode(self) -> None:
        self._layout.removeWidget(self._label)
        self._label.setVisible(False)
        self._label.setEnabled(False)
        for widget in (self._field, self._cancel_button, self._confirm_button):
            self._layout.addWidget(widget)
            widget.setEnabled(True)
            widget.setVisible(True)
        self.update()
