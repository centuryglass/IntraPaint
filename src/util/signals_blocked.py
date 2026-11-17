"""Implements Qt signal blocking as a contextmanager."""
from contextlib import contextmanager
from typing import Generator

from PySide6.QtCore import QObject


@contextmanager
def signals_blocked(signal_source: QObject) -> Generator[None, None, None]:
    """Implements Qt signal blocking as a contextmanager.

    On exit, the source's signals return to the blocked state they had on entry, so nested blocks of one source
    leave it blocked until the outermost block exits."""
    was_blocked = signal_source.blockSignals(True)
    try:
        yield
    finally:
        signal_source.blockSignals(was_blocked)
