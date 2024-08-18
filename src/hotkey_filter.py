"""Passes ImageViewer input events to an active editing tool."""
from typing import Optional, Dict, Callable, List, cast, Tuple
import logging

from PySide6.QtCore import Qt, QObject, QEvent, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QWidget, QTextEdit, QLineEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.util.key_code_utils import get_modifiers, get_modifier_string, get_key_string, get_key_with_modifiers

logger = logging.getLogger(__name__)


class HotkeyFilter(QObject):
    """Registers and handles window-level hotkeys."""

    shared_instance: Optional['HotkeyFilter'] = None
    modifiers_changed = Signal(Qt.KeyboardModifier)

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
                     modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier):
            self.action = action
            self.key = key
            self.modifiers = modifiers

    def __init__(self) -> None:
        """Registers and handles application-level hotkeys."""
        super().__init__()
        if HotkeyFilter.shared_instance is not None:
            raise RuntimeError("HotkeyFilter shouldn't be initialized directly; use HotkeyFilter.instance()")
        HotkeyFilter.shared_instance = self
        self._bindings: Dict[Qt.Key | int, List[HotkeyFilter.KeyBinding]] = {}
        app = QApplication.instance()
        assert app is not None, 'No QApplication initialized'
        app.installEventFilter(self)
        self._default_focus: Optional[QWidget] = None
        self._last_modifier_state = QApplication.keyboardModifiers()
        self._config_bindings: Dict[str, Qt.Key | int] = {}

    def default_focus(self) -> Optional[QWidget]:
        """Returns the widget set as the default input focus, if any."""
        return self._default_focus

    def set_default_focus(self, focus_widget: Optional[QWidget]) -> None:
        """Sets or clears the default focus widget. If a focus widget is set, pressing escape within a text input
           returns focus to the focus widget."""
        self._default_focus = focus_widget

    def register_keybinding(self, action: Callable[[], bool], keys: QKeySequence,
                            modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier
                            ) -> List[Tuple[Qt.Key, 'HotkeyFilter.KeyBinding']]:
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
        new_bindings: List[Tuple[Qt.Key, 'HotkeyFilter.KeyBinding']] = []
        # noinspection PyUnresolvedReferences
        for key in (keys[i] for i in range(keys.count())):
            key = key.key()
            assert key != Qt.Key.Key_unknown, 'Invalid keybinding'
            key_string = get_key_string(key)
            key_modifiers = modifiers
            if '+' in key_string:  # Divide out any modifiers passed in via the key parameter
                if key_modifiers is None:
                    key_modifiers = Qt.KeyboardModifier.NoModifier
                key_strings = key_string.split('+')
                key_modifiers = key_modifiers | get_modifiers(key_strings[:-1])
                # noinspection PyUnresolvedReferences
                key = QKeySequence(key_strings[-1])[0]

            keybinding = HotkeyFilter.KeyBinding(action, key, key_modifiers)
            if key not in self._bindings:
                self._bindings[key] = []
            self._bindings[key].insert(0, keybinding)
            new_bindings.append((key, keybinding))
        return new_bindings

    def register_config_keybinding(self, action: Callable[[], bool], config_key: str) -> None:
        """Register a keybinding defined in application config.

        Parameters
        ----------
        action: Callable
            Function the key binding should invoke. Returns whether the function consumed the key event.
        config_key: str
            Key string for the appropriate key or keys.
        """
        key_text = KeyConfig().get(config_key)
        assert isinstance(key_text, str)
        keys = key_text.split(',')
        new_bindings = []
        for binding_str in keys:
            key, modifiers = get_key_with_modifiers(binding_str)
            new_bindings += self.register_keybinding(action, QKeySequence(key), modifiers)
        if len(new_bindings) == 0:

            return
        connected_binding = new_bindings[0][1]
        connected_key = config_key

        def _update_config(_) -> None:
            # Remove and replace bindings when the config key changes:
            for prev_key, binding in new_bindings:
                self._bindings[prev_key].remove(binding)
            KeyConfig().disconnect(connected_binding, connected_key)
            assert isinstance(connected_binding, HotkeyFilter.KeyBinding)
            self.register_config_keybinding(connected_binding.action, connected_key)
        KeyConfig().connect(connected_binding, connected_key, _update_config)

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
        config = KeyConfig()
        speed_modifier_string = config.get(KeyConfig.SPEED_MODIFIER)
        try:
            speed_modifier = get_modifiers(speed_modifier_string)
        except RuntimeError:
            logger.error(f'Unsupported speed_modifier {speed_modifier_string} not applied to {config_key} binding')
            speed_modifier = Qt.KeyboardModifier.NoModifier
        key_text = KeyConfig().get(config_key)
        assert isinstance(key_text, str)
        keys = key_text.split(',')
        for binding_str in keys:
            key, modifiers = get_key_with_modifiers(binding_str)
            self.register_keybinding(lambda: scaling_action(1), QKeySequence(key), modifiers)
            if (speed_modifier | modifiers) != modifiers:
                self.register_keybinding(lambda: scaling_action(AppConfig().get(AppConfig.SPEED_MODIFIER_MULTIPLIER)),
                                         QKeySequence(key), modifiers | speed_modifier)

    def eventFilter(self, source: Optional[QObject], event: Optional[QEvent]) -> bool:
        """Check for registered keys and trigger associated actions."""
        self._check_modifiers()
        if event is None or (source is not None and not isinstance(source, QObject)):
            return False
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(source, event)
        event = cast(QKeyEvent, event)

        # Avoid blocking inputs to text fields:
        focused_widget = QApplication.focusWidget()
        if isinstance(focused_widget, (QLineEdit, QTextEdit, QLineEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox)):
            if event.key() == Qt.Key.Key_Escape and self._default_focus is not None and self._default_focus.isVisible():
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
            logger.debug(f'{event.text()}: not claimed by handler {i} of {len(self._bindings[event.key()])}: '
                         f'got {event_handled}')
        return event_handled

    def _check_modifiers(self):
        """Check for changes in held key modifiers, notifying any registered listeners."""
        modifiers = QApplication.keyboardModifiers()
        if modifiers == self._last_modifier_state:
            return
        self._last_modifier_state = modifiers
        self.modifiers_changed.emit(self._last_modifier_state)
