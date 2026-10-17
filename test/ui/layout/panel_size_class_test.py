"""Tests the orientation and grid size calculator: boundaries on each axis, hysteresis in both directions on each axis,
orientation from a dock's area, and layout choice."""
from PySide6.QtCore import QSize, Qt

from src.ui.layout.panel_size_class import (COLUMN_BOUNDARIES, HYSTERESIS, ROW_BOUNDARIES, GridSize, GridSizeTracker,
                                            Orientation, choose_layout, grid_size_for, orientation_for_dock)
from test.base_test_case import IntraPaintTestCase


def _size(axis: int, extent: int, other: int = 1000) -> QSize:
    """Returns a size with `extent` on the axis (0 for width, 1 for height) and `other` on the other one."""
    return QSize(extent, other) if axis == 0 else QSize(other, extent)


def _count(grid_size: GridSize, axis: int) -> int:
    return grid_size.columns if axis == 0 else grid_size.rows


AXES = {0: COLUMN_BOUNDARIES, 1: ROW_BOUNDARIES}


class PanelSizeClassTest(IntraPaintTestCase):
    """Tests grid_size_for, GridSizeTracker, orientation_for_dock and choose_layout."""

    def test_cell_boundaries(self) -> None:
        """Columns split at 260 and 420 px of width, rows at 170 and 320 px of height."""
        self.assertEqual(COLUMN_BOUNDARIES, (260, 420))
        self.assertEqual(ROW_BOUNDARIES, (170, 320))
        for axis, (first_end, second_end) in AXES.items():
            for extent, cells in ((0, 1), (first_end - 1, 1), (first_end, 2), (second_end, 2), (second_end + 1, 3),
                                  (10000, 3)):
                with self.subTest(axis=axis, extent=extent):
                    self.assertEqual(_count(grid_size_for(_size(axis, extent)), axis), cells)

    def test_named_classes(self) -> None:
        """The redesign's six named classes map to grid sizes, and `constrained` reads their short axis."""
        cases = {
            (Orientation.SIDE, QSize(200, 600)): (GridSize(1, 3), 1),
            (Orientation.SIDE, QSize(340, 600)): (GridSize(2, 3), 2),
            (Orientation.SIDE, QSize(500, 600)): (GridSize(3, 3), 3),
            (Orientation.STRIP, QSize(1200, 120)): (GridSize(3, 1), 1),
            (Orientation.STRIP, QSize(1200, 240)): (GridSize(3, 2), 2),
            (Orientation.STRIP, QSize(1200, 400)): (GridSize(3, 3), 3),
        }
        for (orientation, size), (grid_size, constrained) in cases.items():
            with self.subTest(orientation=orientation, size=size):
                self.assertEqual(grid_size_for(size), grid_size)
                self.assertEqual(grid_size.constrained(orientation), constrained)

    def test_invalid_size(self) -> None:
        """Counts outside 1 through 3 raise ValueError."""
        for columns, rows in ((0, 1), (1, 0), (4, 1), (1, 4)):
            with self.subTest(columns=columns, rows=rows):
                with self.assertRaises(ValueError):
                    GridSize(columns, rows)

    def test_orientation_from_dock(self) -> None:
        """Left and right areas are side panels, top and bottom are strips, and floating docks use aspect ratio."""
        area = Qt.DockWidgetArea
        size = QSize(100, 100)
        self.assertEqual(orientation_for_dock(area.LeftDockWidgetArea, False, size), Orientation.SIDE)
        self.assertEqual(orientation_for_dock(area.RightDockWidgetArea, False, size), Orientation.SIDE)
        self.assertEqual(orientation_for_dock(area.TopDockWidgetArea, False, size), Orientation.STRIP)
        self.assertEqual(orientation_for_dock(area.BottomDockWidgetArea, False, size), Orientation.STRIP)
        self.assertEqual(orientation_for_dock(area.NoDockWidgetArea, True, QSize(200, 201)), Orientation.SIDE)
        self.assertEqual(orientation_for_dock(area.NoDockWidgetArea, True, QSize(200, 200)), Orientation.STRIP)
        self.assertEqual(orientation_for_dock(area.NoDockWidgetArea, True, QSize(300, 200)), Orientation.STRIP)

    def test_hysteresis_in_both_directions(self) -> None:
        """Each axis holds its count until the extent is more than HYSTERESIS pixels past the count's range, growing
        or shrinking, and changing one axis leaves the other alone."""
        for axis, (first_end, second_end) in AXES.items():
            with self.subTest(axis=axis):
                tracker = GridSizeTracker()
                self.assertTrue(tracker.update(_size(axis, first_end - 20)))
                self.assertEqual(_count(tracker.grid_size, axis), 1)
                # Growing: 1 -> 2 needs first_end + HYSTERESIS.
                self.assertFalse(tracker.update(_size(axis, first_end + HYSTERESIS - 1)))
                self.assertTrue(tracker.update(_size(axis, first_end + HYSTERESIS)))
                self.assertEqual(_count(tracker.grid_size, axis), 2)
                # Shrinking back: 2 holds down to first_end - HYSTERESIS.
                self.assertFalse(tracker.update(_size(axis, first_end - HYSTERESIS)))
                self.assertTrue(tracker.update(_size(axis, first_end - HYSTERESIS - 1)))
                self.assertEqual(_count(tracker.grid_size, axis), 1)
                # 2 <-> 3.
                tracker.update(_size(axis, second_end - 10))
                self.assertEqual(_count(tracker.grid_size, axis), 2)
                self.assertFalse(tracker.update(_size(axis, second_end + HYSTERESIS)))
                self.assertTrue(tracker.update(_size(axis, second_end + HYSTERESIS + 1)))
                self.assertEqual(_count(tracker.grid_size, axis), 3)
                self.assertFalse(tracker.update(_size(axis, second_end - HYSTERESIS + 1)))
                self.assertTrue(tracker.update(_size(axis, second_end - HYSTERESIS)))
                self.assertEqual(_count(tracker.grid_size, axis), 2)
                # The other axis stayed at 3 throughout:
                self.assertEqual(_count(tracker.grid_size, 1 - axis), 3)

    def test_large_jumps_skip_counts(self) -> None:
        """A drag from 1 column straight past 420 px lands on 3."""
        tracker = GridSizeTracker()
        tracker.update(QSize(200, 500))
        tracker.update(QSize(600, 500))
        self.assertEqual(tracker.grid_size, GridSize(3, 3))

    def test_choose_largest_fitting_layout(self) -> None:
        """The largest declared layout that fits wins, so sizes without their own layout reuse a smaller one."""
        layouts = (GridSize(1, 1), GridSize(2, 1), GridSize(3, 1), GridSize(2, 2))
        cases = {GridSize(1, 3): GridSize(1, 1), GridSize(3, 1): GridSize(3, 1), GridSize(2, 3): GridSize(2, 2),
                 GridSize(3, 3): GridSize(2, 2)}
        for available, expected in cases.items():
            with self.subTest(available=str(available)):
                self.assertEqual(choose_layout(available, layouts, Orientation.STRIP), expected)

    def test_tie_break_by_orientation(self) -> None:
        """Between equal areas, strips take more columns and side panels more rows."""
        layouts = (GridSize(1, 1), GridSize(1, 2), GridSize(2, 1))
        self.assertEqual(choose_layout(GridSize(2, 2), layouts, Orientation.STRIP), GridSize(2, 1))
        self.assertEqual(choose_layout(GridSize(2, 2), layouts, Orientation.SIDE), GridSize(1, 2))

    def test_fallback_when_nothing_fits(self) -> None:
        """With no layout that fits, the smallest wins. No declared layouts gives None."""
        layouts = (GridSize(3, 1), GridSize(1, 2), GridSize(2, 2))
        self.assertEqual(choose_layout(GridSize(1, 1), layouts, Orientation.SIDE), GridSize(1, 2))
        self.assertEqual(choose_layout(GridSize(1, 1), layouts, Orientation.STRIP), GridSize(1, 2))
        self.assertIsNone(choose_layout(GridSize(3, 3), (), Orientation.SIDE))
