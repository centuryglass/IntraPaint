"""Returns a QMargins object that is equally spaced on all sides."""

from PyQt5.QtCore import QMargins

def get_equal_margins(size: int) -> QMargins:
    """Returns a QMargins object that is equally spaced on all sides."""
    return QMargins(size, size, size, size)
