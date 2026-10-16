"""The dock context menu, and the moves it offers for main window docks.

- The menu names its targets: another tab group to join, or a window edge. Directions relative to a dock are not
  offered, because the nested dock layout gives them no single meaning.
- A moved dock opens. "Move all panels to edge" keeps closed docks closed.
- Docks are shown while they are placed, and every move ends with `_settle`, which hides the tab bars Qt leaves
  drawn over the window. `_settle` relies on `MainWindow` putting tabs above docks.
"""
import logging
from enum import Enum
from typing import Optional

from PySide6.QtCore import Qt, QRect
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QTabBar, QWidget

from src.ui.window.dock_state import move_dock_to_area_start, restore_state_without_stale_tab_bars
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


def _is_open(dock: PanelDock) -> bool:
    return dock.is_available and not dock.isHidden()


def tab_groups(window: QMainWindow, docks: list[PanelDock]) -> list[list[PanelDock]]:
    """Returns the docked tab groups among the open docks, each with its front dock first. Floating docks are left
    out."""
    groups: list[list[PanelDock]] = []
    grouped: set[str] = set()
    for dock in docks:
        if not _is_open(dock) or dock.isFloating() or dock.objectName() in grouped:
            continue
        group = [dock] + [other for other in window.tabifiedDockWidgets(dock)
                          if isinstance(other, PanelDock) and _is_open(other)]
        grouped.update(member.objectName() for member in group)
        group.sort(key=lambda member: not member.is_showing)
        groups.append(group)
    return groups


def group_label(group: list[PanelDock]) -> str:
    """Returns a tab group's menu label: its front dock's title, with a count of the others."""
    if len(group) == 1:
        return group[0].windowTitle()
    return GROUP_LABEL.format(front_title=group[0].windowTitle(), count=len(group) - 1)


def _settle(window: QMainWindow) -> None:
    """Hides the tab bars a move left drawn over the window.

    A tab group whose open docks all moved away keeps its closed docks, and Qt keeps drawing that group's last tab bar
    until the group shows a dock again. A bar is kept only where it sits on top of the front dock of a docked group and
    lists that group's open docks.
    """
    layout = window.layout()
    if layout is not None:
        layout.activate()
    docks = window.findChildren(PanelDock, options=Qt.FindChildOption.FindDirectChildrenOnly)
    live: list[tuple[QRect, set[str]]] = []
    for group in tab_groups(window, docks):
        if len(group) > 1 and group[0].isVisible():
            live.append((group[0].geometry(), {dock.windowTitle() for dock in group}))
    for tab_bar in window.findChildren(QTabBar, options=Qt.FindChildOption.FindDirectChildrenOnly):
        if tab_bar.isHidden():
            continue
        bounds = tab_bar.geometry()
        titles = {tab_bar.tabText(i) for i in range(tab_bar.count())}
        if not any(dock_bounds.top() == bounds.bottom() + 1 and dock_bounds.left() == bounds.left()
                   and titles == group_titles for dock_bounds, group_titles in live):
            tab_bar.hide()


def _show_for_placement(dock: PanelDock) -> None:
    dock.setFloating(False)
    dock.show()


def tab_with(window: QMainWindow, dock: PanelDock, target: PanelDock) -> None:
    """Moves a dock into a docked target's tab group, in front."""
    _show_for_placement(dock)
    window.tabifyDockWidget(target, dock)
    dock.show()
    _settle(window)
    dock.raise_()


def move_to_edge(window: QMainWindow, dock: PanelDock, edge: DockEdge) -> None:
    """Moves a dock into a new strip running the full length of a window edge, outside every other strip there: a
    column for Left and Right, a row for Top and Bottom."""
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
            restore_state_without_stale_tab_bars(window, reordered)
    _settle(window)
    dock.raise_()


def move_all_to_edge(window: QMainWindow, docks: list[PanelDock], edge: DockEdge) -> None:
    """Moves every dock with content into one tab group along a window edge. The dock in front of the first open
    group stays in front, and closed docks stay closed."""
    docks = [dock for dock in docks if dock.is_available]
    if len(docks) == 0:
        return
    hidden = [dock for dock in docks if dock.isHidden()]
    front = next((dock for dock in docks if dock.is_showing), docks[0])
    leader = docks[0]
    move_to_edge(window, leader, edge)
    for dock in docks[1:]:
        _show_for_placement(dock)
        window.tabifyDockWidget(leader, dock)
        dock.show()
    for dock in hidden:
        dock.hide()
    _settle(window)
    front.raise_()


def add_move_all_actions(menu: QMenu, window: QMainWindow, docks: list[PanelDock]) -> None:
    """Fills a menu with one "move every panel to this edge" action per window edge."""
    for edge in DockEdge:
        action = menu.addAction(edge_title(edge))
        action.triggered.connect(lambda _checked=False, e=edge: move_all_to_edge(window, docks, e))


def build_dock_menu(window: QMainWindow, dock: PanelDock, docks: list[PanelDock],
                    parent: Optional[QWidget] = None) -> QMenu:
    """Builds the context menu for a dock's tab, title area or rail button.

    - "Tab with" lists every other docked tab group, and is disabled when there is none.
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
