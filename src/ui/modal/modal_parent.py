"""Chooses the parent for modal dialogs, so the window manager keeps them above the windows they block.

A modal dialog without a parent has no transient link to the main window. The main window then blocks input but can
still be raised over the dialog, which hides the only window that can respond.
"""
from typing import Optional

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget


def modal_parent(parent: Optional[QWidget] = None) -> Optional[QWidget]:
    """Returns `parent` if set, or else the window a new modal dialog should sit above.

    That is the topmost open modal (so a dialog opened from a dialog stacks over it), then the active window, then
    any visible main window. It returns None only when no such window exists, such as before the main window shows.
    """
    if parent is not None:
        return parent
    active_modal = QApplication.activeModalWidget()
    if active_modal is not None:
        return active_modal
    active_window = QApplication.activeWindow()
    if active_window is not None:
        return active_window
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QMainWindow) and widget.isVisible():
            return widget
    return None
