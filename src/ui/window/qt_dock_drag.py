"""Starts Qt's own dock drag for a docked `PanelDock` from code, for drags that begin on something other than Qt's title
bar: a rail button (`src.ui.window.rail_drag`) or the dock's corner notch (`src.ui.window.dock_notch`).

The dock opens with its title bar, and gets a synthetic press near the bar's left end and moves, as if that bar had been
dragged. Qt floats the dock with that point under the pointer and follows the mouse from there. This relies on Qt
starting a dock drag from mouse events sent to the title area, which `QDockWidget` doesn't document; if Qt doesn't start
one, the dock stays where it was.

The dock's tab group keeps showing a dock: a closed dock opens behind the group's open dock, and an open dock opens the
group's next dock behind it (`PanelDock.open_next_in_group`).
"""
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget


if TYPE_CHECKING:
    from src.ui.window.panel_dock import PanelDock

# Distance from a dock's left edge to the point a hand-off presses in its title bar:
TITLE_PRESS_INSET = 10
TITLE_PRESS_Y = 3


def _send_mouse(widget: QWidget, event_type: QEvent.Type, global_pos: QPoint, button: Qt.MouseButton) -> None:
    """Sends a widget a mouse event at a screen position, with the left button held."""
    QApplication.sendEvent(widget, QMouseEvent(event_type, QPointF(widget.mapFromGlobal(global_pos)),
                                               QPointF(global_pos), button, Qt.MouseButton.LeftButton,
                                               Qt.KeyboardModifier.NoModifier))


def start_qt_dock_drag(window: QMainWindow, dock: 'PanelDock', global_pos: QPoint) -> None:
    """Starts Qt's dock drag of a dock from its title bar, with the pointer at a screen position."""
    if dock.isHidden():
        dock.show()
    else:
        dock.open_next_in_group()
    dock.show_title_bar_for_drag()
    layout = window.layout()
    if layout is not None:
        layout.activate()
    press = QPoint(TITLE_PRESS_INSET, TITLE_PRESS_Y)
    # The first move passes Qt's drag distance to start the drag. The second puts the press point at the pointer:
    past_drag_distance = press + QPoint(QApplication.startDragDistance() + 1, QApplication.startDragDistance() + 1)
    _send_mouse(dock, QEvent.Type.MouseButtonPress, dock.mapToGlobal(press), Qt.MouseButton.LeftButton)
    _send_mouse(dock, QEvent.Type.MouseMove, dock.mapToGlobal(past_drag_distance), Qt.MouseButton.NoButton)
    # Mapped after the first move, which floats the dock:
    _send_mouse(dock, QEvent.Type.MouseMove, global_pos, Qt.MouseButton.NoButton)
    if not dock.isFloating():
        dock.restore_title_bar()
