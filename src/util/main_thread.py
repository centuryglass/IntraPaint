"""Helpers for the threading rule: model, config, undo and UI changes happen on the GUI thread.

Worker threads only produce data and hand it back through signals delivered on the main thread, or through
`run_on_main_thread`.
"""
import threading
from typing import Callable

from PySide6.QtCore import QThread, QTimer, QCoreApplication


def is_main_thread() -> bool:
    """Return whether the caller is on the GUI thread, or on Python's main thread if no Qt application exists."""
    app = QCoreApplication.instance()
    if app is None:
        return threading.current_thread() is threading.main_thread()
    return QThread.currentThread() is app.thread()


def assert_main_thread(description: str) -> None:
    """Raise RuntimeError if the caller is not on the GUI thread."""
    if not is_main_thread():
        raise RuntimeError(f'{description} must run on the main thread.')


def run_on_main_thread(fn: Callable[[], None]) -> None:
    """Run `fn` on the GUI thread from any thread, after control returns to the main event loop.

    Requires a running QApplication.
    """
    app = QCoreApplication.instance()
    assert app is not None, 'run_on_main_thread requires a QApplication'
    QTimer.singleShot(0, app, fn)
