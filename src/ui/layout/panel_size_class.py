"""Orientation and grid size for a panel, computed from its dock's area and size.

A panel never measures the window. Its host reports two facts: an `Orientation` and a `GridSize`. All thresholds live
in this module, so DPI normalization (issue #13) changes them in one place.

- Side panels (left and right docks) are a tall column, and strip panels (top and bottom docks) are a wide row. A
  floating dock is a side panel when it is taller than wide. Orientation sets the direction content flows and scrolls.
- A `GridSize(columns, rows)` classes the width into 1 to 3 columns at `COLUMN_BOUNDARIES` and the height into 1 to 3
  rows at `ROW_BOUNDARIES`. Measure the area the layout fills, not the dock.
- `GridSize.constrained` is the count along a panel's short axis, which sets density: columns for side panels, rows
  for strips. The six named classes of the panel redesign are side 1x3, 2x3 and 3x3 (Compact, Regular, Wide) and
  strip 3x1, 3x2 and 3x3 (Short, Regular, Tall).
- A `GridLayoutPanel` declares the `GridSize`s it has a layout for, and `choose_layout` picks one for an area.
- `GridSizeTracker` keeps each axis's count while the size stays within `HYSTERESIS` pixels of its range, so dragging
  a separator across a boundary doesn't flicker.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional, Protocol, runtime_checkable

from PySide6.QtCore import QSize, Qt


class Orientation(Enum):
    """Whether a panel is a tall column or a wide row."""
    SIDE = 'side'
    STRIP = 'strip'


# Where 1 ends (exclusive) and where 2 ends (inclusive), per axis:
COLUMN_BOUNDARIES = (260, 420)
ROW_BOUNDARIES = (170, 320)
GRID_MAX_CELLS = 3
HYSTERESIS = 6

SIDE_PANEL_MIN_COLUMN_WIDTH = 240
STRIP_SECTION_MIN_WIDTH = 240
STRIP_SECTION_MAX_WIDTH = 300


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

    def constrained(self, orientation: Orientation) -> int:
        """Returns the count along the panel's short axis: columns for side panels, rows for strips."""
        return self.columns if orientation == Orientation.SIDE else self.rows

    def fits_in(self, other: 'GridSize') -> bool:
        """Returns whether this size fits inside another on both axes."""
        return self.columns <= other.columns and self.rows <= other.rows

    def __str__(self) -> str:
        return f'{self.columns}x{self.rows}'


def _cell_count(extent: int, cell_boundaries: tuple[int, int]) -> int:
    first_end, second_end = cell_boundaries
    if extent < first_end:
        return 1
    return 2 if extent <= second_end else 3


def grid_size_for(size: QSize) -> GridSize:
    """Returns the grid size for an area, with no hysteresis.

    Width: 1 column below 260, 2 from 260 through 420, 3 above 420. Height: 1 row below 170, 2 from 170 through 320,
    3 above 320.
    """
    return GridSize(_cell_count(size.width(), COLUMN_BOUNDARIES), _cell_count(size.height(), ROW_BOUNDARIES))


def _tracked_cell_count(current: int, extent: int, cell_boundaries: tuple[int, int]) -> int:
    """Keeps `current` until `extent` is more than `HYSTERESIS` pixels outside its range."""
    first_end, second_end = cell_boundaries
    low, high = {1: (None, first_end), 2: (first_end, second_end + 1), 3: (second_end + 1, None)}[current]
    below = low is not None and extent < low - HYSTERESIS
    above = high is not None and extent >= high + HYSTERESIS
    return _cell_count(extent, cell_boundaries) if below or above else current


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
            self._grid_size = GridSize(_tracked_cell_count(old.columns, size.width(), COLUMN_BOUNDARIES),
                                       _tracked_cell_count(old.rows, size.height(), ROW_BOUNDARIES))
        return old != self._grid_size


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
