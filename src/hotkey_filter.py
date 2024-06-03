"""Passes ImageViewer input events to an active editing tool."""
from sys import version_info
if version_info[1] >= 11:
    from typing import Self, Optional, Dict, Callable, List, cast
else:
    from typing import Optional, Dict, Callable, List, cast
    from typing_extensions import Self
from PyQt5.QtCore import Qt, QObject, QEvent
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QApplication, QWidget, QTextEdit, QLineEdit, QPlainTextEdit, QAbstractSpinBox, QDialog


class HotkeyFilter(QObject):
    """Registers and handles window-level hotkeys."""

    shared_instance = None

    @staticmethod
    def instance() -> Self:
        """Returns the shared application hotkey manager."""
        if HotkeyFilter.shared_instance is None:
            return HotkeyFilter()
        return HotkeyFilter.shared_instance

    class KeyBinding:
        """Holds keybinding information

        KeyBinding.action:
            Function the key binding should invoke. Returns whether the function consumed the key event.
        KeyBinding.key:
            Key that should invoke the action.
        KeyBinding.modifiers:
            Exact keyboard modifiers required to invoke the action.  If none, modifiers will be ignored.
        KeyBinding.widget:
            If not None, the action should only be invoked if this widget is showing.
        """

        def __init__(self, action: Callable[[], bool], key: Qt.Key,
                     modifiers: Optional[Qt.KeyboardModifier | Qt.KeyboardModifiers] = None,
                     widget: Optional[QWidget] = None):
            self.action = action
            self.key = key
            self.modifiers = modifiers
            self.widget = widget

    def __init__(self):
        """Registers and handles application-level hotkeys."""
        super().__init__()
        if HotkeyFilter.shared_instance  is not None:
            raise RuntimeError("HotkeyFilter shouldn't be initialized directly; use HotkeyFilter.instance()")
        HotkeyFilter.shared_instance = self
        self._bindings: Dict[Qt.Key: List[HotkeyFilter.KeyBinding]] = {}
        QApplication.instance().installEventFilter(self)
        self._default_focus = None

    def set_default_focus(self, focus_widget: Optional[QWidget]) -> None:
        """Sets or clears the default focus widget. If a focus widget is set, pressing escape within a text input
           returns focus to the focus widget."""
        self._default_focus = focus_widget

    def register_keybinding(self, action: Callable[[], bool], key: Qt.Key,
                            modifiers: Optional[Qt.KeyboardModifier | Qt.KeyboardModifiers] = None,
                            widget: Optional[QWidget] = None) -> None:
        """Register a keystroke that should invoke an action.

        Parameters
        ----------
        action: Callable
            Function the key binding should invoke. Returns whether the function consumed the key event.
        key: Qt.Key
            Keypress that should invoke the action.
        modifiers: Qt.KeyboardModifiers, optional
            Exact keyboard modifiers required to invoke the action.  If none, modifiers will be ignored.
        widget: QWidget, optional
            If not None, the action should only be invoked if this widget is showing.
        """
        keybinding = HotkeyFilter.KeyBinding(action, key, modifiers, widget)
        if key not in self._bindings:
            self._bindings[key] = []
        self._bindings[key].append(keybinding)

    def eventFilter(self, source: QObject, event: QEvent):
        """Check for registered keys and trigger associated actions."""
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(source, event)
        # Avoid blocking inputs to text fields:
        focused_widget = QApplication.focusWidget()
        if isinstance(focused_widget, (QLineEdit, QTextEdit, QLineEdit, QPlainTextEdit, QAbstractSpinBox, QDialog)):
            if event.key() == Qt.Key_Escape and self._default_focus is not None and self._default_focus.isVisible():
                self._default_focus.setFocus()
                return True
            return False
        event = cast(QKeyEvent, event)
        if event.key() not in self._bindings:
            return super().eventFilter(source, event)
        event_handled = False
        for binding in self._bindings[event.key()]:
            if binding.widget is not None and not binding.widget.isVisible():
                continue
            if binding.modifiers is not None and binding.modifiers != QApplication.keyboardModifiers():
                continue
            event_handled = binding.action()
            if event_handled:
                break
        return event_handled