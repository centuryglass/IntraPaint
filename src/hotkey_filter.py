"""Passes ImageViewer input events to an active editing tool."""
import logging
from dataclasses import dataclass
from typing import Optional, Callable, cast, TypeAlias

from PySide6.QtCore import Qt, QObject, QEvent, Signal, QTimer, SIGNAL
from PySide6.QtGui import QKeyEvent, QKeySequence, QGuiApplication, QWindow
from PySide6.QtWidgets import (QApplication, QWidget, QTextEdit, QLineEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox,
                               QAbstractButton, QAbstractSlider, QAbstractItemView)

from src.config.key_config import KeyConfig
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox, FloatSliderSpinbox
from src.ui.widget.color_picker.gradient_slider import GradientSlider
from src.ui.widget.key_hint_label import KeyHintLabel
from src.util.key_code_utils import get_modifier_string, get_key_with_modifiers, key_alternatives

logger = logging.getLogger(__name__)

MODIFIER_TIMER_INTERVAL_MS = 100

KeybindingAction: TypeAlias = Callable[[], bool] | Callable[[], None] | Callable[[], bool | None]


class HotkeyFilter(QObject):
    """Registers and handles window-level hotkeys.

    The filter is installed on each window's QWindow when that window first takes focus, so it sees key presses
    before any widget does. A key event sent straight to a widget with `QApplication.sendEvent` never reaches a
    QWindow, so it skips every binding. To reach the bindings, send the key to the window's QWindow.
    """

    shared_instance: Optional['HotkeyFilter'] = None
    modifiers_changed = Signal(Qt.KeyboardModifier)

    # Called with each event source that isn't a QObject. Tests set this to fail the running test.
    stale_source_hook: Optional[Callable[[object], None]] = None

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

    @dataclass
    class HeldKeyBinding:
        """A key whose held state is tracked from its press to its release.

        HeldKeyBinding.str_id:
            String used to identify this binding.
        HeldKeyBinding.on_change:
            Called with True when the key goes down and False when it comes back up.
        HeldKeyBinding.key / modifiers:
            The key, and the exact modifiers that must be held when it goes down.
        HeldKeyBinding.predicate:
            Whether a press may start holding the key.
        HeldKeyBinding.held:
            Whether the key is currently held.
        """
        str_id: str
        on_change: Callable[[bool], None]
        key: Qt.Key | int
        modifiers: Qt.KeyboardModifier
        predicate: Callable[[], bool]
        held: bool = False

    def __init__(self) -> None:
        """Registers and handles application-level hotkeys."""
        super().__init__()
        if HotkeyFilter.shared_instance is not None:
            raise RuntimeError("HotkeyFilter shouldn't be initialized directly; use HotkeyFilter.instance()")
        HotkeyFilter.shared_instance = self
        self._bindings: dict[Qt.Key | int, list[HotkeyFilter.KeyBinding]] = {}
        self._held_bindings: list[HotkeyFilter.HeldKeyBinding] = []
        app = QApplication.instance()
        assert isinstance(app, QGuiApplication), 'No QApplication initialized'
        self._default_focus: Optional[QWidget] = None
        self._last_modifier_state = QApplication.keyboardModifiers()
        self._config_bindings: dict[str, Qt.Key | int] = {}
        self._hotkey_timer = QTimer(self)
        self._hotkey_timer.setInterval(MODIFIER_TIMER_INTERVAL_MS)
        self._hotkey_timer.timeout.connect(self._check_modifiers)
        self._hotkey_timer.start()
        app.focusWindowChanged.connect(self.watch_window)
        self.watch_window(QGuiApplication.focusWindow())
        self._stale_source_types: set[str] = set()

    def _reset(self) -> None:
        """Removes all keybindings, the default focus widget, and all modifiers_changed connections.

        Tests call this between cases, since bindings and connections from one test would otherwise act on the next.
        """
        self._bindings.clear()
        self._held_bindings.clear()
        self._config_bindings.clear()
        self._default_focus = None
        self._last_modifier_state = QApplication.keyboardModifiers()
        if self.receivers(SIGNAL('modifiers_changed(Qt::KeyboardModifier)')) > 0:
            self.modifiers_changed.disconnect()

    def watch_window(self, window: Optional[QWindow]) -> None:
        """Handles key presses sent to a window, ahead of the window's other event filters.

        Watching a window twice doesn't install the filter twice. Stops modifier polling while
        no window of the app has focus, and re-syncs the last-seen state before resuming. Held keys are released,
        because the release event goes to whichever window has focus then.
        """
        self._release_held_keys()
        if window is not None:
            window.installEventFilter(self)
            self._last_modifier_state = QApplication.queryKeyboardModifiers()
            self._hotkey_timer.start()
        else:
            self._hotkey_timer.stop()

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
        for combination in (keys[i] for i in range(keys.count())):
            key = combination.key()
            assert key != Qt.Key.Key_unknown, 'Invalid keybinding'
            # Modifiers written into the key sequence, as in 'Shift+Z', add to the `modifiers` parameter:
            key_modifiers = modifiers | combination.keyboardModifiers()

            keybinding = HotkeyFilter.KeyBinding(str_id, action, key, key_modifiers)
            if key not in self._bindings:
                self._bindings[key] = []
            self._bindings[key].insert(0, keybinding)
            new_bindings.append((key, keybinding))
        return new_bindings

    def remove_keybinding(self, str_id: str) -> None:
        """Finds and removes all keybindings with the given ID string, releasing held keys among them."""
        for held_binding in [binding for binding in self._held_bindings if binding.str_id == str_id]:
            self._held_bindings.remove(held_binding)
            if held_binding.held:
                held_binding.on_change(False)
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
        for binding_str in key_alternatives(key_text):
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

    def register_held_key(self, str_id: str, on_change: Callable[[bool], None], config_key: str,
                          predicate: Optional[Callable[[], bool]] = None) -> None:
        """Tracks whether a key defined in application config is held, from its press to its release.

        A press starts the hold only while `predicate` returns True and the focused widget isn't one that uses the key
        itself (a text field, button, slider or list). The key event is not consumed. Releasing the key, losing
        window focus, or removing the binding ends the hold.

        Parameters
        ----------
        str_id: str
            Identifier to assign to this binding, to be used if needed to remove the binding later.
        on_change: Callable[[bool], None]
            Called with True when the hold starts and False when it ends.
        config_key: str
            Key string for the appropriate key or keys.
        predicate: Callable[[], bool], optional
            Whether a press may start a hold. Defaults to always.
        """
        key_text = KeyConfig().get(config_key)
        assert isinstance(key_text, str)
        for binding_str in key_alternatives(key_text):
            try:
                key, modifiers = get_key_with_modifiers(binding_str)
            except ValueError:
                logger.warning(f'Skipping invalid key "{binding_str}" for config key {config_key}')
                continue
            if key is None:
                logger.warning(f'Skipping modifier-only key "{binding_str}" for config key {config_key}')
                continue
            self._held_bindings.append(HotkeyFilter.HeldKeyBinding(str_id, on_change, key, modifiers,
                                                                   predicate if predicate is not None
                                                                   else (lambda: True)))

        _id = str_id
        _config_key = config_key
        _on_change = on_change
        _predicate = predicate

        def _update_config(_) -> None:
            # Remove and replace bindings when the config key changes:
            self.remove_keybinding(_id)
            KeyConfig().disconnect(_id, _config_key)
            self.register_held_key(_id, _on_change, _config_key, _predicate)
        KeyConfig().connect(str_id, config_key, _update_config)

    def _release_held_keys(self) -> None:
        """Ends every key hold that is in progress."""
        for binding in self._held_bindings:
            if binding.held:
                binding.held = False
                binding.on_change(False)

    def _handle_held_key_event(self, event: QKeyEvent) -> None:
        """Starts or ends key holds in response to a key press or release."""
        if event.isAutoRepeat():
            return
        pressed = event.type() == QEvent.Type.KeyPress
        event_modifiers = event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier
        for binding in list(self._held_bindings):
            if binding.key != event.key():
                continue
            if not pressed:
                if binding.held:
                    binding.held = False
                    binding.on_change(False)
            elif not binding.held and binding.modifiers == event_modifiers and binding.predicate() \
                    and not self._focused_widget_uses_keys():
                binding.held = True
                binding.on_change(True)

    @staticmethod
    def _focused_widget_uses_keys() -> bool:
        """Returns whether the focused widget is one that acts on a bare key press itself."""
        focused_widget = QApplication.focusWidget()
        return (isinstance(focused_widget, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox,
                                            GradientSlider, QAbstractButton, QAbstractSlider, QAbstractItemView))
                and focused_widget.isVisible())

    def bind_slider_controls(self, slider: IntSliderSpinbox | FloatSliderSpinbox, down_key: str, up_key: str,
                             predicate: KeybindingAction) -> None:
        """Applies keybindings that step a SliderSpinbox, and sets its control hints."""
        for key, sign in ((down_key, -1), (up_key, 1)):
            def _binding(n=sign, widget=slider) -> bool:
                if not predicate():
                    return False
                widget.stepBy(n)
                return True

            binding_id = f'_SliderSpinBox_{id(slider)}_{key}'
            self.register_config_keybinding(binding_id, _binding, key)
        down_hint = KeyHintLabel(None, down_key, slider)
        up_hint = KeyHintLabel(None, up_key, slider)
        up_hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        down_hint.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        slider.insert_key_hint_labels(down_hint, up_hint)

    def eventFilter(self, source: Optional[QObject], event: Optional[QEvent]) -> bool:
        """Check for registered keys and trigger associated actions."""
        if source is not None and not isinstance(source, QObject):
            self._report_stale_source(source)
            return False
        if event is not None and event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            self._handle_held_key_event(cast(QKeyEvent, event))
        if event is None or event.type() != QEvent.Type.KeyPress:
            return False
        event = cast(QKeyEvent, event)

        # Avoid blocking inputs to text fields:
        focused_widget = QApplication.focusWidget()
        if (isinstance(focused_widget, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox,
                                        GradientSlider))
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
                # In another top-level window (a floating panel), setFocus only records the focus child; the
                # active window has to change for the field to lose keyboard focus.
                if self._default_focus.window() is not focused_widget.window():
                    self._default_focus.window().activateWindow()
                self._default_focus.setFocus()
                return True
            if (not is_text_control_event and isinstance(focused_widget, (QAbstractSpinBox, GradientSlider))
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
                    Qt.Key.Key_Plus,
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
            return False
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

    def _report_stale_source(self, source: object) -> None:
        """Logs an event source that isn't a QObject, once per type, and passes it to `stale_source_hook`.

        Qt only passes QObjects to event filters, so any other source is a stale PySide wrapper left at a reused
        address by a freed object, such as a QLayoutItem. The heap may already be corrupt when this runs.
        """
        type_name = type(source).__qualname__
        if type_name not in self._stale_source_types:
            self._stale_source_types.add(type_name)
            logger.error(f'Event filter received a non-QObject source of type {type_name}: stale PySide wrapper')
        if HotkeyFilter.stale_source_hook is not None:
            HotkeyFilter.stale_source_hook(source)

    def _check_modifiers(self):
        """Check for changes in held key modifiers, notifying any registered listeners."""
        modifiers = QApplication.queryKeyboardModifiers()
        if modifiers == self._last_modifier_state:
            return
        self._last_modifier_state = modifiers
        self.modifiers_changed.emit(self._last_modifier_state)
