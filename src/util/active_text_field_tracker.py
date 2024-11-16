"""Track the active widget, see if it's a text input field, and notify when cut/copy/clear/paste/undo/redo
   action availability change for an active text widget."""
from typing import TypeAlias, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QLineEdit, QTextEdit, QPlainTextEdit, QWidget, QAbstractSpinBox, QApplication

TextInput: TypeAlias = QLineEdit | QTextEdit | QPlainTextEdit


class ActiveTextFieldTracker(QObject):
    """Track the active widget, see if it's a text input field, and notify when cut/copy/clear/paste/undo/redo
       action availability change for an active text widget."""

    status_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._active_widget: Optional[TextInput] = None
        app = QApplication.instance()
        assert isinstance(app, QApplication)
        app.focusChanged.connect(self._update_active_widget)
        QApplication.clipboard().dataChanged.connect(self._monitor_clipboard_status)
        self._update_active_widget(None, QApplication.focusWidget())

    @property
    def focused_text_input(self) -> Optional[TextInput]:
        """Returns the focused text input, or None if no text input is focused."""
        return self._active_widget

    def focused_can_undo(self) -> bool:
        """Returns whether the focused widget has text-based undo support."""
        if self._active_widget is None:
            return False
        if isinstance(self._active_widget, (QTextEdit, QPlainTextEdit)):
            return self._active_widget.document().isUndoAvailable()
        if isinstance(self._active_widget, QAbstractSpinBox):
            return self._active_widget.lineEdit().isUndoAvailable()
        assert isinstance(self._active_widget, QLineEdit)
        return self._active_widget.isUndoAvailable()

    def focused_can_redo(self) -> bool:
        """Returns whether the focused widget has text-based redo support."""
        if self._active_widget is None:
            return False
        if isinstance(self._active_widget, (QTextEdit, QPlainTextEdit)):
            return self._active_widget.document().isRedoAvailable()
        if isinstance(self._active_widget, QAbstractSpinBox):
            return self._active_widget.lineEdit().isRedoAvailable()
        assert isinstance(self._active_widget, QLineEdit)
        return self._active_widget.isRedoAvailable()

    def clear_selected_in_focused(self):
        """Clears selected text in the active text input."""
        assert self._active_widget is not None
        if isinstance(self._active_widget, (QTextEdit, QPlainTextEdit)):
            self._active_widget.textCursor().removeSelectedText()
        else:
            assert isinstance(self._active_widget, QLineEdit)
            self._active_widget.insert('')

    def focused_can_cut_or_clear(self) -> bool:
        """Returns whether the focused widget has selected text that can be cut or cleared."""
        if self._active_widget is None or self._active_widget.isReadOnly():
            return False
        return self._active_has_selection()

    def focused_can_copy(self) -> bool:
        """Returns whether the focused widget has selected text that can be copied."""
        return self._active_has_selection()

    def focused_can_paste(self) -> bool:
        """Returns whether the focused widget can accept text and the clipboard contains valid text."""
        if self._active_widget is None or self._active_widget.isReadOnly():
            return False
        return QApplication.clipboard().mimeData().hasText()

    def _active_has_selection(self) -> bool:
        if self._active_widget is None:
            return False
        if isinstance(self._active_widget, QLineEdit):
            return self._active_widget.selectionLength() > 0
        assert isinstance(self._active_widget, (QTextEdit, QPlainTextEdit))
        cursor = self._active_widget.textCursor()
        return (cursor.selectionEnd() - cursor.selectionStart()) > 0

    def _send_update_signal(self, _=None) -> None:
        self.status_changed.emit()

    def _update_active_widget(self, _, widget: Optional[QWidget]) -> None:
        if isinstance(widget, QAbstractSpinBox):
            widget = widget.lineEdit()
        if not isinstance(widget, TextInput):
            widget = None
        if widget == self._active_widget:
            return
        if self._active_widget is not None:
            self._active_widget.selectionChanged.disconnect(self._send_update_signal)
            if isinstance(self._active_widget, (QTextEdit, QPlainTextEdit)):
                self._active_widget.undoAvailable.disconnect(self._send_update_signal)
                self._active_widget.redoAvailable.disconnect(self._send_update_signal)
            else:
                self._active_widget.textChanged.disconnect(self._send_update_signal)

        self._active_widget = widget
        if isinstance(self._active_widget, TextInput):
            self._active_widget.selectionChanged.connect(self._send_update_signal)
            if isinstance(self._active_widget, (QTextEdit, QPlainTextEdit)):
                self._active_widget.undoAvailable.connect(self._send_update_signal)
                self._active_widget.redoAvailable.connect(self._send_update_signal)
            else:
                assert self._active_widget is not None
                self._active_widget.textChanged.connect(self._send_update_signal)
        self.status_changed.emit()

    def _monitor_clipboard_status(self) -> None:
        """Re-check if paste is valid anytime the clipboard changes."""
        if self._active_widget is not None:
            self.status_changed.emit()
