"""Tests the fit planner with a fake measure, orientation from a dock's area, the widget helpers that bind the
planner to real content, and field width caps."""
import sys
import warnings
from typing import Sequence

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QPushButton, QVBoxLayout, QWidget

from src.ui.layout.panel_fit import (FIELD_MAX_WIDTH, HYSTERESIS, REQUIRED, FitItem, FitPlanner, Orientation,
                                     Placement, base_placement, field_width_cap, fresh_minimum_size,
                                     orientation_for_dock, plan_fit, plan_orientation, set_field_width_cap)
from test.base_test_case import IntraPaintTestCase
from test.ui.panel_capture import find_arrangement_problems

app = QApplication.instance() or QApplication(sys.argv)

SIDE = Orientation.SIDE
STRIP = Orientation.STRIP


class StackedContent:
    """Fake content that stacks its items' forms along the scroll axis, like a side panel's column.

    `forms[i][f]` is the size item i adds in form f. The need is the widest item across, and the sum along the
    scroll axis.
    """

    def __init__(self, orientation: Orientation, *forms: Sequence[tuple[int, int]]) -> None:
        self.orientation = orientation
        self.forms = forms
        self.calls = 0

    @property
    def items(self) -> list[FitItem]:
        """Required items, one per entry, with as many forms as given."""
        return [FitItem(REQUIRED, len(forms)) for forms in self.forms]

    def measure(self, placement: Placement) -> QSize:
        """Returns the stacked size of the placed forms."""
        self.calls += 1
        cross = 0
        along = 0
        for forms, form in zip(self.forms, placement):
            if form is None:
                continue
            item_cross, item_along = forms[form]
            cross = max(cross, item_cross)
            along += item_along
        return QSize(cross, along) if self.orientation == SIDE else QSize(along, cross)


def _side(cross: int, along: int) -> QSize:
    return QSize(cross, along)


class PlanFitTest(IntraPaintTestCase):
    """Tests plan_fit and base_placement."""

    def test_required_items_stay_in_their_smallest_form_when_nothing_fits(self) -> None:
        """Required items are never left out, and take their smallest form when no larger one fits across."""
        content = StackedContent(SIDE, [(300, 50), (100, 50)], [(40, 20)])
        items = content.items
        self.assertEqual(base_placement(items), (1, 0))
        self.assertEqual(plan_fit(items, _side(50, 10), SIDE, content.measure), (1, 0))

    def test_larger_form_that_adds_no_overflow_is_taken(self) -> None:
        """When content is already wider than the panel, a larger form no wider than that is still taken."""
        content = StackedContent(SIDE, [(300, 50), (100, 50)], [(400, 20)])
        self.assertEqual(plan_fit(content.items, _side(50, 10), SIDE, content.measure), (0, 0))

    def test_required_forms_are_judged_across_only(self) -> None:
        """A required item's larger form is taken when it fits across, even if it then scrolls."""
        content = StackedContent(SIDE, [(200, 500), (100, 50)])
        self.assertEqual(plan_fit(content.items, _side(250, 100), SIDE, content.measure), (0,))
        self.assertEqual(plan_fit(content.items, _side(150, 1000), SIDE, content.measure), (1,))

    def test_optional_items_need_room_on_both_axes(self) -> None:
        """An optional item shows in its largest form that fits without scrolling, and is left out otherwise."""
        content = StackedContent(SIDE, [(100, 100)], [(200, 80), (120, 40)])
        items = [FitItem(REQUIRED), FitItem(1, 2)]
        cases = {_side(300, 300): (0, 0), _side(150, 300): (0, 1), _side(300, 150): (0, 1), _side(300, 120): (0, None),
                 _side(110, 300): (0, None)}
        for available, expected in cases.items():
            with self.subTest(available=available):
                self.assertEqual(plan_fit(items, available, SIDE, content.measure), expected)

    def test_strip_scrolls_along_its_width(self) -> None:
        """In a strip, the cross axis is the height, so a required form is judged by height only."""
        content = StackedContent(STRIP, [(200, 300), (100, 50)], [(80, 100)])
        items = [FitItem(REQUIRED, 2), FitItem(1)]
        self.assertEqual(plan_fit(items, QSize(100, 250), STRIP, content.measure), (0, None))
        self.assertEqual(plan_fit(items, QSize(1000, 150), STRIP, content.measure), (1, 0))

    def test_fill_order_follows_priority_then_declaration(self) -> None:
        """Lower priorities are placed first, ties go in declaration order, and a later item that fits is still
        placed after an earlier one didn't."""
        content = StackedContent(SIDE, [(100, 60)], [(100, 60)], [(100, 60)], [(100, 20)])
        items = [FitItem(2), FitItem(1), FitItem(1), FitItem(3)]
        self.assertEqual(plan_fit(items, _side(200, 60), SIDE, content.measure), (None, 0, None, None))
        self.assertEqual(plan_fit(items, _side(200, 120), SIDE, content.measure), (None, 0, 0, None))
        self.assertEqual(plan_fit(items, _side(200, 140), SIDE, content.measure), (None, 0, 0, 0))

    def test_optional_item_that_adds_no_scrolling_shows_while_required_content_scrolls(self) -> None:
        """When required content already overflows along the scroll axis, an optional item that adds nothing there
        still shows, and one that adds to it is left out."""
        content = StackedContent(SIDE, [(100, 500)], [(80, 0)], [(80, 10)])
        items = [FitItem(REQUIRED), FitItem(1), FitItem(1)]
        self.assertEqual(plan_fit(items, _side(200, 300), SIDE, content.measure), (0, 0, None))

    def test_hysteresis_in_both_directions(self) -> None:
        """A better placement replaces the current one only once it fits with HYSTERESIS pixels to spare, and the
        current one holds until it no longer fits."""
        content = StackedContent(SIDE, [(100, 100)], [(100, 100)])
        items = [FitItem(REQUIRED), FitItem(1)]
        current = plan_fit(items, _side(200, 150), SIDE, content.measure)
        self.assertEqual(current, (0, None))
        # Growing: the optional item needs 200 px, and appears from 200 + HYSTERESIS.
        current = plan_fit(items, _side(200, 200 + HYSTERESIS - 1), SIDE, content.measure, current)
        self.assertEqual(current, (0, None))
        current = plan_fit(items, _side(200, 200 + HYSTERESIS), SIDE, content.measure, current)
        self.assertEqual(current, (0, 0))
        # Shrinking: it stays down to 200, and leaves below that.
        current = plan_fit(items, _side(200, 200), SIDE, content.measure, current)
        self.assertEqual(current, (0, 0))
        current = plan_fit(items, _side(200, 199), SIDE, content.measure, current)
        self.assertEqual(current, (0, None))

    def test_current_placement_that_no_longer_fits_does_not_hold(self) -> None:
        """Within HYSTERESIS of a better placement, the current one still gives way once it overflows where the better
        one doesn't, as when an item's forms differ in shape."""
        # A wide, short form and a narrow, tall one, like a preview beside or below the fields:
        content = StackedContent(SIDE, [(100, 100)], [(300, 20), (100, 100)])
        items = [FitItem(REQUIRED), FitItem(1, 2)]
        current = plan_fit(items, _side(100, 300), SIDE, content.measure)
        self.assertEqual(current, (0, 1))
        # The wide form fits with less than HYSTERESIS to spare, and the tall one no longer fits:
        self.assertEqual(plan_fit(items, _side(300 + HYSTERESIS - 1, 150), SIDE, content.measure, current), (0, 0))

    def test_without_current_placement_there_is_no_hysteresis(self) -> None:
        """The first plan, or one after the items changed, takes whatever fits."""
        content = StackedContent(SIDE, [(100, 100)], [(100, 100)])
        items = [FitItem(REQUIRED), FitItem(1)]
        self.assertEqual(plan_fit(items, _side(200, 200), SIDE, content.measure), (0, 0))
        self.assertEqual(plan_fit(items, _side(200, 200), SIDE, content.measure, (0,)), (0, 0))

    def test_measures_each_placement_once(self) -> None:
        """Planning with hysteresis reuses measurements of placements it already tried."""
        content = StackedContent(SIDE, [(100, 100), (50, 50)], [(100, 100)], [(100, 100)])
        items = [FitItem(REQUIRED, 2), FitItem(1), FitItem(1)]
        current = plan_fit(items, _side(200, 150), SIDE, content.measure)
        content.calls = 0
        plan_fit(items, _side(200, 400), SIDE, content.measure, current)
        # Base, required upgrade, then one trial per optional item in each of two passes, minus repeats:
        self.assertLessEqual(content.calls, 6)

    def test_invalid_items(self) -> None:
        """Negative priorities and form counts below one raise ValueError."""
        for priority, form_count in ((-1, 1), (0, 0), (2, -1)):
            with self.subTest(priority=priority, form_count=form_count):
                with self.assertRaises(ValueError):
                    FitItem(priority, form_count)


class PlanOrientationTest(IntraPaintTestCase):
    """Tests plan_orientation with fake content that lays out differently in each orientation."""

    def _measure(self, side: StackedContent, strip: StackedContent):
        return lambda orientation, placement: (side if orientation == SIDE else strip).measure(placement)

    def test_preferred_orientation_holds_while_it_fits(self) -> None:
        """With the same placement fitting both ways, the preferred orientation wins, even if the other one would use
        larger forms."""
        side = StackedContent(SIDE, [(200, 50), (100, 50)])
        strip = StackedContent(STRIP, [(40, 300), (40, 100)])
        items = [FitItem(REQUIRED, 2)]
        orientation, placement = plan_orientation(items, QSize(150, 400), SIDE, self._measure(side, strip))
        self.assertEqual((orientation, placement), (SIDE, (1,)))

    def test_orientation_that_avoids_overflow_wins(self) -> None:
        """A tall, narrow space in a strip's dock lays out as a side panel when only that fits."""
        # 150 x 300 as a side panel, and 300 x 150 as a strip:
        side = StackedContent(SIDE, [(150, 300)])
        strip = StackedContent(STRIP, [(150, 300)])
        items = [FitItem(REQUIRED)]
        self.assertEqual(plan_orientation(items, QSize(200, 900), STRIP, self._measure(side, strip))[0], SIDE)
        self.assertEqual(plan_orientation(items, QSize(900, 200), STRIP, self._measure(side, strip))[0], STRIP)

    def test_orientation_that_shows_more_optional_items_wins(self) -> None:
        """When both fit, the orientation that leaves fewer optional items out wins over the preferred one."""
        side = StackedContent(SIDE, [(100, 100)], [(100, 100)])
        strip = StackedContent(STRIP, [(100, 100)], [(100, 100)])
        items = [FitItem(REQUIRED), FitItem(1)]
        orientation, placement = plan_orientation(items, QSize(1000, 150), SIDE, self._measure(side, strip))
        self.assertEqual((orientation, placement), (STRIP, (0, 0)))

    def test_switching_orientation_needs_room_to_spare(self) -> None:
        """Another orientation replaces the current one only once it also wins with HYSTERESIS pixels to spare."""
        # 100 x 200 as a side panel, and 150 x 100 as a strip:
        side = StackedContent(SIDE, [(100, 200)])
        strip = StackedContent(STRIP, [(100, 150)])
        items = [FitItem(REQUIRED)]
        measure = self._measure(side, strip)
        current = plan_orientation(items, QSize(500, 150), SIDE, measure)
        self.assertEqual(current[0], STRIP)
        current = plan_orientation(items, QSize(100, 200), SIDE, measure, current)
        self.assertEqual(current[0], SIDE)
        self.assertEqual(plan_orientation(items, QSize(150 + HYSTERESIS - 1, 199), SIDE, measure, current)[0], SIDE)
        self.assertEqual(plan_orientation(items, QSize(150 + HYSTERESIS, 199), SIDE, measure, current)[0], STRIP)


class OrientationTest(IntraPaintTestCase):
    """Tests orientation_for_dock."""

    def test_orientation_from_dock(self) -> None:
        """Left and right areas are side panels, top and bottom are strips, and floating docks use aspect ratio."""
        area = Qt.DockWidgetArea
        size = QSize(100, 100)
        self.assertEqual(orientation_for_dock(area.LeftDockWidgetArea, False, size), SIDE)
        self.assertEqual(orientation_for_dock(area.RightDockWidgetArea, False, size), SIDE)
        self.assertEqual(orientation_for_dock(area.TopDockWidgetArea, False, size), STRIP)
        self.assertEqual(orientation_for_dock(area.BottomDockWidgetArea, False, size), STRIP)
        self.assertEqual(orientation_for_dock(area.NoDockWidgetArea, True, QSize(200, 201)), SIDE)
        self.assertEqual(orientation_for_dock(area.NoDockWidgetArea, True, QSize(200, 200)), STRIP)
        self.assertEqual(orientation_for_dock(area.NoDockWidgetArea, True, QSize(300, 200)), STRIP)

    def test_floating_hysteresis(self) -> None:
        """A floating dock keeps its orientation until the other axis is longer by more than HYSTERESIS pixels."""
        floating = Qt.DockWidgetArea.NoDockWidgetArea
        self.assertEqual(orientation_for_dock(floating, True, QSize(200 + HYSTERESIS, 200), SIDE), SIDE)
        self.assertEqual(orientation_for_dock(floating, True, QSize(200 + HYSTERESIS + 1, 200), SIDE), STRIP)
        self.assertEqual(orientation_for_dock(floating, True, QSize(200, 200 + HYSTERESIS), STRIP), STRIP)
        self.assertEqual(orientation_for_dock(floating, True, QSize(200, 200 + HYSTERESIS + 1), STRIP), SIDE)
        self.assertEqual(orientation_for_dock(Qt.DockWidgetArea.TopDockWidgetArea, False, QSize(100, 900), SIDE),
                         STRIP)


class _Column(QWidget):
    """Content for FitPlanner: a required field, and an optional wide button that also takes focus."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.field = QLineEdit()
        self.extra = QPushButton('A button label far wider than the field')
        layout.addWidget(self.field)
        layout.addWidget(self.extra)
        self.applied: list[tuple[Orientation, Placement]] = []

    def apply(self, orientation: Orientation, placement: Placement) -> None:
        """Shows the button when its item is placed."""
        self.applied.append((orientation, placement))
        self.extra.setVisible(placement[1] is not None)


class FitPlannerTest(IntraPaintTestCase):
    """Tests fresh_minimum_size and FitPlanner on real widgets."""

    def setUp(self) -> None:
        super().setUp()
        self.column = _Column()
        self.outer = QWidget()
        outer_layout = QVBoxLayout(self.outer)
        outer_layout.addWidget(self.column)
        self.outer.show()
        outer_layout.activate()
        self.planner = FitPlanner([FitItem(REQUIRED), FitItem(1)], self.column.apply,
                                  lambda: fresh_minimum_size(self.column))

    def tearDown(self) -> None:
        self.outer.hide()
        super().tearDown()

    def test_fresh_minimum_size_counts_nested_changes(self) -> None:
        """A change two levels down counts at once, without running the event loop."""
        wide = fresh_minimum_size(self.outer)
        self.column.extra.hide()
        narrow = fresh_minimum_size(self.outer)
        self.assertLess(narrow.width(), wide.width())
        self.column.extra.show()
        self.assertEqual(fresh_minimum_size(self.outer), wide)

    def test_update_plans_applies_and_skips_unchanged_inputs(self) -> None:
        """An update applies its plan, a repeat with the same inputs does nothing, and `force` plans again."""
        wide = QSize(1000, 1000)
        self.assertTrue(self.planner.update(SIDE, wide))
        self.assertEqual(self.planner.placement, (0, 0))
        self.assertFalse(self.column.extra.isHidden())
        count = len(self.column.applied)
        self.assertFalse(self.planner.update(SIDE, wide))
        self.assertEqual(len(self.column.applied), count)
        self.assertFalse(self.planner.update(SIDE, wide, force=True))
        self.assertGreater(len(self.column.applied), count)
        self.assertTrue(self.planner.update(SIDE, QSize(self.column.field.minimumSizeHint().width(), 1000)))
        self.assertEqual(self.planner.placement, (0, None))
        self.assertTrue(self.column.extra.isHidden())

    def test_focus_survives_planning(self) -> None:
        """Trial placements that hide the focused widget don't take its focus away."""
        # The offscreen platform activates no window on its own, and Qt has no undeprecated way to do it directly:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            QApplication.setActiveWindow(self.outer)
        self.planner.update(SIDE, QSize(1000, 1000))
        self.column.extra.setFocus()
        self.assertIs(QApplication.focusWidget(), self.column.extra)
        self.planner.update(SIDE, QSize(1000, 900))
        self.assertIs(QApplication.focusWidget(), self.column.extra)

    def test_base_size_then_update_replans(self) -> None:
        """base_size measures required items alone and leaves them applied, and the next update restores the plan."""
        wide = QSize(1000, 1000)
        self.planner.update(SIDE, wide)
        base = self.planner.base_size(SIDE)
        self.assertTrue(self.column.extra.isHidden())
        self.assertEqual(base, fresh_minimum_size(self.column))
        self.planner.update(SIDE, wide)
        self.assertFalse(self.column.extra.isHidden())


class FieldWidthCapTest(IntraPaintTestCase):
    """Tests field width caps and the stretched-field check that reads them."""

    def setUp(self) -> None:
        super().setUp()
        self.panel = QWidget()
        self.field = QComboBox(self.panel)
        self.field.setGeometry(0, 0, FIELD_MAX_WIDTH + 100, 24)
        self.panel.resize(FIELD_MAX_WIDTH + 100, 24)

    def _stretched(self) -> list[str]:
        return [problem for problem in find_arrangement_problems(self.panel) if problem.startswith('stretched')]

    def test_default_cap(self) -> None:
        """A field with no cap of its own gets FIELD_MAX_WIDTH, and is stretched past it."""
        self.assertEqual(FIELD_MAX_WIDTH, field_width_cap(self.field))
        self.assertEqual(1, len(self._stretched()))

    def test_own_cap(self) -> None:
        """A field's own cap replaces FIELD_MAX_WIDTH."""
        set_field_width_cap(self.field, FIELD_MAX_WIDTH + 200)
        self.assertEqual(FIELD_MAX_WIDTH + 200, field_width_cap(self.field))
        self.assertEqual([], self._stretched())
        set_field_width_cap(self.field, FIELD_MAX_WIDTH + 50)
        self.assertEqual(1, len(self._stretched()))

    def test_uncapped(self) -> None:
        """A field set to no cap may stretch to any width."""
        set_field_width_cap(self.field, None)
        self.assertIsNone(field_width_cap(self.field))
        self.assertEqual([], self._stretched())
