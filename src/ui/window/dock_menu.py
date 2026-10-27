"""The dock context menu, which offers the moves in `src.ui.window.dock_placement`.

- The menu names its targets: a tab group to join or split beside, or a window edge. Directions relative to the dock
  itself are not offered, because the nested dock layout gives them no single meaning.
- "Move all panels to edge" keeps the first open dock open and closes the rest, since a group shows one dock at a time
  (see `src.ui.window.dock_groups`).
"""
from typing import Optional

from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QWidget

from src.ui.window.dock_groups import tab_groups
from src.ui.window.dock_placement import DockEdge, SplitSide, move_all_to_edge, move_to_edge, split_beside, tab_with
from src.ui.window.panel_dock import PanelDock

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.window.dock_menu'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


MENU_TAB_WITH = _tr('Tab with')
MENU_SPLIT_BESIDE = _tr('Split beside')
MENU_MOVE_TO_EDGE = _tr('Move to edge')
MENU_MOVE_ALL_TO_EDGE = _tr('Move all panels to edge')
MENU_FLOAT = _tr('Float')
MENU_DOCK = _tr('Dock')
MENU_HIDE_PANEL = _tr('Hide panel')
# A tab group's menu label: its front panel, and how many other panels are tabbed with it.
GROUP_LABEL = _tr('{front_title} (+{count})')


_EDGE_TITLES = {
    DockEdge.LEFT: _tr('Left'),
    DockEdge.RIGHT: _tr('Right'),
    DockEdge.TOP: _tr('Top'),
    DockEdge.BOTTOM: _tr('Bottom')
}


def edge_title(edge: DockEdge) -> str:
    """Returns the translated name shown for a window edge."""
    return _EDGE_TITLES[edge]


_SIDE_TITLES = {
    SplitSide.LEFT: _tr('Left'),
    SplitSide.RIGHT: _tr('Right'),
    SplitSide.ABOVE: _tr('Above'),
    SplitSide.BELOW: _tr('Below')
}


def side_title(side: SplitSide) -> str:
    """Returns the translated name shown for a side of a tab group."""
    return _SIDE_TITLES[side]


def group_label(group: list[PanelDock]) -> str:
    """Returns a tab group's menu label: its front dock's title, with a count of the others."""
    if len(group) == 1:
        return group[0].windowTitle()
    return GROUP_LABEL.format(front_title=group[0].windowTitle(), count=len(group) - 1)


def add_move_all_actions(menu: QMenu, window: QMainWindow, docks: list[PanelDock]) -> None:
    """Fills a menu with one "move every panel to this edge" action per window edge."""
    for edge in DockEdge:
        action = menu.addAction(edge_title(edge))
        action.triggered.connect(lambda _checked=False, e=edge: move_all_to_edge(window, docks, e))


def build_dock_menu(window: QMainWindow, dock: PanelDock, docks: list[PanelDock],
                    parent: Optional[QWidget] = None) -> QMenu:
    """Builds the context menu for a dock's title area or rail button.

    - "Tab with" lists every other docked tab group, open or closed, and is disabled when there is none.
    - "Split beside" lists the same groups, plus the dock's own group while it holds another dock with content, each
      with one entry per side. It is disabled when there is none.
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

    split_menu = menu.addMenu(MENU_SPLIT_BESIDE)
    for group in tab_groups(window, docks):
        others = [member for member in group if member is not dock]
        if len(others) == 0:
            continue
        side_menu = split_menu.addMenu(group_label(group))
        for side in SplitSide:
            action = side_menu.addAction(side_title(side))
            action.triggered.connect(lambda _checked=False, t=others[0], s=side: split_beside(window, dock, t, s))
    split_menu.setEnabled(not split_menu.isEmpty())

    edge_menu = menu.addMenu(MENU_MOVE_TO_EDGE)
    for edge in DockEdge:
        action = edge_menu.addAction(edge_title(edge))
        action.triggered.connect(lambda _checked=False, e=edge: move_to_edge(window, dock, e))

    if dock.isFloating():
        menu.addAction(MENU_DOCK).triggered.connect(lambda _checked=False: dock.setFloating(False))
    else:
        def _float() -> None:
            if dock.isHidden():
                dock.show()
            else:
                dock.open_next_in_group()
            dock.setFloating(True)
        menu.addAction(MENU_FLOAT).triggered.connect(lambda _checked=False: _float())
    if not dock.isHidden():
        menu.addAction(MENU_HIDE_PANEL).triggered.connect(lambda _checked=False: dock.hide())
    menu.addSeparator()
    add_move_all_actions(menu.addMenu(MENU_MOVE_ALL_TO_EDGE), window, docks)
    return menu
