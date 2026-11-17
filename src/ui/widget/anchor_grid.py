"""A 3x3 grid of cells for picking where existing content sits in a resized area: a corner, an edge or the center.

The grid is a view. It reports the clicked cell through `anchorSelected` as (column, row), each 0 to 2, and shows the
anchor the owner sets with `set_anchor`. The owner turns an anchor into an offset.
"""
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QApplication, QSizePolicy, QWidget

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.anchor_grid'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


ANCHOR_TOOLTIP = _tr('Place the current image at this corner, edge or the center of the new canvas')

GRID_SIDE = 3
CELL_SIZE = 22
CELL_GAP = 3


class AnchorGrid(QWidget):
    """A 3x3 grid of selectable cells. Clicking one emits `anchorSelected(column, row)`."""

    anchorSelected = Signal(int, int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._anchor: Optional[tuple[int, int]] = None
        self.setToolTip(ANCHOR_TOOLTIP)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def anchor(self) -> Optional[tuple[int, int]]:
        """Returns the highlighted (column, row), or None when the content sits at no anchor."""
        return self._anchor

    def set_anchor(self, anchor: Optional[tuple[int, int]]) -> None:
        """Highlights one cell, or none."""
        if anchor != self._anchor:
            self._anchor = anchor
            self.update()

    def sizeHint(self) -> QSize:
        """Returns the grid's fixed size."""
        side = GRID_SIDE * CELL_SIZE + (GRID_SIDE - 1) * CELL_GAP
        return QSize(side, side)

    def minimumSizeHint(self) -> QSize:
        """Returns the grid's fixed size."""
        return self.sizeHint()

    def cell_rect(self, column: int, row: int) -> QRectF:
        """Returns one cell's bounds in widget coordinates."""
        return QRectF(column * (CELL_SIZE + CELL_GAP), row * (CELL_SIZE + CELL_GAP), CELL_SIZE, CELL_SIZE)

    def _cell_at(self, point: QPointF) -> Optional[tuple[int, int]]:
        for column in range(GRID_SIDE):
            for row in range(GRID_SIDE):
                if self.cell_rect(column, row).contains(point):
                    return column, row
        return None

    def mousePressEvent(self, event: QMouseEvent) -> None:  # pylint: disable=invalid-name
        """Selects the clicked cell."""
        cell = self._cell_at(event.position())
        if cell is not None and event.button() == Qt.MouseButton.LeftButton:
            self.anchorSelected.emit(*cell)

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the cells, with the anchor filled."""
        palette = self.palette()
        group = QPalette.ColorGroup.Active if self.isEnabled() else QPalette.ColorGroup.Disabled
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(palette.color(group, QPalette.ColorRole.Mid), 1))
        for column in range(GRID_SIDE):
            for row in range(GRID_SIDE):
                selected = (column, row) == self._anchor
                painter.setBrush(palette.color(group, QPalette.ColorRole.Highlight) if selected
                                 else palette.color(group, QPalette.ColorRole.Base))
                painter.drawRoundedRect(self.cell_rect(column, row).adjusted(0.5, 0.5, -0.5, -0.5), 3, 3)
        painter.end()
