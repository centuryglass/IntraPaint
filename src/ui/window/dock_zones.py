"""Named dock zones, and the menus that move main window docks between them.

- The zones are Top, Left, Right, "Bottom, upper row" and "Bottom, lower row". A dock's zone is read from its dock
  area and, in the bottom area, from where its tab group sits. A layout that fits no zone exactly counts as the nearest
  one: any bottom group with another group above it is in the lower row.
- Moving a dock into a zone that is empty creates it, and moving out the last dock removes it. Qt closes an empty
  split on its own.
- Docks are shown while they are placed and docks are moved without `removeDockWidget`. Qt leaves stale tab bars when
  tabifying hidden docks (see `MainWindow`).
- Side areas (Left, Right) stack tab groups vertically. The top-most group is the "upper group", and the others are
  "lower groups".
"""
from enum import StrEnum
from typing import Optional

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QWidget

from src.ui.window.panel_dock import PanelDock

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.window.dock_zones'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


MENU_MOVE_TO = _tr('Move to')
MENU_MOVE_ALL_TO = _tr('Move all tabs to')
MENU_MOVE_TO_LOWER_GROUP = _tr('Move to lower group')
MENU_MOVE_TO_UPPER_GROUP = _tr('Move to upper group')
MENU_HIDE_PANEL = _tr('Hide panel')

_AREA = Qt.DockWidgetArea
_HORIZONTAL = Qt.Orientation.Horizontal
_VERTICAL = Qt.Orientation.Vertical
_SIDE_AREAS = (_AREA.LeftDockWidgetArea, _AREA.RightDockWidgetArea)


class DockZone(StrEnum):
    """Places a dock can be moved to by name."""
    TOP = 'top'
    LEFT = 'left'
    RIGHT = 'right'
    BOTTOM_UPPER = 'bottom_upper'
    BOTTOM_LOWER = 'bottom_lower'


_ZONE_TITLES = {
    DockZone.TOP: _tr('Top'),
    DockZone.LEFT: _tr('Left'),
    DockZone.RIGHT: _tr('Right'),
    DockZone.BOTTOM_UPPER: _tr('Bottom, upper row'),
    DockZone.BOTTOM_LOWER: _tr('Bottom, lower row')
}

_ZONE_AREAS = {
    DockZone.TOP: _AREA.TopDockWidgetArea,
    DockZone.LEFT: _AREA.LeftDockWidgetArea,
    DockZone.RIGHT: _AREA.RightDockWidgetArea,
    DockZone.BOTTOM_UPPER: _AREA.BottomDockWidgetArea,
    DockZone.BOTTOM_LOWER: _AREA.BottomDockWidgetArea
}


def zone_title(zone: DockZone) -> str:
    """Returns the translated name shown for a zone."""
    return _ZONE_TITLES[zone]


def _group_of(window: QMainWindow, dock: PanelDock) -> list[PanelDock]:
    """Returns the dock and every dock tabified with it."""
    return [dock] + [other for other in window.tabifiedDockWidgets(dock) if isinstance(other, PanelDock)]


def _group_bounds(group: list[PanelDock]) -> Optional[QRect]:
    """Returns where a tab group is drawn, or None if no member is on screen."""
    for dock in group:
        if dock.isVisible():
            return dock.geometry()
    return None


def _area_groups(window: QMainWindow, area: Qt.DockWidgetArea) -> list[list[PanelDock]]:
    """Returns the tab groups docked in an area."""
    groups: list[list[PanelDock]] = []
    seen: set[str] = set()
    for child in window.findChildren(PanelDock, options=Qt.FindChildOption.FindDirectChildrenOnly):
        if child.isFloating() or window.dockWidgetArea(child) != area or child.objectName() in seen:
            continue
        group = _group_of(window, child)
        seen.update(member.objectName() for member in group)
        groups.append(group)
    return groups


def _is_above(upper: QRect, lower: QRect) -> bool:
    """Returns whether one group is drawn entirely above another, over some of the same width."""
    return upper.bottom() < lower.top() and upper.left() <= lower.right() and lower.left() <= upper.right()


def _is_lower(window: QMainWindow, dock: PanelDock) -> bool:
    """Returns whether another group in the dock's area is drawn above the dock's group."""
    group = _group_of(window, dock)
    bounds = _group_bounds(group)
    if bounds is None:
        return False
    names = {member.objectName() for member in group}
    for other in _area_groups(window, window.dockWidgetArea(dock)):
        if other[0].objectName() in names:
            continue
        other_bounds = _group_bounds(other)
        if other_bounds is not None and _is_above(other_bounds, bounds):
            return True
    return False


def zone_of(window: QMainWindow, dock: PanelDock) -> Optional[DockZone]:
    """Returns the named zone containing a dock, or None if the dock is floating."""
    if dock.isFloating():
        return None
    area = window.dockWidgetArea(dock)
    if area == _AREA.TopDockWidgetArea:
        return DockZone.TOP
    if area == _AREA.LeftDockWidgetArea:
        return DockZone.LEFT
    if area == _AREA.RightDockWidgetArea:
        return DockZone.RIGHT
    if area == _AREA.BottomDockWidgetArea:
        return DockZone.BOTTOM_LOWER if _is_lower(window, dock) else DockZone.BOTTOM_UPPER
    return None


def _zone_docks(window: QMainWindow, zone: DockZone, excluding: list[PanelDock]) -> list[PanelDock]:
    """Returns the docks in a zone, leaving out the excluded ones."""
    excluded = {dock.objectName() for dock in excluding}
    return [child for child in window.findChildren(PanelDock, options=Qt.FindChildOption.FindDirectChildrenOnly)
            if child.objectName() not in excluded and zone_of(window, child) == zone]


def _place(window: QMainWindow, dock: PanelDock, zone: DockZone, others: list[PanelDock]) -> None:
    """Docks one dock in a zone. `others` are the docks that would otherwise already be there."""
    dock.setFloating(False)
    area = _ZONE_AREAS[zone]
    if zone == DockZone.BOTTOM_LOWER:
        if len(others) == 0:
            # A vertical split of the whole bottom area makes a full-width row:
            window.addDockWidget(area, dock, _VERTICAL)
        else:
            window.splitDockWidget(others[0], dock, _HORIZONTAL)
    elif zone == DockZone.BOTTOM_UPPER and len(others) > 0:
        window.splitDockWidget(others[0], dock, _HORIZONTAL)
    else:
        window.addDockWidget(area, dock)


def move_dock_to_zone(window: QMainWindow, dock: PanelDock, zone: DockZone) -> None:
    """Moves a dock to a zone as a group of its own, creating the zone if it is empty."""
    others = _zone_docks(window, zone, [dock])
    if zone == DockZone.BOTTOM_LOWER and len(others) == 0 and len(_zone_docks(window, DockZone.BOTTOM_UPPER,
                                                                              [dock])) == 0:
        zone = DockZone.BOTTOM_UPPER  # Nothing to be below.
    # Placing relative to a dock that is also being moved is not possible, so a dock only joins another dock's row:
    was_hidden = dock.isHidden()
    others = [other for other in others if not other.isFloating() and other.objectName() != dock.objectName()]
    dock.show()
    _place(window, dock, zone, others)
    dock.show()
    if was_hidden:
        dock.hide()
    else:
        dock.raise_()


def move_docks_to_zone(window: QMainWindow, docks: list[PanelDock], zone: DockZone) -> None:
    """Moves docks to one zone, tabified together. The first dock leads the tab group, and docks that were closed stay
    closed."""
    docks = [dock for dock in docks if dock.is_available]
    if len(docks) == 0:
        return
    hidden = [dock for dock in docks if dock.isHidden()]
    front = next((dock for dock in docks if dock.is_showing), docks[0])
    move_dock_to_zone(window, docks[0], zone)
    leader = docks[0]
    leader.show()
    for dock in docks[1:]:
        dock.setFloating(False)
        dock.show()
        window.tabifyDockWidget(leader, dock)
        dock.show()
    for dock in hidden:
        dock.hide()
    front.raise_()


def other_group_title(window: QMainWindow, dock: PanelDock) -> Optional[str]:
    """Returns the menu text for moving a dock between the groups of its side area, or None if it has no other group
    to move to."""
    if dock.isFloating() or window.dockWidgetArea(dock) not in _SIDE_AREAS:
        return None
    group_names = {member.objectName() for member in _group_of(window, dock)}
    if len(_area_groups(window, window.dockWidgetArea(dock))) < 2 and len(group_names) < 2:
        return None
    return MENU_MOVE_TO_UPPER_GROUP if _is_lower(window, dock) else MENU_MOVE_TO_LOWER_GROUP


def move_dock_to_other_group(window: QMainWindow, dock: PanelDock) -> None:
    """Moves a dock from the upper group of its side area into the group below it, or from a lower group into the
    upper group. With no group below, the dock splits off into a new one."""
    title = other_group_title(window, dock)
    if title is None:
        return
    area = window.dockWidgetArea(dock)
    names = {member.objectName() for member in _group_of(window, dock)}
    groups = [group for group in _area_groups(window, area) if group[0].objectName() not in names]
    visible = [(bounds, group) for group in groups if (bounds := _group_bounds(group)) is not None]
    visible.sort(key=lambda item: item[0].top())
    was_hidden = dock.isHidden()
    dock.show()
    if len(visible) > 0:
        window.tabifyDockWidget(visible[0][1][0], dock)
    else:
        sibling = next(member for member in _group_of(window, dock) if member is not dock)
        window.splitDockWidget(sibling, dock, _VERTICAL)
    dock.show()
    if was_hidden:
        dock.hide()
    else:
        dock.raise_()


def add_move_all_actions(menu: QMenu, window: QMainWindow, all_docks: list[PanelDock]) -> None:
    """Fills a menu with one "move every tab to" action per zone."""
    for zone in DockZone:
        action = menu.addAction(zone_title(zone))
        action.triggered.connect(lambda _checked=False, z=zone: move_docks_to_zone(window, all_docks, z))


def build_dock_menu(window: QMainWindow, dock: PanelDock, all_docks: list[PanelDock],
                    parent: Optional[QWidget] = None) -> QMenu:
    """Builds the context menu for a dock's title area or tab.

    - "Move to" has one entry per zone, with the dock's zone checked and disabled.
    - A side-area dock also gets a group move entry.
    - "Move all tabs to" moves every dock with content.
    - "Hide panel" closes the dock.
    """
    menu = QMenu(parent if parent is not None else window)
    current = zone_of(window, dock)
    move_menu = menu.addMenu(MENU_MOVE_TO)
    for zone in DockZone:
        action = move_menu.addAction(zone_title(zone))
        action.setCheckable(True)
        action.setChecked(zone == current)
        action.setEnabled(zone != current)
        action.triggered.connect(lambda _checked=False, z=zone: move_dock_to_zone(window, dock, z))
    group_title = other_group_title(window, dock)
    if group_title is not None:
        group_action = menu.addAction(group_title)
        group_action.triggered.connect(lambda _checked=False: move_dock_to_other_group(window, dock))
    move_all_menu = menu.addMenu(MENU_MOVE_ALL_TO)
    add_move_all_actions(move_all_menu, window, all_docks)
    menu.addSeparator()
    hide_action: QAction = menu.addAction(MENU_HIDE_PANEL)
    hide_action.triggered.connect(lambda _checked=False: dock.hide())
    return menu
