"""Scene item for one ruler guide: a line across the image that is only ever drawn."""
from typing import Optional

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPalette, QPen, QColor
from PySide6.QtWidgets import QApplication, QGraphicsItem, QStyleOptionGraphicsItem, QWidget

# Scene pixels added around the line for repaint bounds. The cosmetic pen is 1 view pixel wide, which is wider than
# this in scene pixels once the view is zoomed far out.
BOUNDS_PADDING = 32
# Dash lengths, in pen widths (view pixels), for the black segments drawn over the accent-colored line:
DASH_PATTERN = [4.0, 4.0]


class GuideLineItem(QGraphicsItem):
    """A guide line spanning the image on one axis, drawn with a cosmetic 1px pen that alternates black and the
    palette's accent color, so it shows over any image content at any zoom.

    The item accepts no mouse buttons and no hover events, so it never takes input from the tools beneath it.
    """

    def __init__(self, orientation: Qt.Orientation, position: int = 0, length: int = 0) -> None:
        super().__init__()
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setAcceptHoverEvents(False)
        self._orientation = orientation
        self._position = position
        self._length = length

    @property
    def orientation(self) -> Qt.Orientation:
        """Returns the guide's orientation: horizontal guides have a fixed y coordinate, vertical ones a fixed x."""
        return self._orientation

    @property
    def position(self) -> int:
        """Returns the guide's coordinate on its fixed axis."""
        return self._position

    @property
    def length(self) -> int:
        """Returns the line's extent along its own axis, starting at 0."""
        return self._length

    def set_guide(self, position: int, length: int) -> None:
        """Sets the guide's coordinate and the image size along its own axis."""
        if position == self._position and length == self._length:
            return
        self.prepareGeometryChange()
        self._position = position
        self._length = length
        self.update()

    def boundingRect(self) -> QRectF:  # pylint: disable=invalid-name  # Qt override
        """Returns the line's bounds, padded for the cosmetic pen."""
        pad = BOUNDS_PADDING
        if self._orientation == Qt.Orientation.Horizontal:
            return QRectF(-pad, self._position - pad, self._length + pad * 2, pad * 2)
        return QRectF(self._position - pad, -pad, pad * 2, self._length + pad * 2)

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              widget: Optional[QWidget] = None) -> None:
        """Draws the accent-colored line with black dashes over it."""
        assert painter is not None
        accent: QColor = (widget.palette() if widget is not None else QApplication.palette()).color(
            QPalette.ColorRole.Highlight)
        if self._orientation == Qt.Orientation.Horizontal:
            start, end = (0.0, float(self._position)), (float(self._length), float(self._position))
        else:
            start, end = (float(self._position), 0.0), (float(self._position), float(self._length))
        painter.save()
        accent_pen = QPen(accent, 1)
        accent_pen.setCosmetic(True)
        painter.setPen(accent_pen)
        painter.drawLine(start[0], start[1], end[0], end[1])
        black_pen = QPen(QColor(0, 0, 0), 1)
        black_pen.setCosmetic(True)
        black_pen.setDashPattern(DASH_PATTERN)
        painter.setPen(black_pen)
        painter.drawLine(start[0], start[1], end[0], end[1])
        painter.restore()
