"""Implements Qt signal blocking as a contextmanager."""
from contextlib import contextmanager
from typing import Generator

from PySide6.QtCore import QObject


@contextmanager
def signals_blocked(signal_source: QObject) -> Generator[None, None, None]:
    """Implements Qt signal blocking as a contextmanager."""
    signal_source.blockSignals(True)
    try:
        yield
    finally:
        signal_source.blockSignals(False)
