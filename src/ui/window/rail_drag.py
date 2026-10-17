"""Dragging a dock's rail button: within its rail to tab or split the dock, or out of the rail into Qt's dock drag.

- A press on a rail button becomes a drag once it moves `DRAG_DISTANCE` px. A shorter press stays a click.
- Within the rail, a marker shows the drop. Over another group's buttons, the drop tabs the dock into that group
  (`tab_with`). Between groups, it splits the dock beside the nearer group, on that side (`split_beside`).
- Leaving the rail hands the drag to Qt: the dock opens with its title bar, and gets a synthetic press and move on
  it, as if that bar had been dragged. Qt floats the dock and follows the mouse from there, as for any title bar drag.
  This relies on Qt starting a dock drag from mouse events sent to the title area, which `QDockWidget` doesn't
  document; if Qt doesn't start one, the dock stays where it was.
"""
from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QMouseEvent, QPainter, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget

from src.ui.window.dock_placement import SplitSide, split_beside, tab_with
from src.ui.window.dock_rail import DockRail, DockRails, RailButton
from src.ui.window.panel_dock import PanelDock

DRAG_DISTANCE = 6
# How far the pointer may stray past a rail's edges before the drag leaves the rail:
RAIL_LEAVE_MARGIN = 8
MARKER_WIDTH = 3
# Distance from a dock's left or right edge to the point a hand-off presses in its title bar:
TITLE_PRESS_INSET = 10
TITLE_PRESS_Y = 3


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

    @property
    def marker(self) -> QWidget:
        """Returns the drop marker, shown in the rail while a drag is over it."""
        return self._marker

    def watch(self, button: RailButton) -> None:
        """Lets a rail button be dragged."""
        button.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # pylint: disable=invalid-name
        """Starts, follows and ends drags of watched buttons, leaving clicks to the buttons."""
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
        drop = self.drop_at(button, global_pos)
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
        rail = self._rail(button)
        side_rail = rail.is_side
        content = rail.content
        local = content.mapFromGlobal(global_pos)
        along = local.y() if side_rail else local.x()
        groups = [[member for member in group if not member.isHidden()] for group in rail.groups]
        groups = [group for group in groups if len(group) > 0]
        spans = [(self._start(group[0], side_rail), self._end_of(group[-1], side_rail)) for group in groups]
        for group, (start, end) in zip(groups, spans):
            if start <= along <= end:
                if button in group:
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
        others = [member.dock for member in groups[idx] if member is not button]
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
        dock = button.dock
        if dock.isHidden():
            dock.open_in_group()
        dock.show_title_bar_for_drag()
        layout = self._window.layout()
        if layout is not None:
            layout.activate()
        target = dock.mapFromGlobal(global_pos)
        # The press is far enough from the pointer for the move to pass Qt's drag distance:
        left, right = TITLE_PRESS_INSET, max(dock.width() - TITLE_PRESS_INSET, TITLE_PRESS_INSET)
        press = QPoint(left if abs(target.x() - left) >= abs(target.x() - right) else right, TITLE_PRESS_Y)
        for event_type, position, button_state in ((QEvent.Type.MouseButtonPress, press, Qt.MouseButton.LeftButton),
                                                   (QEvent.Type.MouseMove, target, Qt.MouseButton.NoButton)):
            QApplication.sendEvent(dock, QMouseEvent(event_type, QPointF(position),
                                                     QPointF(dock.mapToGlobal(position)), button_state,
                                                     Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        if not dock.isFloating():
            dock.restore_title_bar()
