"""Moves that place a main window dock: tab it with a group, split it beside a group, or move it to a window edge.

- The dock menu and dragging a rail button both place docks through these functions.
- A placed dock opens in front of its group. Moves run inside `PanelDock.placing_docks`, so docking a floating dock
  along the way closes nothing.
- `QMainWindow.splitDockWidget` tabs the new dock into the first dock's group when that dock is tabbed, and only
  places after. Splitting beside a group edits the saved layout instead (`split_dock_beside`).
"""
import logging
from enum import Enum

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtWidgets import QMainWindow

from src.ui.window.dock_state import move_dock_to_area_start, split_dock_beside
from src.ui.window.panel_dock import PanelDock

logger = logging.getLogger(__name__)


class DockEdge(Enum):
    """A window edge a dock can be moved to, as its dock area."""
    LEFT = Qt.DockWidgetArea.LeftDockWidgetArea
    RIGHT = Qt.DockWidgetArea.RightDockWidgetArea
    TOP = Qt.DockWidgetArea.TopDockWidgetArea
    BOTTOM = Qt.DockWidgetArea.BottomDockWidgetArea


class SplitSide(Enum):
    """A side of a tab group a dock can be split onto, as the split's orientation and whether the dock goes after."""
    LEFT = (Qt.Orientation.Horizontal, False)
    RIGHT = (Qt.Orientation.Horizontal, True)
    ABOVE = (Qt.Orientation.Vertical, False)
    BELOW = (Qt.Orientation.Vertical, True)


def _show_for_placement(dock: PanelDock) -> None:
    dock.setFloating(False)
    dock.show()


def tab_with(window: QMainWindow, dock: PanelDock, target: PanelDock) -> None:
    """Moves a dock into a docked target's tab group, open in front."""
    with PanelDock.placing_docks():
        _show_for_placement(dock)
        window.tabifyDockWidget(target, dock)
    dock.open_in_group()


def move_to_edge(window: QMainWindow, dock: PanelDock, edge: DockEdge) -> None:
    """Moves a dock into a new strip running the full length of a window edge, outside every other strip there: a
    column for Left and Right, a row for Top and Bottom."""
    with PanelDock.placing_docks():
        _show_for_placement(dock)
        across = Qt.Orientation.Horizontal if edge in (DockEdge.LEFT, DockEdge.RIGHT) else Qt.Orientation.Vertical
        window.addDockWidget(edge.value, dock, across)
        dock.show()
        if edge in (DockEdge.LEFT, DockEdge.TOP):
            # addDockWidget appends, which is the side nearest the canvas for Left and Top:
            reordered = move_dock_to_area_start(window.saveState().data(), edge.value, across, dock.objectName())
            if reordered is None:
                logger.warning(f'Could not move {dock.objectName()} to the outer side of its area')
            else:
                window.restoreState(QByteArray(reordered))


def move_all_to_edge(window: QMainWindow, docks: list[PanelDock], edge: DockEdge) -> None:
    """Moves every dock with content into one tab group along a window edge. The first open dock stays open in front,
    or the first dock if none is open, and the others close."""
    docks = [dock for dock in docks if dock.is_available]
    if len(docks) == 0:
        return
    front = next((dock for dock in docks if not dock.isHidden()), docks[0])
    leader = docks[0]
    move_to_edge(window, leader, edge)
    with PanelDock.placing_docks():
        for dock in docks[1:]:
            dock.setFloating(False)
            window.tabifyDockWidget(leader, dock)
    front.open_in_group()


def split_beside(window: QMainWindow, dock: PanelDock, target: PanelDock, side: SplitSide) -> bool:
    """Moves a dock into a group of its own on one side of the target's tab group, open, and gives the two equal
    shares of the group's old size. Returns whether it moved.

    The target's group keeps its other docks and its open dock. A dock split from its own group while open leaves the
    target open in its place, so the group doesn't collapse.
    """
    orientation, after = side.value
    leaves_own_group_empty = not dock.isHidden() and target in dock.group_mates()
    with PanelDock.placing_docks():
        dock.setFloating(False)
        state = split_dock_beside(window.saveState().data(), dock.objectName(), target.objectName(), orientation,
                                  after)
        if state is None:
            logger.warning(f'Could not split {dock.objectName()} beside {target.objectName()}')
            return False
        window.restoreState(QByteArray(state))
    dock.open_in_group()
    if leaves_own_group_empty:
        target.open_in_group()
    layout = window.layout()
    if layout is not None:
        layout.activate()
    front = next((mate for mate in [target, *target.group_mates()] if not mate.isHidden()), None)
    if front is not None:
        horizontal = orientation == Qt.Orientation.Horizontal
        total = sum(placed.width() if horizontal else placed.height() for placed in (front, dock))
        window.resizeDocks([front, dock], [total - total // 2, total // 2], orientation)
    return True
