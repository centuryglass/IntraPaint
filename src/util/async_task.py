"""Perform an async task in another thread."""
from typing import Callable, TypeAlias, List

from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool

from src.util.application_state import AppStateTracker, APP_STATE_LOADING

ThreadAction: TypeAlias = Callable[..., None]


class AsyncTask(QObject):
    """Run an async task in another thread."""
    finish_signal = Signal()

    def __init__(self, action: ThreadAction, set_loading_state: bool = False) -> None:
        super().__init__()
        self._action = action
        if set_loading_state:
            AppStateTracker.set_app_state(APP_STATE_LOADING)

    def signals(self) -> List[Signal]:
        """Return a list of Qt signals that will be passed to the worker."""
        return []

    def start(self):
        """Start the thread, caching the AsyncTask to prevent deletion."""
        task = self

        class _TaskRunner(QRunnable):
            def run(self):
                """Start the AsyncTask within the global thread pool."""
                task.run()
        QThreadPool.globalInstance().start(_TaskRunner())

    def run(self) -> None:
        """Run the action, passing in available signals and sending a finish signal on exit."""
        self._action(*self.signals())
        self.finish_signal.emit()
