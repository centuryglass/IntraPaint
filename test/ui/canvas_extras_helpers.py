"""Helpers for tests that hide canvas extras categories through hide mode, the only way they hide."""
from PySide6.QtCore import QEvent, QPointF
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QApplication, QWidget

from src.ui.canvas_extras import CanvasExtraCategory, CanvasExtras


def move_cursor_over(view: QWidget, over: bool) -> None:
    """Sends a view the enter or leave event the cursor would."""
    if over:
        QApplication.sendEvent(view, QEnterEvent(QPointF(1, 1), QPointF(1, 1), QPointF(1, 1)))
    else:
        QApplication.sendEvent(view, QEvent(QEvent.Type.Leave))


def hide_category(extras: CanvasExtras, view: QWidget, category: CanvasExtraCategory) -> None:
    """Hides one category through hide mode, with the cursor over `view` and every other category needed. `view` is
    the widget `extras` watches."""
    move_cursor_over(view, True)
    extras.tool_categories = set(CanvasExtraCategory) - {category}
    extras.hide_mode = True
