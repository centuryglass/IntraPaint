"""Main window dock tab groups, which show one dock at a time with the edge rails as their tabs.

- Qt's own dock tab bars are never drawn (`hide_dock_tab_bars`). Qt shows each group's bar again after every layout
  pass, so a filter hides it each time.
- Qt reserves room for a group's tab bar while two of its docks are open, so a group keeps one dock open
  (`PanelDock.open_in_group`). A restored layout can have more, so restores end with `close_background_docks`.
- `QMainWindow.tabifiedDockWidgets` leaves out closed docks, so groups are read from the saved layout.
"""
from typing import Optional

from PySide6.QtCore import QChildEvent, QEvent, QObject, Qt
from PySide6.QtWidgets import QMainWindow, QTabBar

from src.ui.window.dock_state import read_dock_groups
from src.ui.window.panel_dock import PanelDock


class _TabBarHider(QObject):
    """Hides each dock tab bar of the main window it filters, whenever Qt shows it."""

    def watch(self, tab_bar: QTabBar) -> None:
        """Hides a tab bar now and whenever it is shown."""
        tab_bar.installEventFilter(self)
        tab_bar.hide()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # pylint: disable=invalid-name
        """Watches each tab bar the window gains, and hides watched tab bars as they show."""
        child = event.child() if isinstance(event, QChildEvent) else None
        if event.type() == QEvent.Type.ChildPolished and isinstance(child, QTabBar):
            self.watch(child)
        elif event.type() == QEvent.Type.Show and isinstance(watched, QTabBar):
            watched.hide()
        return False


def hide_dock_tab_bars(window: QMainWindow) -> None:
    """Keeps every dock tab bar of a main window hidden, including bars Qt creates later."""
    hider = _TabBarHider(window)
    for tab_bar in window.findChildren(QTabBar, options=Qt.FindChildOption.FindDirectChildrenOnly):
        hider.watch(tab_bar)
    window.installEventFilter(hider)


def _by_name(docks: list[PanelDock]) -> dict[str, PanelDock]:
    return {dock.objectName(): dock for dock in docks}


def tab_groups(window: QMainWindow, docks: list[PanelDock]) -> list[list[PanelDock]]:
    """Returns the docked tab groups among `docks` that hold a dock with content, in layout order.

    Each group lists its docks with content in tab order, with its open dock moved to the front. A dock alone in its
    place is a group of one. Floating docks are left out.
    """
    groups = read_dock_groups(window.saveState().data())
    by_name = _by_name(docks)
    result: list[list[PanelDock]] = []
    for group in groups or []:
        members = [by_name.get(saved.name) for saved in group.docks]
        available = [dock for dock in members if dock is not None and dock.is_available and not dock.isFloating()]
        if len(available) == 0:
            continue
        available.sort(key=lambda dock: dock.isHidden())
        result.append(available)
    return result


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
