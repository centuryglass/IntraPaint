"""Coordinates the current application state.

Mostly used for enabling and disabling components that should only be active in particular states.
"""
from typing import Any
import logging

from PySide6.QtCore import QObject, Signal, SignalInstance, SIGNAL
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget

from src.app_context import AppService

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

logger = logging.getLogger(__name__)

class AppStateTracker(metaclass=AppService):
    """Global service that tracks the current application state and sends signals on state change.

    `AppController` reads the `AppStateTracker()` accessor once and passes the instance on. Other code under `src/`
    receives it through a constructor, or reads `ImageStack.app_state` from the stack it works on.
    """

    def __init__(self) -> None:

        class _InnerQObject(QObject):
            state_changed = Signal(str)
        self._signal_object = _InnerQObject()
        self._state_changed = self._signal_object.state_changed
        self._app_state = APP_STATE_INIT
        self._connections: dict[QWidget | QAction, Any] = {}

    def set_app_state(self, new_state: str) -> None:
        """Updates the current application state, emitting `state_changed` if it changed."""
        if new_state not in APP_STATE_ALL:
            raise RuntimeError(f'Invalid application state {new_state}')
        if new_state != self._app_state:
            logger.info(f'State change: from {self._app_state} to {new_state}')
            self._app_state = new_state
            self._state_changed.emit(new_state)

    def app_state(self) -> str:
        """Returns the current application state."""
        return self._app_state

    def set_enabled_states(self, widget: QWidget | QAction, valid_states: list[str]) -> None:
        """Configures a widget or action to automatically enable or disable itself based on application state."""
        assert isinstance(valid_states, list), f'Invalid state list {valid_states}'
        if widget in self._connections:
            self.disconnect_from_state(widget)

        def _change_enabled_status(app_state: str, connected_widget=widget, state_list=valid_states) -> None:
            connected_widget.setEnabled(app_state in state_list)
        self._connections[widget] = self._state_changed.connect(_change_enabled_status)
        _change_enabled_status(self._app_state)

    def disconnect_from_state(self, widget: QWidget | QAction) -> None:
        """Removes a widget or action that was previously connected to state change signals."""
        if widget in self._connections:
            self._state_changed.disconnect(self._connections[widget])
            del self._connections[widget]

    def signal(self) -> SignalInstance:
        """Accesses the state change signal."""
        return self._state_changed

    def close(self) -> None:
        """Disconnects every widget, action and slot connected to state changes. `AppContext.close` calls this.

        Connections keep their widgets alive for as long as anything still holds this tracker.
        """
        self._connections.clear()
        if self._signal_object.receivers(SIGNAL('state_changed(QString)')) > 0:
            self._state_changed.disconnect()
