"""Tests which key presses HotkeyFilter sees."""
from unittest.mock import MagicMock

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QGuiApplication, QKeyEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QWidget

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
