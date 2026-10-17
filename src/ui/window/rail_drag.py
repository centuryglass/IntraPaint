"""Dragging a dock's rail button: within its rail to tab or split the dock, or out of the rail into Qt's dock drag.

- A press on a rail button becomes a drag once it moves `DRAG_DISTANCE` px. A shorter press stays a click.
- Within the rail, a marker shows the drop. Over another group's buttons, the drop tabs the dock into that group
  (`tab_with`). Between groups, it splits the dock beside the nearer group, on that side (`split_beside`).
- Leaving the rail hands the drag to Qt (`start_qt_dock_drag`), which floats the dock and follows the mouse as for any
  title bar drag.
- A floating dock dragged over a rail, whether handed off from a rail or dragged by its own title bar, shows the same
  marker there. Released over the rail, Qt finishes its own drag first, then the dock is placed as a rail drop would
  place it.
"""
from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt
from PySide6.QtGui import QCursor, QMouseEvent, QPainter, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget

from src.ui.window.dock_placement import SplitSide, split_beside, tab_with
from src.ui.window.dock_rail import DockRail, DockRails, RailButton
from src.ui.window.panel_dock import PanelDock
from src.ui.window.qt_dock_drag import start_qt_dock_drag

DRAG_DISTANCE = 6
# How far the pointer may stray past a rail's edges before the drag leaves the rail:
RAIL_LEAVE_MARGIN = 8
MARKER_WIDTH = 3


@dataclass(frozen=True)
class RailDrop:
    """Where a rail button drag would put its dock: tabbed with `target`, or split beside it on `side`."""
    target: PanelDock
    side: Optional[SplitSide]
    marker: QRect


class _DropMarker(QWidget):
    """Outlines a tab drop's group, or fills a split drop's line."""

    def __init__(self) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.tab = False
        self.hide()

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the outline or line in the highlight color."""
        painter = QPainter(self)
        highlight = self.palette().color(QPalette.ColorRole.Highlight)
        if self.tab:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(highlight, 2))
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 4, 4)
        else:
            painter.fillRect(self.rect(), highlight)
        painter.end()


class RailDrag(QObject):
    """Watches rail buttons for drags, and places their docks where they're dropped."""

    def __init__(self, window: QMainWindow, rails: DockRails, moved: Callable[[], None]) -> None:
        """`moved` is called after a drop within a rail moves a dock."""
        super().__init__(window)
        self._window = window
        self._rails = rails
        self._moved = moved
        self._marker = _DropMarker()
        self._button: Optional[RailButton] = None
        self._press_pos = QPoint()
        self._dragging = False
        self._floating_drop: Optional[RailDrop] = None

    @property
    def marker(self) -> QWidget:
        """Returns the drop marker, shown in the rail while a drag is over it."""
        return self._marker

    def watch(self, button: RailButton) -> None:
        """Lets a rail button be dragged, and its dock be dropped on a rail while floating."""
        button.installEventFilter(self)
        dock = button.dock
        dock.installEventFilter(self)
        # A floating dock without native decorations gets Qt's resize handler as an event filter, which takes mouse
        # moves first. Installing this filter again puts it back in front:
        dock.topLevelChanged.connect(lambda _floating, watched=dock: watched.installEventFilter(self))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # pylint: disable=invalid-name
        """Starts, follows and ends drags of watched buttons, leaving clicks to the buttons, and follows floating
        docks dragged over rails."""
        if isinstance(watched, PanelDock):
            return self._floating_dock_event(watched, event)
        if not isinstance(watched, RailButton) or not isinstance(event, QMouseEvent):
            return False
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._button = watched
            self._press_pos = event.position().toPoint()
            self._dragging = False
        elif event.type() == QEvent.Type.MouseMove and watched is self._button \
                and event.buttons() & Qt.MouseButton.LeftButton:
            if not self._dragging:
                if (event.position().toPoint() - self._press_pos).manhattanLength() < DRAG_DISTANCE:
                    return False
                self._dragging = True
                watched.setDown(False)
            self._drag_to(watched, event.globalPosition().toPoint())
            return True
        elif event.type() == QEvent.Type.MouseButtonRelease and watched is self._button:
            if self._dragging:
                drop = self.drop_at(watched, event.globalPosition().toPoint())
                self._end()
                watched.setDown(False)
                if drop is not None:
                    self._apply(watched.dock, drop)
            self._button = None
        return False

    def _end(self) -> None:
        self._dragging = False
        self._marker.hide()

    def _rail(self, button: RailButton) -> DockRail:
        return self._rails.rail_for(button.dock)

    def _drag_to(self, button: RailButton, global_pos: QPoint) -> None:
        rail = self._rail(button)
        margin = RAIL_LEAVE_MARGIN
        if not rail.rect().adjusted(-margin, -margin, margin, margin).contains(rail.mapFromGlobal(global_pos)):
            self._hand_off(button, global_pos)
            return
        self._show_marker(rail, self.drop_at(button, global_pos))

    def _show_marker(self, rail: DockRail, drop: Optional[RailDrop]) -> None:
        if drop is None:
            self._marker.hide()
            return
        self._marker.setParent(rail.content)
        self._marker.tab = drop.side is None
        self._marker.setGeometry(drop.marker)
        self._marker.show()
        self._marker.raise_()
        self._marker.update()

    def drop_at(self, button: RailButton, global_pos: QPoint) -> Optional[RailDrop]:
        """Returns where dropping a dragged button at a screen position puts its dock, or None for nowhere."""
        return self.drop_in(self._rail(button), button.dock, global_pos)

    def drop_in(self, rail: DockRail, dock: PanelDock, global_pos: QPoint) -> Optional[RailDrop]:
        """Returns where dropping a dock on a rail at a screen position puts it, or None for nowhere."""
        side_rail = rail.is_side
        content = rail.content
        local = content.mapFromGlobal(global_pos)
        along = local.y() if side_rail else local.x()
        groups = [[member for member in group if not member.isHidden()] for group in rail.groups]
        groups = [group for group in groups if len(group) > 0]
        spans = [(self._start(group[0], side_rail), self._end_of(group[-1], side_rail)) for group in groups]
        for group, (start, end) in zip(groups, spans):
            if start <= along <= end:
                if any(member.dock is dock for member in group):
                    return None
                return RailDrop(group[0].dock, None, self._span_rect(content, side_rail, start, end))
        before = [idx for idx, (start, _end) in enumerate(spans) if start > along]
        after = [idx for idx, (_start, end) in enumerate(spans) if end < along]
        if len(before) > 0 and (len(after) == 0
                                or spans[before[0]][0] - along <= along - spans[after[-1]][1]):
            idx, is_after = before[0], False
        elif len(after) > 0:
            idx, is_after = after[-1], True
        else:
            return None
        others = [member.dock for member in groups[idx] if member.dock is not dock]
        if len(others) == 0:
            return None
        if side_rail:
            side = SplitSide.BELOW if is_after else SplitSide.ABOVE
        else:
            side = SplitSide.RIGHT if is_after else SplitSide.LEFT
        edge = spans[idx][1] + MARKER_WIDTH if is_after else spans[idx][0] - 2 * MARKER_WIDTH
        return RailDrop(others[0], side, self._span_rect(content, side_rail, edge, edge + MARKER_WIDTH - 1))

    @staticmethod
    def _start(button: RailButton, side_rail: bool) -> int:
        return button.geometry().top() if side_rail else button.geometry().left()

    @staticmethod
    def _end_of(button: RailButton, side_rail: bool) -> int:
        return button.geometry().bottom() if side_rail else button.geometry().right()

    @staticmethod
    def _span_rect(content: QWidget, side_rail: bool, start: int, end: int) -> QRect:
        if side_rail:
            return QRect(0, start, content.width(), end - start + 1)
        return QRect(start, 0, end - start + 1, content.height())

    def _rail_at(self, global_pos: QPoint) -> Optional[DockRail]:
        margin = RAIL_LEAVE_MARGIN
        for area in (Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea,
                     Qt.DockWidgetArea.TopDockWidgetArea, Qt.DockWidgetArea.BottomDockWidgetArea):
            rail = self._rails.rail(area)
            if rail.isVisible() and rail.rect().adjusted(-margin, -margin, margin, margin).contains(
                    rail.mapFromGlobal(global_pos)):
                return rail
        return None

    def _floating_dock_event(self, dock: PanelDock, event: QEvent) -> bool:
        """Shows the marker while a floating dock is dragged over a rail, and places it there when released."""
        if not dock.isFloating():
            return False
        moves = (QEvent.Type.MouseMove, QEvent.Type.NonClientAreaMouseMove)
        releases = (QEvent.Type.MouseButtonRelease, QEvent.Type.NonClientAreaMouseButtonRelease)
        if event.type() in moves and isinstance(event, QMouseEvent) and event.buttons() & Qt.MouseButton.LeftButton:
            self._hover_floating(dock, event.globalPosition().toPoint())
        elif event.type() == QEvent.Type.Move and QApplication.mouseButtons() & Qt.MouseButton.LeftButton:
            # Native title bars move the window without mouse events:
            self._hover_floating(dock, QCursor.pos())
        elif event.type() in releases and self._floating_drop is not None:
            drop = self._floating_drop
            self._floating_drop = None
            self._marker.hide()
            # Qt ends its own drag first, so the placement isn't undone by it:
            dock.event(event)
            self._apply(dock, drop)
            return True
        return False

    def _hover_floating(self, dock: PanelDock, global_pos: QPoint) -> None:
        rail = self._rail_at(global_pos)
        self._floating_drop = None if rail is None else self.drop_in(rail, dock, global_pos)
        if rail is None:
            self._marker.hide()
        else:
            self._show_marker(rail, self._floating_drop)

    def _apply(self, dock: PanelDock, drop: RailDrop) -> None:
        if drop.side is None:
            tab_with(self._window, dock, drop.target)
        else:
            split_beside(self._window, dock, drop.target, drop.side)
        self._moved()

    def _hand_off(self, button: RailButton, global_pos: QPoint) -> None:
        """Ends the rail drag and starts Qt's dock drag from the dock's title bar, at the pointer."""
        self._end()
        self._button = None
        button.setDown(False)
        start_qt_dock_drag(self._window, button.dock, global_pos)
