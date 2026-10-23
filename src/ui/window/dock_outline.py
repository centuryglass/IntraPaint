"""The 1px outline around a `PanelDock`, in the color of the line between a `DockRail` and the panels beside it.

- The outline marks where a panel ends, most of all where floating panels overlap each other or the canvas.
- It paints over the dock's outermost pixels and ignores the mouse, so presses reach the content beneath.
- A docked dock leaves out the edge on its rail's side, where the rail's own line already is. A floating dock
  outlines every edge.
"""
from typing import Optional

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import QWidget


class DockOutline(QWidget):
    """Draws the outline over its parent dock's edges."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._skipped_edge: Optional[Qt.Edge] = None
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

    @property
    def skipped_edge(self) -> Optional[Qt.Edge]:
        """The edge left undrawn, or None to draw all four."""
        return self._skipped_edge

    def set_skipped_edge(self, edge: Optional[Qt.Edge]) -> None:
        """Sets the edge to leave undrawn, or None to draw all four."""
        if edge != self._skipped_edge:
            self._skipped_edge = edge
            self.update()

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the edges in the palette's shadow color."""
        painter = QPainter(self)
        color = self.palette().color(QPalette.ColorRole.Shadow)
        bounds = self.rect()
        edges = {
            Qt.Edge.LeftEdge: QRect(bounds.left(), bounds.top(), 1, bounds.height()),
            Qt.Edge.RightEdge: QRect(bounds.right(), bounds.top(), 1, bounds.height()),
            Qt.Edge.TopEdge: QRect(bounds.left(), bounds.top(), bounds.width(), 1),
            Qt.Edge.BottomEdge: QRect(bounds.left(), bounds.bottom(), bounds.width(), 1),
        }
        for edge, rect in edges.items():
            if edge != self._skipped_edge:
                painter.fillRect(rect, color)
        painter.end()
