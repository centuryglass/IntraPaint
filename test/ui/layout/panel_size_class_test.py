"""Tests the orientation and size class calculator: boundaries, hysteresis in both directions for both orientations,
and orientation from a dock's area."""
from PySide6.QtCore import QSize, Qt

from src.ui.layout.panel_size_class import (HYSTERESIS, Orientation, SizeClass, SizeClassTracker,
                                            orientation_for_dock, size_class_for)
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
