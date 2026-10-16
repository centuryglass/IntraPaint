"""Orientation and size class for a panel, computed from its dock's area and size.

A panel never measures the window. Its host reports two facts: an `Orientation` and a `SizeClass`. All thresholds live
in this module, so DPI normalization (issue #13) changes them in one place.

- Side panels (left and right docks) are a tall column and are classed by width.
- Strip panels (top and bottom docks) are a wide row and are classed by height.
- A floating dock is a side panel when it is taller than wide.
- `SizeClassTracker` keeps the current class while the size stays within `HYSTERESIS` pixels of its range, so dragging
  a separator across a boundary doesn't flicker.

`SizeClass` sets density along the constrained axis. Arrangement uses a `GridSize`, which measures both axes:
- An area is `GridSize(columns, rows)`: how many `GRID_COLUMN_WIDTH` columns fit across it and how many
  `GRID_ROW_HEIGHT` bands fit down it, each from 1 to `GRID_MAX_CELLS`. Measure the area the layout fills, not the dock.
- A `GridLayoutPanel` declares the `GridSize`s it has a layout for, and `choose_layout` picks one for an area.
- `GridSizeTracker` applies `HYSTERESIS` to each axis separately.
"""
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Iterable, Optional, Protocol, runtime_checkable

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

GRID_COLUMN_WIDTH = 250
GRID_ROW_HEIGHT = 120
GRID_MAX_CELLS = 3


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


@dataclass(frozen=True)
class GridSize:
    """An area or a layout in grid cells: `columns` across and `rows` down, each from 1 to `GRID_MAX_CELLS`.

    Written columns x rows, so `GridSize(3, 1)` is "3x1". Raises ValueError for a count outside that range.
    """
    columns: int
    rows: int

    def __post_init__(self) -> None:
        for count in (self.columns, self.rows):
            if not 1 <= count <= GRID_MAX_CELLS:
                raise ValueError(f'Invalid grid size {self.columns}x{self.rows}')

    @property
    def area(self) -> int:
        """The number of cells covered."""
        return self.columns * self.rows

    def fits_in(self, other: 'GridSize') -> bool:
        """Returns whether this size fits inside another on both axes."""
        return self.columns <= other.columns and self.rows <= other.rows

    def __str__(self) -> str:
        return f'{self.columns}x{self.rows}'


def _cell_count(extent: int, unit: int) -> int:
    return max(1, min(GRID_MAX_CELLS, extent // unit))


def grid_size_for(size: QSize) -> GridSize:
    """Returns how many grid columns and row bands fit in an area, with no hysteresis.

    `n` columns fit from `n * GRID_COLUMN_WIDTH` pixels wide, and `n` rows from `n * GRID_ROW_HEIGHT` tall.
    """
    return GridSize(_cell_count(size.width(), GRID_COLUMN_WIDTH), _cell_count(size.height(), GRID_ROW_HEIGHT))


def _tracked_cell_count(current: int, extent: int, unit: int) -> int:
    """Keeps `current` until `extent` is more than `HYSTERESIS` pixels outside its range."""
    shrink = current > 1 and extent < current * unit - HYSTERESIS
    grow = current < GRID_MAX_CELLS and extent >= (current + 1) * unit + HYSTERESIS
    return _cell_count(extent, unit) if shrink or grow else current


class GridSizeTracker:
    """Tracks one area's `GridSize` across resizes, keeping each axis's count near its boundaries."""

    def __init__(self) -> None:
        self._grid_size: Optional[GridSize] = None

    @property
    def grid_size(self) -> Optional[GridSize]:
        """The current grid size, or None before the first update."""
        return self._grid_size

    def update(self, size: QSize) -> bool:
        """Applies a new area size, returning whether the grid size changed."""
        old = self._grid_size
        if old is None:
            self._grid_size = grid_size_for(size)
        else:
            self._grid_size = GridSize(_tracked_cell_count(old.columns, size.width(), GRID_COLUMN_WIDTH),
                                       _tracked_cell_count(old.rows, size.height(), GRID_ROW_HEIGHT))
        return old != self._grid_size


def choose_layout(available: GridSize, layouts: Iterable[GridSize], orientation: Orientation) -> Optional[GridSize]:
    """Returns the declared layout to use in an area, or None if no layouts are declared.

    - The largest layout by area that fits wins.
    - On a tie, strips prefer more columns and side panels more rows.
    - If none fits, the smallest layout wins, with the same tie-break. The panel's body scrolls.
    """
    layouts = list(layouts)
    if len(layouts) == 0:
        return None

    def long_axis(layout: GridSize) -> int:
        return layout.columns if orientation == Orientation.STRIP else layout.rows

    fitting = [layout for layout in layouts if layout.fits_in(available)]
    if len(fitting) == 0:
        return min(layouts, key=lambda layout: (layout.area, -long_axis(layout)))
    return max(fitting, key=lambda layout: (layout.area, long_axis(layout)))


@runtime_checkable
class GridLayoutPanel(Protocol):
    """Content that arranges itself in one of the `GridSize` layouts it declares."""

    def grid_layouts(self) -> tuple[GridSize, ...]:
        """Returns the layouts this content has. It must not change while the content is shown."""

    def set_grid_layout(self, orientation: Orientation, layout: GridSize) -> None:
        """Arranges the content for a chosen layout. Called only when the orientation or layout changes."""
