"""The dock context menu, and the moves it offers for main window docks.

- The menu names its targets: another tab group to join, or a window edge. Directions relative to a dock are not
  offered, because the nested dock layout gives them no single meaning.
- A moved dock opens in front of its group. "Move all panels to edge" keeps the first open dock open and closes the
  rest, since a group shows one dock at a time (see `src.ui.window.dock_groups`).
- Moves run inside `PanelDock.placing_docks`, so docking a floating dock along the way closes nothing.
"""
import logging
from enum import Enum
from typing import Optional

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QWidget

from src.ui.window.dock_groups import tab_groups
from src.ui.window.dock_state import move_dock_to_area_start
from src.ui.window.panel_dock import PanelDock

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.window.dock_menu'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


MENU_TAB_WITH = _tr('Tab with')
MENU_MOVE_TO_EDGE = _tr('Move to edge')
MENU_MOVE_ALL_TO_EDGE = _tr('Move all panels to edge')
MENU_FLOAT = _tr('Float')
MENU_DOCK = _tr('Dock')
MENU_HIDE_PANEL = _tr('Hide panel')
# A tab group's menu label: its front panel, and how many other panels are tabbed with it.
GROUP_LABEL = _tr('{front_title} (+{count})')


class DockEdge(Enum):
    """A window edge a dock can be moved to, as its dock area."""
    LEFT = Qt.DockWidgetArea.LeftDockWidgetArea
    RIGHT = Qt.DockWidgetArea.RightDockWidgetArea
    TOP = Qt.DockWidgetArea.TopDockWidgetArea
    BOTTOM = Qt.DockWidgetArea.BottomDockWidgetArea


_EDGE_TITLES = {
    DockEdge.LEFT: _tr('Left'),
    DockEdge.RIGHT: _tr('Right'),
    DockEdge.TOP: _tr('Top'),
    DockEdge.BOTTOM: _tr('Bottom')
}


def edge_title(edge: DockEdge) -> str:
    """Returns the translated name shown for a window edge."""
    return _EDGE_TITLES[edge]


def group_label(group: list[PanelDock]) -> str:
    """Returns a tab group's menu label: its front dock's title, with a count of the others."""
    if len(group) == 1:
        return group[0].windowTitle()
    return GROUP_LABEL.format(front_title=group[0].windowTitle(), count=len(group) - 1)


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


def add_move_all_actions(menu: QMenu, window: QMainWindow, docks: list[PanelDock]) -> None:
    """Fills a menu with one "move every panel to this edge" action per window edge."""
    for edge in DockEdge:
        action = menu.addAction(edge_title(edge))
        action.triggered.connect(lambda _checked=False, e=edge: move_all_to_edge(window, docks, e))


def build_dock_menu(window: QMainWindow, dock: PanelDock, docks: list[PanelDock],
                    parent: Optional[QWidget] = None) -> QMenu:
    """Builds the context menu for a dock's title area or rail button.

    - "Tab with" lists every other docked tab group, open or closed, and is disabled when there is none.
    - "Move to edge" has one entry per window edge.
    - "Float" or "Dock" toggles floating.
    - "Hide panel" closes the dock, and is left out while it is closed.
    - "Move all panels to edge" moves every dock with content.
    """
    menu = QMenu(parent if parent is not None else window)
    tab_menu = menu.addMenu(MENU_TAB_WITH)
    for group in tab_groups(window, docks):
        if dock in group:
            continue
        target = group[0]
        action = tab_menu.addAction(group_label(group))
        action.triggered.connect(lambda _checked=False, t=target: tab_with(window, dock, t))
    tab_menu.setEnabled(not tab_menu.isEmpty())

    edge_menu = menu.addMenu(MENU_MOVE_TO_EDGE)
    for edge in DockEdge:
        action = edge_menu.addAction(edge_title(edge))
        action.triggered.connect(lambda _checked=False, e=edge: move_to_edge(window, dock, e))

    if dock.isFloating():
        menu.addAction(MENU_DOCK).triggered.connect(lambda _checked=False: dock.setFloating(False))
    else:
        def _float() -> None:
            dock.show()
            dock.setFloating(True)
        menu.addAction(MENU_FLOAT).triggered.connect(lambda _checked=False: _float())
    if not dock.isHidden():
        menu.addAction(MENU_HIDE_PANEL).triggered.connect(lambda _checked=False: dock.hide())
    menu.addSeparator()
    add_move_all_actions(menu.addMenu(MENU_MOVE_ALL_TO_EDGE), window, docks)
    return menu
