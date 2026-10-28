"""Main window dock tab groups, which show one dock at a time with the edge rails as their tabs.

- Qt's own dock tab bars are never drawn (`hide_dock_tab_bars`). QMainWindow shows each group's bar again after every
  layout pass, so each bar is kept visible at zero size: showing it changes no geometry, and the window's layout
  settles instead of relaying out forever.
- Qt reserves room for a group's tab bar while two of its docks are open, so a group keeps one dock open
  (`PanelDock.open_in_group`). A restored layout can have more, so restores end with `close_background_docks`.
- `QMainWindow.tabifiedDockWidgets` leaves out closed docks, so groups are read from the saved layout.
"""
from typing import Optional

from PySide6.QtCore import QChildEvent, QEvent, QObject, Qt
from PySide6.QtWidgets import QMainWindow, QSizePolicy, QTabBar

from src.ui.window.dock_state import read_dock_groups
from src.ui.window.panel_dock import PanelDock


class _TabBarZeroer(QObject):
    """Keeps each dock tab bar of the main window it filters out of the layout.

    Hiding a tab bar makes `QMainWindowLayout` lay the window out again, and the layout shows the bar again, so the
    window never settles. A bar kept visible at zero size and an ignored size policy takes no space, and showing it
    changes no geometry.
    """

    def watch(self, tab_bar: QTabBar) -> None:
        """Sizes a tab bar out of the window, so it takes no space now and whenever Qt shows it again."""
        tab_bar.setMaximumSize(0, 0)
        tab_bar.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

    def eventFilter(self, _watched: QObject, event: QEvent) -> bool:  # pylint: disable=invalid-name
        """Sizes out each tab bar the window gains."""
        child = event.child() if isinstance(event, QChildEvent) else None
        if event.type() == QEvent.Type.ChildPolished and isinstance(child, QTabBar):
            self.watch(child)
        return False


def hide_dock_tab_bars(window: QMainWindow) -> None:
    """Keeps every dock tab bar of a main window out of the layout, including bars Qt creates later."""
    zeroer = _TabBarZeroer(window)
    for tab_bar in window.findChildren(QTabBar, options=Qt.FindChildOption.FindDirectChildrenOnly):
        zeroer.watch(tab_bar)
    window.installEventFilter(zeroer)


def _by_name(docks: list[PanelDock]) -> dict[str, PanelDock]:
    return {dock.objectName(): dock for dock in docks}


def docked_groups(window: QMainWindow, docks: list[PanelDock], with_empty: bool = False) -> list[list[PanelDock]]:
    """Returns the docked tab groups among `docks` that hold a dock with content, in layout order.

    Each group lists its docks with content in tab order, and with `with_empty` its docks without content too. A dock
    alone in its place is a group of one. Floating docks are left out.
    """
    groups = read_dock_groups(window.saveState().data())
    by_name = _by_name(docks)
    result: list[list[PanelDock]] = []
    for group in groups or []:
        members = [by_name.get(saved.name) for saved in group.docks]
        docked = [dock for dock in members if dock is not None and not dock.isFloating()]
        if any(dock.is_available for dock in docked):
            result.append(docked if with_empty else [dock for dock in docked if dock.is_available])
    return result


def tab_groups(window: QMainWindow, docks: list[PanelDock]) -> list[list[PanelDock]]:
    """Returns `docked_groups`, with each group's open dock moved to the front."""
    groups = docked_groups(window, docks)
    for group in groups:
        group.sort(key=lambda dock: dock.isHidden())
    return groups


def _is_open(dock: PanelDock) -> bool:
    """Returns whether a dock is open, or is empty and opens once content arrives."""
    return not dock.isHidden() if dock.is_available else dock.open_when_available


def close_background_docks(window: QMainWindow, docks: list[PanelDock], state: Optional[bytes] = None) -> None:
    """Closes every open dock among `docks` that isn't in front of its tab group, so each group has one open dock.

    An empty dock that opens once content arrives counts as open. A group keeps the dock in front in `state`, a saved
    layout that defaults to the current one, or its first open dock if that one is closed. After a restore, pass the
    restored layout: hiding its empty docks moves Qt's front tab.
    """
    groups = read_dock_groups(state if state is not None else window.saveState().data())
    by_name = _by_name(docks)
    for group in groups or []:
        members = [by_name.get(saved.name) for saved in group.docks]
        open_docks = [dock for dock in members if dock is not None and _is_open(dock) and not dock.isFloating()]
        if len(open_docks) < 2:
            continue
        front: Optional[PanelDock] = members[group.current] if group.current >= 0 else None
        if front not in open_docks:
            front = open_docks[0]
        for dock in open_docks:
            if dock is not front:
                dock.set_open(False)
