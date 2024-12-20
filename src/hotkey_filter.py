"""Passes ImageViewer input events to an active editing tool."""
import logging
from dataclasses import dataclass
from typing import Optional, Callable, cast, TypeAlias

from PySide6.QtCore import Qt, QObject, QEvent, Signal, QTimer
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QWidget, QTextEdit, QLineEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox, FloatSliderSpinbox
from src.ui.widget.key_hint_label import KeyHintLabel
from src.util.key_code_utils import get_modifiers, get_modifier_string, get_key_string, get_key_with_modifiers

logger = logging.getLogger(__name__)

MODIFIER_TIMER_INTERVAL_MS = 100

KeybindingAction: TypeAlias = Callable[[], bool] | Callable[[], None] | Callable[[], bool | None]


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

    @dataclass
    class KeyBinding:
        """Holds key binding information

        KeyBinding.str_id:
            String used to identify this binding.
        KeyBinding.action:
            Function the key binding should invoke. Optionally returns whether the function consumed the key event.
        KeyBinding.key:
            Key that should invoke the action.
        KeyBinding.modifiers:
            Exact keyboard modifiers required to invoke the action.  If none, modifiers will be ignored.
        """
        str_id: str
        action: KeybindingAction
        key: Qt.Key | int
        modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier

    def __init__(self) -> None:
        """Registers and handles application-level hotkeys."""
        super().__init__()
        if HotkeyFilter.shared_instance is not None:
            raise RuntimeError("HotkeyFilter shouldn't be initialized directly; use HotkeyFilter.instance()")
        HotkeyFilter.shared_instance = self
        self._bindings: dict[Qt.Key | int, list[HotkeyFilter.KeyBinding]] = {}
        app = QApplication.instance()
        assert app is not None, 'No QApplication initialized'
        app.installEventFilter(self)
        self._default_focus: Optional[QWidget] = None
        self._last_modifier_state = QApplication.keyboardModifiers()
        self._config_bindings: dict[str, Qt.Key | int] = {}
        self._hotkey_timer = QTimer(self)
        self._hotkey_timer.setInterval(MODIFIER_TIMER_INTERVAL_MS)
        self._hotkey_timer.timeout.connect(self._check_modifiers)
        self._hotkey_timer.start()

    def default_focus(self) -> Optional[QWidget]:
        """Returns the widget set as the default input focus, if any."""
        return self._default_focus

    def set_default_focus(self, focus_widget: Optional[QWidget]) -> None:
        """Sets or clears the default focus widget. If a focus widget is set, pressing escape within a text input
           returns focus to the focus widget."""
        self._default_focus = focus_widget

    def register_keybinding(self, str_id: str, action: KeybindingAction, keys: QKeySequence,
                            modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier
                            ) -> list[tuple[Qt.Key, 'HotkeyFilter.KeyBinding']]:
        """Register a keystroke that should invoke an action.

        If keybindings share a key, newer ones will be checked before older ones. This makes it easier to add
        context-specific overrides for keys that only take effect when a particular widget is present.

        Parameters
        ----------
        str_id: str
            Identifier to assign to this binding, to be used if needed to remove the binding later.
        action: Callable
            Function the key binding should invoke. Optionally returns whether the function consumed the key event.
            If None is returned, it is assumed to always consume the event.
        keys: QKeySequence
            List of valid keys that should invoke the action.
        modifiers: Qt.KeyboardModifiers, optional
            Exact keyboard modifiers required to invoke the action, defaults to Qt.NoModifier.
        """
        new_bindings: list[tuple[Qt.Key, 'HotkeyFilter.KeyBinding']] = []
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

            keybinding = HotkeyFilter.KeyBinding(str_id, action, key, key_modifiers)
            if key not in self._bindings:
                self._bindings[key] = []
            self._bindings[key].insert(0, keybinding)
            new_bindings.append((key, keybinding))
        return new_bindings

    def remove_keybinding(self, str_id: str) -> None:
        """Finds and removes all keybindings with the given ID string."""
        to_remove: list[tuple[Qt.Key | int, int]] = []
        for key, key_list in self._bindings.items():
            for i, binding in enumerate(key_list):
                if binding.str_id == str_id:
                    to_remove.append((key, i))
        for key, idx in reversed(sorted(to_remove, key=lambda entry: entry[1])):
            self._bindings[key].pop(idx)

    def register_config_keybinding(self, str_id: str, action: KeybindingAction, config_key: str) -> None:
        """Register a keybinding defined in application config.

        Parameters
        ----------
        str_id: str
            Identifier to assign to this binding, to be used if needed to remove the binding later.
        action: Callable
            Function the key binding should invoke. Optionally returns whether the function consumed the key event.
            If None is returned, it is assumed to always consume the event.
        config_key: str
            Key string for the appropriate key or keys.
        """
        key_text = KeyConfig().get(config_key)
        assert isinstance(key_text, str)
        keys = key_text.split(',')
        for binding_str in keys:
            try:
                key, modifiers = get_key_with_modifiers(binding_str)
                self.register_keybinding(str_id, action, QKeySequence(key), modifiers)
            except ValueError:
                logger.warning(f'Skipping invalid key "{binding_str}" for config key {config_key}')
                continue

        _id = str_id
        _config_key = config_key
        _action = action

        def _update_config(_) -> None:
            # Remove and replace bindings when the config key changes:
            self.remove_keybinding(_id)
            KeyConfig().disconnect(_id, _config_key)
            self.register_config_keybinding(str_id, _action, _config_key)
        KeyConfig().connect(str_id, config_key, _update_config)

    def register_speed_modified_keybinding(self, str_id: str,
                                           scaling_action: Callable[[int], bool] | Callable[[int], None],
                                           config_key: str) -> None:
        """Register a keybinding defined in application config that's affected by the speed modifier.

        If the speed_modifier key has a valid definition in the config file, some actions operate at increased speed if
        that modifier is held. This function will register both the base and increased speed versions of those bindings.

        Parameters
        ----------
        str_id: str
            Identifier to assign to this binding, to be used if needed to remove the binding later.
        scaling_action: Callable[[int], bool]
            Function the key binding should invoke. The int parameter is a multiplier that the function should apply to
            some scalar action it performs. Return value is whether the function consumed the key event, or None if
            the function always consumes the event.
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
            try:
                key, modifiers = get_key_with_modifiers(binding_str)
            except ValueError:
                logger.warning(f'Skipping invalid key "{binding_str}" for config key {config_key}')
                continue
            self.register_keybinding(str_id, lambda: scaling_action(1), QKeySequence(key), modifiers)
            if (speed_modifier | modifiers) != modifiers:
                self.register_keybinding(str_id,
                                         lambda: scaling_action(AppConfig().get(AppConfig.SPEED_MODIFIER_MULTIPLIER)),
                                         QKeySequence(key), modifiers | speed_modifier)

        _id = str_id
        _config_key = config_key
        _action = scaling_action

        def _update_config(_) -> None:
            # Remove and replace bindings when the config key changes:
            self.remove_keybinding(_id)
            KeyConfig().disconnect(_id, _config_key)
            self.register_speed_modified_keybinding(str_id, _action, _config_key)
        KeyConfig().connect(str_id, config_key, _update_config)

    def bind_slider_controls(self, slider: IntSliderSpinbox | FloatSliderSpinbox, down_key: str, up_key: str,
                             predicate: KeybindingAction) -> None:
        """Applies speed modified keybindings to a SliderSpinbox, and sets its control hints."""
        for key, sign in ((down_key, -1), (up_key, 1)):
            def _binding(mult, n=sign, widget=slider) -> bool:
                if not predicate():
                    return False
                steps = n * mult
                widget.stepBy(steps)
                return True

            binding_id = f'_SliderSpinBox_{id(slider)}_{key}'
            self.register_speed_modified_keybinding(binding_id, _binding, key)
        down_hint = KeyHintLabel(None, down_key, slider)
        up_hint = KeyHintLabel(None, up_key, slider)
        up_hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        down_hint.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        slider.insert_key_hint_labels(down_hint, up_hint)

    def eventFilter(self, source: Optional[QObject], event: Optional[QEvent]) -> bool:
        """Check for registered keys and trigger associated actions."""
        if event is None or (source is not None and not isinstance(source, QObject)):
            return False
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(source, event)
        event = cast(QKeyEvent, event)

        # Avoid blocking inputs to text fields:
        focused_widget = QApplication.focusWidget()
        if (isinstance(focused_widget, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox))
                and focused_widget.isVisible()):
            # Cut/copy/paste/clear bindings can dynamically handle selecting between text and image content, so let
            # these run as usual.
            is_text_control_event = False
            text_control_bindings = (
                KeyConfig.CUT_SHORTCUT,
                KeyConfig.COPY_SHORTCUT,
                KeyConfig.PASTE_SHORTCUT,
                KeyConfig.CLEAR_SHORTCUT,
                KeyConfig.UNDO_SHORTCUT,
                KeyConfig.REDO_SHORTCUT
            )
            for control_binding in text_control_bindings:
                if is_text_control_event:
                    break
                binding_string = KeyConfig().get(control_binding)
                binding_key, binding_modifiers = get_key_with_modifiers(binding_string)
                if binding_key is not None and event.key() == binding_key \
                        and (binding_modifiers is None or QApplication.keyboardModifiers() == binding_modifiers):
                    is_text_control_event = True
            if event.key() == Qt.Key.Key_Escape and self._default_focus is not None and self._default_focus.isVisible():
                self._default_focus.setFocus()
                return True
            if (not is_text_control_event and isinstance(focused_widget, QAbstractSpinBox)
                    and event.key() in self._bindings):
                # Let keybindings work within numeric fields if they're not also keys used by the input:
                numeric_inputs = {
                    Qt.Key.Key_1,
                    Qt.Key.Key_2,
                    Qt.Key.Key_3,
                    Qt.Key.Key_4,
                    Qt.Key.Key_5,
                    Qt.Key.Key_6,
                    Qt.Key.Key_7,
                    Qt.Key.Key_8,
                    Qt.Key.Key_9,
                    Qt.Key.Key_0,
                    Qt.Key.Key_Period,
                    # Navigation:
                    Qt.Key.Key_Minus,
                    Qt.Key.Key_Left,
                    Qt.Key.Key_Right,
                    Qt.Key.Key_Up,
                    Qt.Key.Key_Down,
                    Qt.Key.Key_Home,
                    Qt.Key.Key_End,
                    Qt.Key.Key_PageUp,
                    Qt.Key.Key_PageDown,
                    Qt.Key.Key_Backspace,
                    Qt.Key.Key_Delete
                }
                if event.key() in numeric_inputs:
                    return False
                if QApplication.keyboardModifiers() == Qt.KeyboardModifier.ControlModifier:
                    shortcut_keys = {
                        Qt.Key.Key_A,
                        Qt.Key.Key_C,
                        Qt.Key.Key_V,
                        Qt.Key.Key_X
                    }
                    if event.key() in shortcut_keys:
                        return False
            elif not is_text_control_event:
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
            result = binding.action()
            event_handled = result if result is not None else True
            if event_handled:
                logger.debug(f'{event.text()}: claimed by handler {i} of {len(self._bindings[event.key()])}')
                break
            logger.debug(f'{event.text()}: not claimed by handler {i} of {len(self._bindings[event.key()])}: '
                         f'got {event_handled}')
        return event_handled

    def _check_modifiers(self):
        """Check for changes in held key modifiers, notifying any registered listeners."""
        modifiers = QApplication.queryKeyboardModifiers()
        if modifiers == self._last_modifier_state:
            return
        self._last_modifier_state = modifiers
        self.modifiers_changed.emit(self._last_modifier_state)
