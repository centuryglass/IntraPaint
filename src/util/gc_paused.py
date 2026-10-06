"""Pauses Python's cyclic garbage collector around Qt calls that walk every live widget.

QApplication.setStyle and QApplication.setStyleSheet copy the list of all widgets, then send each one events. Any
Python event handler they reach can trigger a cyclic collection, and a collection that frees a Python-owned widget
deletes it in C++ while it is still in Qt's copied list, so Qt then dereferences freed memory and usually segfaults.
"""
import gc
from contextlib import contextmanager
from typing import Generator


@contextmanager
def gc_paused() -> Generator[None, None, None]:
    """Collects garbage, then keeps the cyclic garbage collector disabled until the block exits.

    Collecting first frees unreachable widgets before Qt lists them. Objects whose reference count reaches zero are
    still freed inside the block.
    """
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()
