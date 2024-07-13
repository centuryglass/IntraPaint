"""Perform an async task in another thread."""
from threading import Lock
from typing import Callable, TypeAlias, Optional, List

from PyQt6.QtCore import QObject, pyqtSignal, QThread

from src.util.application_state import AppStateTracker, APP_STATE_LOADING

ThreadAction: TypeAlias = Callable[..., None]


class AsyncTask(QObject):
    """Run an async task in another thread."""

    active_threads: List['AsyncTask'] = []
    lock = Lock()
    finish_signal = pyqtSignal()

    def __init__(self, action: ThreadAction, set_loading_state: bool = False) -> None:
        super().__init__()
        self._thread: Optional[QThread] = None
        self._action = action
        with AsyncTask.lock:
            AsyncTask.active_threads.append(self)
        self._thread = QThread()
        self.moveToThread(self._thread)
        if set_loading_state:
            AppStateTracker.set_app_state(APP_STATE_LOADING)

    def signals(self) -> List[pyqtSignal]:
        """Return a list of Qt signals that will be passed to the worker."""
        return []

    def start(self):
        """Start the thread, caching the AsyncTask to prevent deletion."""
        assert self._thread is not None
        self._thread.finished.connect(self._cleanup)
        self._thread.started.connect(self._run)
        self._thread.start()

    def _run(self) -> None:
        self._action(*self.signals())
        self.finish_signal.emit()

    def _cleanup(self) -> None:
        assert self._thread is not None and self._thread.isFinished()
        self._thread.deleteLater()
        self._thread = None
        with AsyncTask.lock:
            AsyncTask.active_threads.remove(self)
            self.deleteLater()
