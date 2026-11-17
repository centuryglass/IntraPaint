"""Tests which key presses HotkeyFilter sees."""
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QGuiApplication, QKeyEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QLineEdit, QVBoxLayout, QWidget

from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from test.base_test_case import IntraPaintTestCase

BINDING_ID = 'hotkey_filter_test_binding'


def _key_press() -> QKeyEvent:
    return QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_F12, Qt.KeyboardModifier.NoModifier)


class HotkeyFilterTest(IntraPaintTestCase):
    """Tests that HotkeyFilter handles key presses sent to windows that have taken focus."""

    def setUp(self) -> None:
        super().setUp()
        self.action = MagicMock(return_value=True)
        HotkeyFilter.instance().register_keybinding(BINDING_ID, self.action, QKeySequence(Qt.Key.Key_F12))
        self.widget = QWidget()
        self.widget.winId()  # Creates the QWindow.
        window = self.widget.windowHandle()
        assert window is not None
        self.window = window

    def test_window_that_takes_focus_is_watched(self) -> None:
        """A key press sent to a window runs its binding once the window has taken focus."""
        app = QApplication.instance()
        assert isinstance(app, QGuiApplication)
        app.focusWindowChanged.emit(self.window)
        self.assertTrue(QApplication.sendEvent(self.window, _key_press()))
        self.action.assert_called_once()

    def test_unfocused_window_is_not_watched(self) -> None:
        """A key press sent to a window that never took focus doesn't run any binding."""
        QApplication.sendEvent(self.window, _key_press())
        self.action.assert_not_called()

    def test_key_sent_to_widget_skips_bindings(self) -> None:
        """A key press sent straight to a widget doesn't pass through a QWindow, so no binding sees it."""
        HotkeyFilter.instance().watch_window(self.window)
        QApplication.sendEvent(self.widget, _key_press())
        self.action.assert_not_called()

    def test_watching_twice_runs_binding_once(self) -> None:
        """Watching a window again doesn't install the filter a second time."""
        HotkeyFilter.instance().watch_window(self.window)
        HotkeyFilter.instance().watch_window(self.window)
        self.action.return_value = False
        QApplication.sendEvent(self.window, _key_press())
        self.action.assert_called_once()

    def test_escape_in_other_window_activates_default_focus_window(self) -> None:
        """Escape in a field of a floating panel activates the window holding the default focus widget."""
        floating = QWidget()
        field = QLineEdit(floating)
        QVBoxLayout(floating).addWidget(field)
        main = QWidget()
        target = QWidget(main)
        for widget in (floating, main):
            widget.show()
        hotkeys = HotkeyFilter.instance()
        hotkeys.set_default_focus(target)
        escape = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        # Offscreen windows never become active, so report the field as focused directly.
        with patch.object(QApplication, 'focusWidget', new=staticmethod(lambda: field)), \
                patch.object(QWidget, 'activateWindow') as activate:
            self.assertTrue(hotkeys.eventFilter(field, escape))
        activate.assert_called_once()

    def test_modifiers_in_key_sequence_are_required(self) -> None:
        """A binding registered as 'Shift+Z' runs only while Shift is held, and leaves plain Z unbound."""
        action = MagicMock(return_value=True)
        hotkeys = HotkeyFilter.instance()
        hotkeys.register_keybinding('hotkey_filter_test_shift_z', action, QKeySequence('Shift+Z'))
        z_press = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Z, Qt.KeyboardModifier.NoModifier)
        for held, expect_handled in ((Qt.KeyboardModifier.NoModifier, False),
                                     (Qt.KeyboardModifier.ShiftModifier, True)):
            # Offscreen key events don't update the application's modifier state, so report it directly.
            with patch.object(QApplication, 'keyboardModifiers', new=staticmethod(lambda mods=held: mods)):
                self.assertEqual(hotkeys.eventFilter(self.window, z_press), expect_handled)
        action.assert_called_once()


class HotkeyFilterZoomKeyTest(IntraPaintTestCase):
    """Tests that the bare zoom keys, which are also typed characters, don't fire while a text field has focus."""

    def setUp(self) -> None:
        super().setUp()
        self.zoom_out = MagicMock(return_value=True)
        self.zoom_in = MagicMock(return_value=True)
        hotkeys = HotkeyFilter.instance()
        hotkeys.register_config_keybinding('zoom_key_test_out', self.zoom_out, KeyConfig.ZOOM_OUT)
        hotkeys.register_config_keybinding('zoom_key_test_in', self.zoom_in, KeyConfig.ZOOM_IN)
        self.widget = QWidget()
        self.field = QLineEdit(self.widget)
        self.widget.show()
        window = self.widget.windowHandle()
        assert window is not None
        self.window = window

    def _press(self, key: Qt.Key, modifiers: Qt.KeyboardModifier, focused: QWidget | None) -> None:
        # Offscreen key events don't update the application's focus or modifier state, so report them directly.
        with patch.object(QApplication, 'keyboardModifiers', new=staticmethod(lambda: modifiers)), \
                patch.object(QApplication, 'focusWidget', new=staticmethod(lambda: focused)):
            HotkeyFilter.instance().eventFilter(self.window, QKeyEvent(QEvent.Type.KeyPress, key, modifiers))

    def test_minus_zooms_out_unless_typing(self) -> None:
        """Minus zooms out with no text field focused, and types into the focused field otherwise."""
        self._press(Qt.Key.Key_Minus, Qt.KeyboardModifier.NoModifier, self.field)
        self.zoom_out.assert_not_called()
        self._press(Qt.Key.Key_Minus, Qt.KeyboardModifier.NoModifier, None)
        self.zoom_out.assert_called_once()

    def test_plus_and_equals_zoom_in_unless_typing(self) -> None:
        """Both the plus key, which needs Shift, and the equals key zoom in with no text field focused."""
        for key, modifiers in ((Qt.Key.Key_Plus, Qt.KeyboardModifier.ShiftModifier),
                               (Qt.Key.Key_Equal, Qt.KeyboardModifier.NoModifier)):
            with self.subTest(key=key):
                self.zoom_in.reset_mock()
                self._press(key, modifiers, self.field)
                self.zoom_in.assert_not_called()
                self._press(key, modifiers, None)
                self.zoom_in.assert_called_once()


class HotkeyFilterHeldKeyTest(IntraPaintTestCase):
    """Tests tracking of a key that is held down, as the pan key is."""

    def setUp(self) -> None:
        super().setUp()
        self.changes: list[bool] = []
        self.filter = HotkeyFilter.instance()
        self.filter.register_held_key('held_key_test', self.changes.append, KeyConfig.PAN_VIEW_KEY)
        self.widget = QWidget()
        self.widget.winId()  # Creates the QWindow.
        window = self.widget.windowHandle()
        assert window is not None
        self.window = window
        self.filter.watch_window(window)

    def tearDown(self) -> None:
        self.filter.remove_keybinding('held_key_test')
        super().tearDown()

    def _send(self, event_type: QEvent.Type, auto_repeat: bool = False) -> None:
        QApplication.sendEvent(self.window, QKeyEvent(event_type, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier,
                                                      '', auto_repeat))

    def test_press_and_release_report_the_hold(self) -> None:
        """The hold starts at the press and ends at the release, and key repeats change nothing."""
        self._send(QEvent.Type.KeyPress)
        self._send(QEvent.Type.KeyPress, auto_repeat=True)
        self._send(QEvent.Type.KeyRelease, auto_repeat=True)
        self.assertEqual([True], self.changes)
        self._send(QEvent.Type.KeyRelease)
        self.assertEqual([True, False], self.changes)

    def test_focused_text_field_keeps_the_key(self) -> None:
        """Space typed into a text field doesn't start a hold."""
        field = QLineEdit(self.widget)
        self.widget.show()
        with patch.object(QApplication, 'focusWidget', new=staticmethod(lambda: field)):
            self._send(QEvent.Type.KeyPress)
        self.assertEqual([], self.changes)

    def test_losing_window_focus_ends_the_hold(self) -> None:
        """A key that is released in another window can't leave the hold stuck."""
        self._send(QEvent.Type.KeyPress)
        self.filter.watch_window(None)
        self.assertEqual([True, False], self.changes)

    def test_removing_the_binding_ends_the_hold(self) -> None:
        """Removing the binding releases the key."""
        self._send(QEvent.Type.KeyPress)
        self.filter.remove_keybinding('held_key_test')
        self.assertEqual([True, False], self.changes)
        self._send(QEvent.Type.KeyPress)
        self.assertEqual([True, False], self.changes)

    def test_key_is_not_consumed(self) -> None:
        """The press still reaches other handlers, such as a focused button."""
        press = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
        self.assertFalse(self.filter.eventFilter(self.window, press))
        self.assertEqual([True], self.changes)


class HotkeyFilterConfigRebindTest(IntraPaintTestCase):
    """Tests that config keybindings follow their config key only while registered."""

    def setUp(self) -> None:
        super().setUp()
        self.filter = HotkeyFilter.instance()

    def tearDown(self) -> None:
        self.filter.remove_keybinding('rebind_test')
        super().tearDown()

    def _bindings_for_id(self) -> list[HotkeyFilter.KeyBinding]:
        return [binding for bindings in self.filter._bindings.values()  # pylint: disable=protected-access
                for binding in bindings if binding.str_id == 'rebind_test']

    def test_removed_keybinding_stays_removed(self) -> None:
        """Changing a config key doesn't bring back a binding removed under its ID."""
        self.filter.register_config_keybinding('rebind_test', MagicMock(), KeyConfig.ERASER_TOOL_KEY)
        self.filter.remove_keybinding('rebind_test')
        KeyConfig().set(KeyConfig.ERASER_TOOL_KEY, 'Ctrl+F9')
        self.assertEqual([], self._bindings_for_id())

    def test_removed_held_key_stays_removed(self) -> None:
        """Changing a config key doesn't bring back a held-key binding removed under its ID."""
        self.filter.register_held_key('rebind_test', MagicMock(), KeyConfig.PAN_VIEW_KEY)
        self.filter.remove_keybinding('rebind_test')
        KeyConfig().set(KeyConfig.PAN_VIEW_KEY, 'Ctrl+F9')
        self.assertEqual([], [b for b in self.filter._held_bindings  # pylint: disable=protected-access
                              if b.str_id == 'rebind_test'])

    def test_registered_keybinding_follows_key_change(self) -> None:
        """A binding that wasn't removed is re-registered under the new key."""
        self.filter.register_config_keybinding('rebind_test', MagicMock(), KeyConfig.ERASER_TOOL_KEY)
        KeyConfig().set(KeyConfig.ERASER_TOOL_KEY, 'Ctrl+F9')
        matches = self._bindings_for_id()
        self.assertEqual(1, len(matches))
        self.assertEqual(Qt.Key.Key_F9, matches[0].key)
