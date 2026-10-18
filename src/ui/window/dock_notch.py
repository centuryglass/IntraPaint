"""The accent-colored triangle in a docked `PanelDock`'s upper-left corner, which drags the dock like a title bar.

- `PanelDock` shows the notch above its content while docked, and hides it while floating, where the floating title bar
  drags the dock.
- A press that moves `DRAG_DISTANCE` px becomes Qt's dock drag, as for a rail button (`start_qt_dock_drag`). A press
  outside the triangle goes to the dock beneath.
"""
from typing import Callable, Optional

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPalette, QPolygonF, QRegion
from PySide6.QtWidgets import QApplication, QWidget

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.window.dock_notch'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


NOTCH_TOOLTIP = _tr('Drag to move panel')

NOTCH_SIZE = 16
DRAG_DISTANCE = 6


class DockNotch(QWidget):
    """A corner triangle that starts a drag of its dock."""

    def __init__(self, parent: QWidget, start_drag: Callable[[QPoint], None]) -> None:
        """`start_drag` is called with the pointer's screen position once a press has moved far enough to be a drag."""
        super().__init__(parent)
        self._start_drag = start_drag
        self._press_pos: Optional[QPoint] = None
        self.setFixedSize(NOTCH_SIZE, NOTCH_SIZE)
        # The mask limits hit testing, the cursor and the tooltip to the triangle:
        self.setMask(QRegion(self._triangle().toPolygon()))
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(NOTCH_TOOLTIP)

    def _triangle(self) -> QPolygonF:
        return QPolygonF([QPointF(0, 0), QPointF(NOTCH_SIZE, 0), QPointF(0, NOTCH_SIZE)])

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Fills the triangle with the accent color."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.palette().color(QPalette.ColorRole.Highlight)))
        painter.drawPolygon(self._triangle())
        painter.end()

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:  # pylint: disable=invalid-name
        """Begins a possible drag, unless the press is off the triangle."""
        if event is None:
            return
        if event.button() != Qt.MouseButton.LeftButton or not self._triangle().containsPoint(
                event.position(), Qt.FillRule.WindingFill):
            event.ignore()
            return
        self._press_pos = event.position().toPoint()

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:  # pylint: disable=invalid-name
        """Starts the dock's drag once the press has moved `DRAG_DISTANCE` px."""
        if event is None or self._press_pos is None:
            return
        if (event.position().toPoint() - self._press_pos).manhattanLength() < DRAG_DISTANCE:
            return
        self._press_pos = None
        self._start_drag(event.globalPosition().toPoint())

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:  # pylint: disable=invalid-name
        """Ends a press that never became a drag."""
        self._press_pos = None
        if event is not None:
            event.accept()
