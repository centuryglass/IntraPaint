"""Coordinate the current application state, mostly for enabling/disabling components that should only be active
   in particular states."""
from typing import List

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QWidget, QAction

from src.util.singleton import Singleton

# Valid tracked application states:

# Initial loading, login, server connection, etc.:
APP_STATE_INIT = 'init'

# Ready for use, but no image is open:
APP_STATE_NO_IMAGE = 'no image'

# Active image editing in progress:
APP_STATE_EDITING = 'editing'

# Some ongoing process is blocking input:
APP_STATE_LOADING = 'loading'

# Picking between generated images:
APP_STATE_SELECTION = 'selection'

APP_STATE_ALL = [APP_STATE_INIT, APP_STATE_NO_IMAGE, APP_STATE_EDITING, APP_STATE_LOADING, APP_STATE_SELECTION]
APP_STATE_NOT_LOADING = [APP_STATE_INIT, APP_STATE_NO_IMAGE, APP_STATE_EDITING, APP_STATE_SELECTION]


class AppStateTracker(metaclass=Singleton):
    """Singleton QObject that tracks the current application state and sends signals on state change."""

    def __init__(self):

        class _InnerQObject(QObject):
            state_changed = pyqtSignal(str)
        self._signal_object = _InnerQObject()
        self._state_changed = self._signal_object.state_changed
        self._app_state = APP_STATE_INIT

    @staticmethod
    def set_app_state(new_state: str) -> None:
        """Updates the current application state."""
        if new_state == AppStateTracker.app_state():
            return
        AppStateTracker()._set_app_state(new_state)

    @staticmethod
    def app_state() -> str:
        """Returns the current application state."""
        return AppStateTracker()._app_state

    @staticmethod
    def set_enabled_states(widget: QWidget | QAction, valid_states: List[str]) -> None:
        """Configures a widget or action to automatically enable or disable itself based on application state."""
        assert isinstance(valid_states, list), f'Invalid state list {valid_states}'

        def _change_enabled_status(app_state: str, connected_widget=widget, state_list=None) -> None:
            if state_list is None:
                state_list = valid_states
            connected_widget.setEnabled(app_state in state_list)
        AppStateTracker.signal().connect(_change_enabled_status)
        _change_enabled_status(AppStateTracker.app_state())

    @staticmethod
    def signal() -> pyqtSignal:
        """Accesses the state change signal."""
        return AppStateTracker()._state_changed

    def _set_app_state(self, new_state: str) -> None:
        if new_state not in APP_STATE_ALL:
            raise RuntimeError(f'Invalid application state {new_state}')
        if new_state != self._app_state:
            self._app_state = new_state
            self._state_changed.emit(new_state)
