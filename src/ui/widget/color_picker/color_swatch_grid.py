"""A wrapping grid of clickable color swatches.

Swatches wrap to the widget's width, and the height follows through `heightForWidth`, so the grid works in narrow and
wide panels alike. Colors with alpha show over a checkerboard. The swatch matching `set_current_color` gets a
highlighted border. A left click emits `color_clicked`; callers treat it as a finished choice.
"""
from typing import Optional

from PySide6.QtCore import Qt, QRect, QSize, Signal, QPoint, QEvent
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen, QPalette, QHelpEvent
from PySide6.QtWidgets import QWidget, QSizePolicy, QToolTip

from src.util.visual.image_utils import tile_pattern_fill

SWATCH_SIZE = 20
SWATCH_SPACING = 3
CHECKER_TILE_SIZE = 5
# sizeHint asks for room for this many swatches per row.
PREFERRED_COLUMNS = 8


def color_key(color: QColor) -> str:
    """Returns the `#aarrggbb` string the grid uses to compare colors."""
    return color.name(QColor.NameFormat.HexArgb)


class ColorSwatchGrid(QWidget):
    """A wrapping grid of clickable color swatches."""

    color_clicked = Signal(QColor)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._colors: list[QColor] = []
        self._current_key = ''
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def colors(self) -> list[QColor]:
        """Returns the displayed colors, in order."""
        return [QColor(color) for color in self._colors]

    def set_colors(self, colors: list[QColor]) -> None:
        """Displays a list of colors, left to right then top to bottom."""
        self._colors = [QColor(color) for color in colors]
        self.updateGeometry()
        self.update()

    def set_current_color(self, color: QColor) -> None:
        """Highlights the swatch that matches a color, if any."""
        self._current_key = color_key(color)
        self.update()

    def columns(self, width: Optional[int] = None) -> int:
        """Returns how many swatches fit in one row at a width, defaulting to the current width."""
        if width is None:
            width = self.width()
        return max(1, (width + SWATCH_SPACING) // (SWATCH_SIZE + SWATCH_SPACING))

    def _rows(self, width: int) -> int:
        """Returns the row count at a width. An empty grid keeps one row, so the layout doesn't jump on the first
        color."""
        columns = self.columns(width)
        return max(1, (len(self._colors) + columns - 1) // columns)

    def hasHeightForWidth(self) -> bool:
        """The row count depends on the width."""
        return True

    def heightForWidth(self, width: int) -> int:
        """Returns the height that fits every swatch at a width."""
        rows = self._rows(width)
        return rows * (SWATCH_SIZE + SWATCH_SPACING) - SWATCH_SPACING

    def sizeHint(self) -> QSize:
        """Room for PREFERRED_COLUMNS swatches per row."""
        width = PREFERRED_COLUMNS * (SWATCH_SIZE + SWATCH_SPACING) - SWATCH_SPACING
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:
        """One swatch wide."""
        return QSize(SWATCH_SIZE, SWATCH_SIZE)

    def swatch_rect(self, index: int) -> QRect:
        """Returns the bounds of the swatch at an index, in widget coordinates."""
        columns = self.columns()
        row, column = divmod(index, columns)
        step = SWATCH_SIZE + SWATCH_SPACING
        return QRect(column * step, row * step, SWATCH_SIZE, SWATCH_SIZE)

    def index_at(self, point: QPoint) -> int:
        """Returns the index of the swatch under a point, or -1."""
        for index in range(len(self._colors)):
            if self.swatch_rect(index).contains(point):
                return index
        return -1

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """A left click on a swatch emits `color_clicked`."""
        assert event is not None
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        index = self.index_at(event.position().toPoint())
        if index >= 0:
            self.color_clicked.emit(QColor(self._colors[index]))

    def event(self, event: Optional[QEvent]) -> bool:
        """Shows the hovered swatch's hex value as its tooltip."""
        if event is not None and event.type() == QEvent.Type.ToolTip:
            assert isinstance(event, QHelpEvent)
            index = self.index_at(event.pos())
            if index >= 0:
                QToolTip.showText(event.globalPos(), color_key(self._colors[index]), self)
            else:
                QToolTip.hideText()
                event.ignore()
            return True
        return super().event(event)

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draws each swatch over a checkerboard, with a border, highlighting the current color."""
        painter = QPainter(self)
        border_color = self.palette().color(QPalette.ColorRole.Dark)
        highlight_color = self.palette().color(QPalette.ColorRole.Highlight)
        for index, color in enumerate(self._colors):
            bounds = self.swatch_rect(index)
            if color.alpha() < 255:
                tile_pattern_fill(painter, bounds, CHECKER_TILE_SIZE, Qt.GlobalColor.lightGray,
                                  Qt.GlobalColor.darkGray)
            painter.fillRect(bounds, color)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if color_key(color) == self._current_key:
                painter.setPen(QPen(highlight_color, 2))
                painter.drawRect(bounds.adjusted(1, 1, -1, -1))
            else:
                painter.setPen(QPen(border_color, 1))
                painter.drawRect(bounds.adjusted(0, 0, -1, -1))
        painter.end()
