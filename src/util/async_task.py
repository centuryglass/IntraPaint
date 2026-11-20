"""Perform an async task in another thread."""
from typing import Callable, TypeAlias

from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, SignalInstance

from src.util.application_state import AppStateTracker, APP_STATE_LOADING
from src.util.main_thread import assert_main_thread

ThreadAction: TypeAlias = Callable[..., None]


class _TaskRunner(QRunnable):
    """Runs an AsyncTask in the global thread pool.

    Defined at module level: a class created inside `AsyncTask.start` is a reference cycle that keeps the task alive.
    """

    def __init__(self, task: 'AsyncTask') -> None:
        super().__init__()
        self._task = task

    def run(self) -> None:
        """Run the AsyncTask on the pool's thread."""
        self._task.run()


class AsyncTask(QObject):
    """Run an async task in another thread.

    Must be constructed on the main thread; __init__ raises RuntimeError otherwise. Closures connected to its signals
    run on the main thread only because the AsyncTask object lives there.
    """
    finish_signal = Signal()

    def __init__(self, action: ThreadAction, set_loading_state: bool = False) -> None:
        assert_main_thread('AsyncTask construction')
        super().__init__()
        self._action = action
        if QThreadPool.globalInstance().maxThreadCount() < 3:
            QThreadPool.globalInstance().setMaxThreadCount(3)
        if set_loading_state:
            AppStateTracker.set_app_state(APP_STATE_LOADING)

    def signals(self) -> list[SignalInstance]:
        """Return a list of Qt signals that will be passed to the worker."""
        return []

    def start(self):
        """Start the thread, caching the AsyncTask to prevent deletion."""
        QThreadPool.globalInstance().start(_TaskRunner(self))

    def run(self) -> None:
        """Run the action, passing in available signals and sending a finish signal on exit."""
        self._action(*self.signals())
        self.finish_signal.emit()
