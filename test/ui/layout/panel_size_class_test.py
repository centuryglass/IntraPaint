"""Tests the orientation and size class calculator: boundaries, hysteresis in both directions for both orientations,
and orientation from a dock's area. Also tests grid sizes, their per-axis hysteresis, and layout choice."""
from PySide6.QtCore import QSize, Qt

from src.ui.layout.panel_size_class import (GRID_COLUMN_WIDTH, GRID_ROW_HEIGHT, HYSTERESIS, GridSize,
                                            GridSizeTracker, Orientation, SizeClass, SizeClassTracker, choose_layout,
                                            grid_size_for, orientation_for_dock, size_class_for)
from test.base_test_case import IntraPaintTestCase


def _size(orientation: Orientation, extent: int) -> QSize:
    return QSize(extent, 500) if orientation == Orientation.SIDE else QSize(500, extent)


class PanelSizeClassTest(IntraPaintTestCase):
    """Tests size_class_for, orientation_for_dock and SizeClassTracker."""

    def test_class_boundaries(self) -> None:
        """Side panels split at 260 and 420 by width, strips at 170 and 320 by height."""
        cases = {Orientation.SIDE: (259, 260, 420, 421), Orientation.STRIP: (169, 170, 320, 321)}
        for orientation, (compact, regular_low, regular_high, wide) in cases.items():
            with self.subTest(orientation=orientation):
                self.assertEqual(size_class_for(orientation, _size(orientation, compact)), SizeClass.COMPACT)
                self.assertEqual(size_class_for(orientation, _size(orientation, regular_low)), SizeClass.REGULAR)
                self.assertEqual(size_class_for(orientation, _size(orientation, regular_high)), SizeClass.REGULAR)
                self.assertEqual(size_class_for(orientation, _size(orientation, wide)), SizeClass.WIDE)

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
        """A class holds until the extent is more than HYSTERESIS pixels past its edge, growing or shrinking."""
        edges = {Orientation.SIDE: (260, 420), Orientation.STRIP: (170, 320)}
        for orientation, (compact_end, regular_end) in edges.items():
            with self.subTest(orientation=orientation):
                tracker = SizeClassTracker(orientation, _size(orientation, compact_end - 20))
                self.assertEqual(tracker.size_class, SizeClass.COMPACT)
                # Growing: COMPACT -> REGULAR needs compact_end + HYSTERESIS.
                self.assertFalse(tracker.update(orientation, _size(orientation, compact_end + HYSTERESIS - 1)))
                self.assertEqual(tracker.size_class, SizeClass.COMPACT)
                self.assertTrue(tracker.update(orientation, _size(orientation, compact_end + HYSTERESIS)))
                self.assertEqual(tracker.size_class, SizeClass.REGULAR)
                # Shrinking back: REGULAR holds down to compact_end - HYSTERESIS.
                self.assertFalse(tracker.update(orientation, _size(orientation, compact_end - HYSTERESIS)))
                self.assertEqual(tracker.size_class, SizeClass.REGULAR)
                self.assertTrue(tracker.update(orientation, _size(orientation, compact_end - HYSTERESIS - 1)))
                self.assertEqual(tracker.size_class, SizeClass.COMPACT)
                # REGULAR <-> WIDE.
                tracker.update(orientation, _size(orientation, regular_end - 10))
                self.assertEqual(tracker.size_class, SizeClass.REGULAR)
                self.assertFalse(tracker.update(orientation, _size(orientation, regular_end + HYSTERESIS)))
                self.assertTrue(tracker.update(orientation, _size(orientation, regular_end + HYSTERESIS + 1)))
                self.assertEqual(tracker.size_class, SizeClass.WIDE)
                self.assertFalse(tracker.update(orientation, _size(orientation, regular_end - HYSTERESIS + 1)))
                self.assertTrue(tracker.update(orientation, _size(orientation, regular_end - HYSTERESIS)))
                self.assertEqual(tracker.size_class, SizeClass.REGULAR)

    def test_large_jumps_skip_classes(self) -> None:
        """A drag from COMPACT straight to WIDE lands in WIDE."""
        tracker = SizeClassTracker(Orientation.SIDE, QSize(200, 500))
        tracker.update(Orientation.SIDE, QSize(600, 500))
        self.assertEqual(tracker.size_class, SizeClass.WIDE)

    def test_orientation_change_reclassifies(self) -> None:
        """Changing orientation reports a change and classifies the size without history."""
        tracker = SizeClassTracker(Orientation.SIDE, QSize(300, 500))
        self.assertTrue(tracker.update(Orientation.STRIP, QSize(300, 500)))
        self.assertEqual(tracker.orientation, Orientation.STRIP)
        self.assertEqual(tracker.size_class, SizeClass.WIDE)


class GridSizeTest(IntraPaintTestCase):
    """Tests grid_size_for, GridSizeTracker and choose_layout."""

    def test_cell_boundaries(self) -> None:
        """n cells fit from n units on each axis, clamped to 1 through 3."""
        for extent, cells in ((0, 1), (2 * GRID_COLUMN_WIDTH - 1, 1), (2 * GRID_COLUMN_WIDTH, 2),
                              (3 * GRID_COLUMN_WIDTH - 1, 2), (3 * GRID_COLUMN_WIDTH, 3), (10000, 3)):
            with self.subTest(width=extent):
                self.assertEqual(grid_size_for(QSize(extent, 0)), GridSize(cells, 1))
        for extent, cells in ((2 * GRID_ROW_HEIGHT - 1, 1), (2 * GRID_ROW_HEIGHT, 2), (3 * GRID_ROW_HEIGHT, 3)):
            with self.subTest(height=extent):
                self.assertEqual(grid_size_for(QSize(0, extent)), GridSize(1, cells))

    def test_invalid_size(self) -> None:
        """Counts outside 1 through 3 raise ValueError."""
        for columns, rows in ((0, 1), (1, 0), (4, 1), (1, 4)):
            with self.subTest(columns=columns, rows=rows):
                with self.assertRaises(ValueError):
                    GridSize(columns, rows)

    def test_hysteresis_on_each_axis(self) -> None:
        """Each axis holds its count until the extent is more than HYSTERESIS pixels past the boundary, and changing
        one axis leaves the other alone."""
        for axis, unit in ((0, GRID_COLUMN_WIDTH), (1, GRID_ROW_HEIGHT)):

            def size(extent: int, other: int = 0) -> QSize:
                return QSize(extent, other) if axis == 0 else QSize(other, extent)

            def count(grid_size: GridSize) -> int:
                return grid_size.columns if axis == 0 else grid_size.rows

            with self.subTest(axis=axis):
                tracker = GridSizeTracker()
                self.assertTrue(tracker.update(size(unit, 10000)))
                self.assertEqual(count(tracker.grid_size), 1)
                self.assertFalse(tracker.update(size(2 * unit + HYSTERESIS - 1, 10000)))
                self.assertTrue(tracker.update(size(2 * unit + HYSTERESIS, 10000)))
                self.assertEqual(count(tracker.grid_size), 2)
                self.assertFalse(tracker.update(size(2 * unit - HYSTERESIS, 10000)))
                self.assertTrue(tracker.update(size(2 * unit - HYSTERESIS - 1, 10000)))
                self.assertEqual(count(tracker.grid_size), 1)
                # The other axis stayed at 3 throughout:
                other = tracker.grid_size.rows if axis == 0 else tracker.grid_size.columns
                self.assertEqual(other, 3)

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
