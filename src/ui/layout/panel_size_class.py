"""Orientation and size class for a panel, computed from its dock's area and size.

A panel never measures the window. Its host reports two facts: an `Orientation` and a `SizeClass`. All thresholds live
in this module, so DPI normalization (issue #13) changes them in one place.

- Side panels (left and right docks) are a tall column and are classed by width.
- Strip panels (top and bottom docks) are a wide row and are classed by height.
- A floating dock is a side panel when it is taller than wide.
- `SizeClassTracker` keeps the current class while the size stays within `HYSTERESIS` pixels of its range, so dragging
  a separator across a boundary doesn't flicker.
"""
from enum import Enum, IntEnum
from typing import Optional

from PySide6.QtCore import QSize, Qt


class Orientation(Enum):
    """Whether a panel is a tall column or a wide row."""
    SIDE = 'side'
    STRIP = 'strip'


class SizeClass(IntEnum):
    """How much room a panel has along its constrained axis, in increasing order.

    Strip panels call `COMPACT` "Short" and `WIDE` "Tall".
    """
    COMPACT = 0
    REGULAR = 1
    WIDE = 2


# Where COMPACT ends (exclusive) and where REGULAR ends (inclusive), per orientation.
SIDE_BOUNDARIES = (260, 420)
STRIP_BOUNDARIES = (170, 320)
HYSTERESIS = 6

SIDE_PANEL_MIN_COLUMN_WIDTH = 240
STRIP_SECTION_MIN_WIDTH = 240
STRIP_SECTION_MAX_WIDTH = 300


def boundaries(orientation: Orientation) -> tuple[int, int]:
    """Returns the sizes where `COMPACT` ends and where `REGULAR` ends for an orientation."""
    return SIDE_BOUNDARIES if orientation == Orientation.SIDE else STRIP_BOUNDARIES


def constrained_extent(orientation: Orientation, size: QSize) -> int:
    """Returns the dimension that decides the size class: width for side panels, height for strips."""
    return size.width() if orientation == Orientation.SIDE else size.height()


def size_class_for(orientation: Orientation, size: QSize) -> SizeClass:
    """Returns the size class for a dock size, with no hysteresis.

    Side panels: COMPACT below 260, REGULAR from 260 through 420, WIDE above 420. Strips: COMPACT below 170, REGULAR
    from 170 through 320, TALL above 320.
    """
    extent = constrained_extent(orientation, size)
    compact_end, regular_end = boundaries(orientation)
    if extent < compact_end:
        return SizeClass.COMPACT
    if extent <= regular_end:
        return SizeClass.REGULAR
    return SizeClass.WIDE


def orientation_for_dock(area: Qt.DockWidgetArea, floating: bool, size: QSize) -> Orientation:
    """Returns a dock's orientation from its area, or from its aspect ratio when it is floating.

    Left and right areas are side panels, top and bottom are strips. A floating dock taller than wide is a side panel,
    and a square one is a strip.
    """
    if floating:
        return Orientation.SIDE if size.height() > size.width() else Orientation.STRIP
    if area in (Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea):
        return Orientation.SIDE
    return Orientation.STRIP


class SizeClassTracker:
    """Tracks one panel's size class across resizes, keeping the current class near its boundaries.

    The class changes only once the size is more than `HYSTERESIS` pixels outside the current class's range. Changing
    orientation discards the history and classifies from scratch.
    """

    def __init__(self, orientation: Orientation = Orientation.SIDE, size: Optional[QSize] = None) -> None:
        self._orientation = orientation
        self._size_class: Optional[SizeClass] = None
        if size is not None:
            self.update(orientation, size)

    @property
    def orientation(self) -> Orientation:
        """The orientation from the latest update."""
        return self._orientation

    @property
    def size_class(self) -> Optional[SizeClass]:
        """The current size class, or None before the first update."""
        return self._size_class

    def update(self, orientation: Orientation, size: QSize) -> bool:
        """Applies new host facts, returning whether the orientation or size class changed."""
        old = (self._orientation, self._size_class)
        if orientation != self._orientation or self._size_class is None:
            self._orientation = orientation
            self._size_class = size_class_for(orientation, size)
            return old != (self._orientation, self._size_class)
        extent = constrained_extent(orientation, size)
        compact_end, regular_end = boundaries(orientation)
        low, high = {
            SizeClass.COMPACT: (None, compact_end),
            SizeClass.REGULAR: (compact_end, regular_end + 1),
            SizeClass.WIDE: (regular_end + 1, None)
        }[self._size_class]
        below = low is not None and extent < low - HYSTERESIS
        above = high is not None and extent >= high + HYSTERESIS
        if below or above:
            self._size_class = size_class_for(orientation, size)
        return old != (self._orientation, self._size_class)
