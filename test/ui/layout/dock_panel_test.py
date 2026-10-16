"""Tests DockPanel: priority placement at each count along the constrained axis, the "More" overflow, re-arranging
without rebuilding widgets, scrolling, and a layout snapshot at each of the six named grid sizes."""
import os
import sys

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QLineEdit, QPushButton, QScrollArea, QSlider, QWidget

from src.ui.layout.dock_panel import P1, P2, P3, DockPanel, PanelLayout
from src.ui.layout.panel_size_class import (GridSize, Orientation, STRIP_SECTION_MAX_WIDTH,
                                            STRIP_SECTION_MIN_WIDTH)
from test.base_test_case import IntraPaintTestCase, TEST_RESOURCE_DIR
from test.ui.ui_capture import PanelHost, find_layout_problems

app = QApplication.instance() or QApplication(sys.argv)

SNAPSHOT_DIR = os.path.join(TEST_RESOURCE_DIR, 'layout_snapshots')
# One representative size per count along the constrained axis, per orientation:
SIDE_SIZES = {1: QSize(200, 600), 2: QSize(340, 600), 3: QSize(500, 600)}
STRIP_SIZES = {1: QSize(900, 120), 2: QSize(900, 240), 3: QSize(900, 400)}


class SamplePanel(DockPanel):
    """Two sections with one control at each priority, plus a P1-only section."""

    def build(self, ui: PanelLayout) -> None:
        self.size_slider = QSlider()
        self.name_field = QLineEdit()
        self.flag = QCheckBox('flag')
        self.extra = QLineEdit()
        self.only_extra = QCheckBox('only extra')
        stroke = ui.section('Stroke')
        stroke.add(self.size_slider, P1)
        stroke.add(self.name_field, P2)
        stroke.add(self.flag, P3)
        advanced = ui.section('Advanced')
        advanced.add(self.extra, P3)
        advanced.add(self.only_extra, P3)


class OversizedPanel(DockPanel):
    """A tall column of P1 fields and a P1 button wider than a compact side panel, so neither fits by priority alone."""

    def build(self, ui: PanelLayout) -> None:
        fields = ui.section('Fields')
        for i in range(6):
            fields.add(QLineEdit(str(i)), P1)
        ui.section('Wide').add(QPushButton('A button label far wider than a compact side panel'), P1)


class DockPanelTest(IntraPaintTestCase):
    """Tests DockPanel with a fake host that calls set_host_facts."""

    def setUp(self) -> None:
        super().setUp()
        self.panel = SamplePanel()

    def _place(self, widget: QWidget) -> str:
        if widget in self.panel.overflow_widgets:
            return 'more'
        return 'section'

    def test_priority_placement_per_constrained_count(self) -> None:
        """P1 always stays in its section, P2 from 2 cells along the constrained axis, P3 only at 3, in both
        orientations."""
        expected = {
            1: ('section', 'more', 'more'),
            2: ('section', 'section', 'more'),
            3: ('section', 'section', 'section'),
        }
        for orientation, sizes in ((Orientation.SIDE, SIDE_SIZES), (Orientation.STRIP, STRIP_SIZES)):
            for count, size in sizes.items():
                with self.subTest(orientation=orientation, count=count):
                    self.panel.set_host_facts(orientation, size)
                    grid_size = self.panel.grid_size
                    assert grid_size is not None
                    self.assertEqual(grid_size.constrained(orientation), count)
                    placed = (self._place(self.panel.size_slider), self._place(self.panel.name_field),
                              self._place(self.panel.flag))
                    self.assertEqual(placed, expected[count])

    def test_overflowed_controls_stay_usable(self) -> None:
        """An overflowed control is still parented to the panel, still enabled, and keeps its value."""
        self.panel.set_host_facts(Orientation.SIDE, SIDE_SIZES[1])
        self.panel.name_field.setText('kept')
        self.panel.show()
        more_button = self.panel.header.more_button
        content = self.panel.header.popover.content
        self.assertFalse(more_button.isHidden())
        self.assertIsNotNone(content)
        self.assertTrue(content.isAncestorOf(self.panel.name_field))
        self.assertFalse(self.panel.name_field.isHidden())
        self.assertTrue(self.panel.name_field.isEnabled())
        self.panel.name_field.setText('edited')
        self.assertEqual(self.panel.name_field.text(), 'edited')

    def test_no_more_button_without_overflow(self) -> None:
        """When every control fits, the More button and popover content are gone."""
        self.panel.set_host_facts(Orientation.SIDE, SIDE_SIZES[3])
        self.panel.show()
        self.assertFalse(self.panel.header.more_button.isVisible())
        self.assertIsNone(self.panel.header.popover.content)
        self.assertEqual(self.panel.overflow_widgets, [])

    def test_section_with_no_shown_controls_is_hidden(self) -> None:
        """A section whose controls all overflowed is hidden, and its heading appears in the More area."""
        self.panel.set_host_facts(Orientation.SIDE, SIDE_SIZES[1])
        self.panel.show()
        advanced = self.panel.sections[1]
        self.assertFalse(advanced.widget.isVisibleTo(self.panel))
        self.assertFalse(advanced.overflow_title.isHidden())
        self.assertEqual(len(self.panel.overflow_widgets), 4)

    def test_host_change_keeps_widgets_and_state(self) -> None:
        """Changing orientation and class re-arranges the same widget objects, with their state intact."""
        widgets = (self.panel.size_slider, self.panel.name_field, self.panel.flag)
        self.panel.set_host_facts(Orientation.SIDE, SIDE_SIZES[3])
        self.panel.size_slider.setValue(42)
        self.panel.name_field.setText('typed')
        self.panel.flag.setChecked(True)
        for orientation, size in ((Orientation.STRIP, STRIP_SIZES[1]),
                                  (Orientation.SIDE, SIDE_SIZES[1]),
                                  (Orientation.STRIP, STRIP_SIZES[3])):
            self.panel.set_host_facts(orientation, size)
            self.assertEqual((self.panel.size_slider, self.panel.name_field, self.panel.flag), widgets)
            self.assertEqual(self.panel.size_slider.value(), 42)
            self.assertEqual(self.panel.name_field.text(), 'typed')
            self.assertTrue(self.panel.flag.isChecked())

    def test_unchanged_grid_size_does_not_rearrange(self) -> None:
        """A resize inside one grid size doesn't call arrange again, and a change on either axis does."""
        calls: list[tuple[Orientation, GridSize]] = []
        original = self.panel.arrange
        self.panel.arrange = lambda o, c: (calls.append((o, c)), original(o, c))[1]  # type: ignore[method-assign]
        self.panel.set_host_facts(Orientation.SIDE, QSize(300, 500))
        self.panel.set_host_facts(Orientation.SIDE, QSize(310, 500))
        self.assertEqual(len(calls), 1)
        self.panel.set_host_facts(Orientation.SIDE, QSize(310, 150))
        self.assertEqual(calls[-1], (Orientation.SIDE, GridSize(2, 1)))

    def test_strip_short_moves_more_button_out_of_hidden_header(self) -> None:
        """In Strip Short the header is hidden and the More button moves to the end of the row, and returns later."""
        self.panel.set_host_facts(Orientation.STRIP, STRIP_SIZES[1])
        self.panel.show()
        more_button = self.panel.header.more_button
        self.assertTrue(self.panel.header.isHidden())
        self.assertFalse(self.panel.header.isAncestorOf(more_button))
        self.assertTrue(more_button.isVisible())
        self.panel.set_host_facts(Orientation.STRIP, STRIP_SIZES[2])
        self.assertFalse(self.panel.header.isHidden())
        self.assertTrue(self.panel.header.isAncestorOf(more_button))
        self.assertTrue(more_button.isVisible())

    def test_invalid_priority(self) -> None:
        """Priorities other than P1-P3 raise ValueError."""
        with self.assertRaises(ValueError):
            self.panel.sections[0].add(QCheckBox(), 4)

    def test_content_that_cannot_shrink_scrolls_on_both_axes(self) -> None:
        """Content taller than a strip or wider than a side panel gets a scroll bar on that axis, so none is cut off."""
        panel = OversizedPanel()
        host = PanelHost(panel)
        try:
            for orientation, size in ((Orientation.STRIP, STRIP_SIZES[1]),
                                      (Orientation.SIDE, QSize(150, 600))):
                with self.subTest(orientation=orientation):
                    panel.set_host_facts(orientation, size)
                    host.capture(size)
                    scroll_area = panel.findChild(QScrollArea)
                    cross_bar = scroll_area.verticalScrollBar() if orientation == Orientation.STRIP \
                        else scroll_area.horizontalScrollBar()
                    # The bar's visibility updates on a posted event, so check what decides it: a scroll range, and
                    # a policy that lets Qt show the bar for it.
                    self.assertGreater(cross_bar.maximum(), 0)
                    policy = scroll_area.verticalScrollBarPolicy() if orientation == Orientation.STRIP \
                        else scroll_area.horizontalScrollBarPolicy()
                    self.assertNotEqual(policy, Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        finally:
            host.release()

    def test_layout_snapshots(self) -> None:
        """Where each control sits, which sections show, their geometry and any layout problems, at each of the six
        named grid sizes."""
        result: dict[str, dict] = {}
        names = {id(self.panel.size_slider): 'size', id(self.panel.name_field): 'name', id(self.panel.flag): 'flag',
                 id(self.panel.extra): 'extra', id(self.panel.only_extra): 'only_extra'}
        host = PanelHost(self.panel)
        try:
            for orientation, sizes in ((Orientation.SIDE, SIDE_SIZES), (Orientation.STRIP, STRIP_SIZES)):
                for size in sizes.values():
                    self.panel.set_host_facts(orientation, size)
                    host.capture(size)
                    shown = [s for s in self.panel.sections if not s.widget.isHidden()]
                    result[f'{orientation.value}_{self.panel.grid_size}'] = {
                        'overflow': [names[id(w)] for w in self.panel.overflow_widgets],
                        'visible_sections': [s.title for s in shown],
                        'section_geometry': {s.title: list(s.widget.geometry().getRect()) for s in shown},
                        'more_button': not self.panel.header.more_button.isHidden(),
                        'problems': find_layout_problems(self.panel),
                    }
                    if orientation == Orientation.STRIP:
                        for section in shown:
                            self.assertGreaterEqual(section.widget.width(), STRIP_SECTION_MIN_WIDTH)
                            self.assertLessEqual(section.widget.width(), STRIP_SECTION_MAX_WIDTH)
        finally:
            host.release()
        self.assert_json_matches_snapshot(result, os.path.join(SNAPSHOT_DIR, 'dock_panel_sample.json'))
