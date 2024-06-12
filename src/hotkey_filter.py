"""Passes ImageViewer input events to an active editing tool."""
from typing import Optional, Dict, Callable, List, cast
import logging

from PyQt5.QtCore import Qt, QObject, QEvent
from PyQt5.QtGui import QKeyEvent, QKeySequence
from PyQt5.QtWidgets import QApplication, QWidget, QTextEdit, QLineEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox

from src.config.application_config import AppConfig
from src.util.key_code_utils import get_modifiers, get_modifier_string, get_key_string

logger = logging.getLogger(__name__)


class HotkeyFilter(QObject):
    """Registers and handles window-level hotkeys."""

    shared_instance = None

    @staticmethod
    def instance() -> 'HotkeyFilter':
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
        """

        def __init__(self, action: Callable[[], bool], key: Qt.Key | int,
                     modifiers: Qt.KeyboardModifier | Qt.KeyboardModifiers | int = Qt.NoModifier):
            self.action = action
            self.key = key
            self.modifiers = modifiers

    def __init__(self):
        """Registers and handles application-level hotkeys."""
        super().__init__()
        if HotkeyFilter.shared_instance is not None:
            raise RuntimeError("HotkeyFilter shouldn't be initialized directly; use HotkeyFilter.instance()")
        HotkeyFilter.shared_instance = self
        self._bindings: Dict[Qt.Key: List[HotkeyFilter.KeyBinding]] = {}
        QApplication.instance().installEventFilter(self)
        self._default_focus = None

    def set_default_focus(self, focus_widget: Optional[QWidget]) -> None:
        """Sets or clears the default focus widget. If a focus widget is set, pressing escape within a text input
           returns focus to the focus widget."""
        self._default_focus = focus_widget

    def register_keybinding(self, action: Callable[[], bool], keys: QKeySequence,
                            modifiers: Qt.KeyboardModifier | Qt.KeyboardModifiers | int = Qt.NoModifier) -> None:
        """Register a keystroke that should invoke an action.

        If keybindings share a key, newer ones will be checked before older ones. This makes it easier to add
        context-specific overrides for keys that only take effect when a particular widget is present.

        Parameters
        ----------
        action: Callable
            Function the key binding should invoke. Returns whether the function consumed the key event.
        keys: QKeySequence
            List of valid keys that should invoke the action.
        modifiers: Qt.KeyboardModifiers, optional
            Exact keyboard modifiers required to invoke the action, defaults to Qt.NoModifier.
        """
        for key in keys:
            assert key != Qt.Key_unknown, 'Invalid keybinding'
            key_string = get_key_string(key)
            key_modifiers = modifiers
            if '+' in key_string:  # Divide out any modifiers passed in via the key parameter
                if key_modifiers is None:
                    key_modifiers = Qt.KeyboardModifier.NoModifier
                keys = key_string.split('+')
                key_modifiers = key_modifiers | get_modifiers(keys[:-1])
                key = QKeySequence(keys[-1])[0]

            keybinding = HotkeyFilter.KeyBinding(action, key, key_modifiers)
            if key not in self._bindings:
                self._bindings[key] = []
            self._bindings[key].insert(0, keybinding)

    def register_config_keybinding(self, action: Callable[[], bool], config_key: str) -> None:
        """Register a keybinding defined in application config.

        Parameters
        ----------
        action: Callable
            Function the key binding should invoke. Returns whether the function consumed the key event.
        config_key: str
            Key string for the appropriate key or keys.
        """
        keys = AppConfig.instance().get_keycodes(config_key)
        self.register_keybinding(action, keys, Qt.NoModifier)

    def register_speed_modified_keybinding(self, scaling_action: Callable[[int], bool], config_key: str) -> None:
        """Register a keybinding defined in application config that's affected by the speed modifier.

        If the speed_modifier key has a valid definition in the config file, some actions operate at increased speed if
        that modifier is held. This function will register both the base and increased speed versions of those bindings.

        Parameters
        ----------
        scaling_action: Callable[[int], bool]
            Function the key binding should invoke. The int parameter is a multiplier that the function should apply to
            some scalar action it performs. Return value is whether the function consumed the key event.
        config_key: str
            Key string for the appropriate key or keys.
        """
        config = AppConfig.instance()
        keys = config.get_keycodes(config_key)
        self.register_keybinding(lambda: scaling_action(1), keys, Qt.NoModifier)

        modifier_string = config.get(AppConfig.SPEED_MODIFIER)
        try:
            modifier = get_modifiers(modifier_string)
        except RuntimeError:
            logger.error(f'Unsupported speed_modifier {modifier_string} not applied to {config_key} binding')
            return
        if modifier != Qt.KeyboardModifier.NoModifier:
            multiplier = config.get(AppConfig.SPEED_MODIFIER_MULTIPLIER)
            self.register_keybinding(lambda: scaling_action(multiplier), keys, modifier)

    def eventFilter(self, source: Optional[QObject], event: Optional[QEvent]) -> bool:
        """Check for registered keys and trigger associated actions."""
        if event is None:
            return False
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(source, event)
        event = cast(QKeyEvent, event)

        # Avoid blocking inputs to text fields:
        focused_widget = QApplication.focusWidget()
        if isinstance(focused_widget, (QLineEdit, QTextEdit, QLineEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox)):
            if event.key() == Qt.Key_Escape and self._default_focus is not None and self._default_focus.isVisible():
                self._default_focus.setFocus()
                return True
            return False
        if event.key() not in self._bindings:
            return super().eventFilter(source, event)
        event_handled = False
        for i, binding in enumerate(self._bindings[event.key()]):
            if binding.modifiers != QApplication.keyboardModifiers():
                logger.debug(
                    f'{event.text()}: not claimed by handler {i} of {len(self._bindings[event.key()])}: modifier'
                    f' mismatch, expected {get_modifier_string(binding.modifiers)}, found'
                    f' {get_modifier_string(QApplication.keyboardModifiers())}')
                continue
            event_handled = binding.action()
            if event_handled:
                logger.debug(f'{event.text()}: claimed by handler {i} of {len(self._bindings[event.key()])}')
                break
            else:
                logger.debug(
                    f'{event.text()}: not claimed by handler {i} of {len(self._bindings[event.key()])}: got {event_handled}')
        return event_handled
