"""Tests DockPanel: placement by fit in tall, short, wide and narrow panels of both orientations, the "More" overflow,
decorative controls, control forms, re-planning without rebuilding widgets, scrolling, and a layout snapshot at each
sample size."""
import gc
import os
import sys
import weakref

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QLineEdit, QPushButton, QScrollArea, QSlider, QWidget

from src.ui.layout.dock_panel import DockPanel, PanelLayout
from src.ui.layout.panel_fit import HYSTERESIS, REQUIRED, STRIP_SECTION_MAX_WIDTH, STRIP_SECTION_MIN_WIDTH, Orientation
from src.ui.widget.panel_section import HEADER_HEIGHT
from test.base_test_case import IntraPaintTestCase, TEST_RESOURCE_DIR
from test.ui.panel_capture import PanelHost, find_layout_problems, tell_orientation

app = QApplication.instance() or QApplication(sys.argv)

SNAPSHOT_DIR = os.path.join(TEST_RESOURCE_DIR, 'layout_snapshots')
SIDE = Orientation.SIDE
STRIP = Orientation.STRIP
# Sample sizes, named by shape. Every control fits in side_tall_narrow, side_wide, strip_wide and strip_regular:
SAMPLE_SIZES = {
    'side_tall_narrow': (SIDE, QSize(200, 900)),
    'side_short': (SIDE, QSize(362, 142)),
    'side_wide': (SIDE, QSize(500, 600)),
    'strip_short': (STRIP, QSize(1400, 90)),
    'strip_wide': (STRIP, QSize(1400, 182)),
    'strip_regular': (STRIP, QSize(900, 240)),
    'strip_narrow': (STRIP, QSize(300, 400)),
    'strip_tiny': (STRIP, QSize(300, 50)),
}


class SamplePanel(DockPanel):
    """Two sections: a required slider, then optional controls in fill order across both."""

    def build(self, ui: PanelLayout) -> None:
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.name_field = QLineEdit()
        self.flag = QCheckBox('flag')
        self.extra = QLineEdit()
        self.only_extra = QCheckBox('only extra')
        stroke = ui.section('Stroke')
        stroke.add(self.size_slider, REQUIRED)
        stroke.add(self.name_field, 1)
        stroke.add(self.flag, 2)
        advanced = ui.section('Advanced')
        advanced.add(self.extra, 3)
        advanced.add(self.only_extra, 3)


class MeasureCountingPanel(SamplePanel):
    """A `SamplePanel` that counts its `measure` calls."""

    def __init__(self) -> None:
        self.measure_count = 0
        super().__init__()

    def measure(self) -> QSize:
        self.measure_count += 1
        return super().measure()


class CollapsiblePanel(DockPanel):
    """A required slider, an optional field, and a collapsible section of tall required content with a summary."""

    def build(self, ui: PanelLayout) -> None:
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.optional = QLineEdit()
        self.block = QWidget()
        self.block.setMinimumHeight(200)
        main = ui.section('Main')
        main.add(self.slider, REQUIRED)
        main.add(self.optional, 2)
        self.sampling = ui.section('Sampling', collapsible=True, priority=3)
        self.sampling.add(self.block, REQUIRED)
        self.sampling.widget.set_summary('Euler a, 30 steps')


class OversizedPanel(DockPanel):
    """A tall column of required fields and a required button wider than a narrow side panel."""

    def build(self, ui: PanelLayout) -> None:
        fields = ui.section('Fields')
        for i in range(6):
            fields.add(QLineEdit(str(i)), REQUIRED)
        ui.section('Wide').add(QPushButton('A button label far wider than a narrow side panel'), REQUIRED)


class PackedPanel(DockPanel):
    """Three sections of fixed-height content that pack into strip columns, and a trailing column."""

    def build(self, ui: PanelLayout) -> None:
        self.set_column_packing(True)
        self.blocks: list[QWidget] = []
        for title in ('First', 'Second', 'Third'):
            block = QWidget()
            block.setMinimumHeight(100)
            self.blocks.append(block)
            ui.section(title).add(block, REQUIRED)
        self.trailing_button = QPushButton('Trailing')

    def arrange(self, orientation: Orientation) -> None:
        super().arrange(orientation)
        self.trailing_layout.addWidget(self.trailing_button)
        self.set_trailing_visible(orientation == STRIP)


def _trailing_column(panel: DockPanel) -> QWidget:
    """The widget holding the trailing column's scroll area."""
    return panel.trailing_layout.parentWidget().parentWidget().parentWidget().parentWidget()


class DockPanelTest(IntraPaintTestCase):
    """Tests DockPanel with a fake host that starts it in an orientation and reports its size (`tell_orientation`)."""

    def setUp(self) -> None:
        super().setUp()
        self.panel = SamplePanel()

    def _host(self, orientation: Orientation, size: QSize, panel: DockPanel | None = None) -> None:
        panel = self.panel if panel is None else panel
        panel.resize(size)
        tell_orientation(panel, orientation, size)

    def _optional(self) -> list[QWidget]:
        return [self.panel.name_field, self.panel.flag, self.panel.extra, self.panel.only_extra]

    def test_planned_panel_is_freed_without_a_cyclic_collection(self) -> None:
        """A planned panel is freed when its last reference goes, so its C++ side is never deleted by a cyclic
        collection during an unrelated Qt call."""
        panel = SamplePanel()
        self._host(SIDE, QSize(200, 900), panel)
        panel_ref = weakref.ref(panel)
        gc.disable()
        try:
            del panel
            self.assertIsNone(panel_ref())
        finally:
            gc.enable()

    def test_roomy_panels_show_everything(self) -> None:
        """A tall, narrow side panel and a wide strip under 190 px tall have room for every control, so nothing moves
        to More."""
        for name in ('side_tall_narrow', 'side_wide', 'strip_wide'):
            with self.subTest(size=name):
                self._host(*SAMPLE_SIZES[name])
                self.assertEqual(self.panel.overflow_widgets, [])
                self.assertTrue(all(section.widget.isVisibleTo(self.panel) for section in self.panel.sections))

    def test_cramped_panels_move_optional_controls_to_more_in_fill_order(self) -> None:
        """A short side panel keeps the required slider, shows the optional controls that fit, and moves the rest to
        More in their section order."""
        self._host(*SAMPLE_SIZES['side_short'])
        overflow = self.panel.overflow_widgets
        self.assertNotIn(self.panel.size_slider, overflow)
        self.assertIn(self.panel.only_extra, overflow)
        self.assertLess(len(overflow), len(self._optional()))
        self.assertEqual(overflow, [widget for widget in self._optional() if widget in overflow])

    def test_overflowed_controls_stay_usable(self) -> None:
        """An overflowed control is still parented to the panel, still enabled, and keeps its value."""
        self._host(SIDE, QSize(340, 60))
        self.panel.name_field.setText('kept')
        self.panel.show()
        more_button = self.panel.header.more_button
        content = self.panel.header.popover.content
        self.assertFalse(more_button.isHidden())
        self.assertIsNotNone(content)
        self.assertTrue(content.isAncestorOf(self.panel.name_field))
        self.assertFalse(self.panel.name_field.isHidden())
        self.assertTrue(self.panel.name_field.isEnabled())
        self.assertEqual(self.panel.name_field.text(), 'kept')

    def test_no_more_button_without_overflow(self) -> None:
        """When every control fits, the More button and popover content are gone."""
        self._host(*SAMPLE_SIZES['side_wide'])
        self.panel.show()
        self.assertFalse(self.panel.header.more_button.isVisible())
        self.assertIsNone(self.panel.header.popover.content)

    def test_section_with_no_shown_controls_is_hidden(self) -> None:
        """A section whose controls all overflowed is hidden, and its heading appears in the More area."""
        self._host(SIDE, QSize(340, 60))
        advanced = self.panel.sections[1]
        self.assertFalse(advanced.widget.isVisibleTo(self.panel))
        self.assertFalse(advanced.overflow_title.isHidden())
        self.assertEqual(len(self.panel.overflow_widgets), 4)

    def test_host_change_keeps_widgets_and_state(self) -> None:
        """Changing orientation and size re-arranges the same widget objects, with their state intact."""
        widgets = (self.panel.size_slider, self.panel.name_field, self.panel.flag)
        self._host(*SAMPLE_SIZES['side_wide'])
        self.panel.size_slider.setValue(42)
        self.panel.name_field.setText('typed')
        self.panel.flag.setChecked(True)
        for name in ('strip_regular', 'side_short', 'strip_short', 'side_tall_narrow'):
            self._host(*SAMPLE_SIZES[name])
            self.assertEqual((self.panel.size_slider, self.panel.name_field, self.panel.flag), widgets)
            self.assertEqual(self.panel.size_slider.value(), 42)
            self.assertEqual(self.panel.name_field.text(), 'typed')
            self.assertTrue(self.panel.flag.isChecked())

    def test_unchanged_host_facts_do_not_replan(self) -> None:
        """Repeating the same size measures nothing, and a change plans again."""
        panel = MeasureCountingPanel()
        panel.set_host_facts(QSize(300, 500))
        count = panel.measure_count
        panel.set_host_facts(QSize(300, 500))
        self.assertEqual(panel.measure_count, count)
        panel.set_host_facts(QSize(310, 500))
        self.assertGreater(panel.measure_count, count)

    def test_orientation_follows_the_size_no_matter_its_area(self) -> None:
        """A panel takes the orientation its size suggests, whatever orientation the host reports: a wide space lays
        out as a strip even in a side dock, and a tall one as a side panel even in a bottom dock."""
        self._host(STRIP, QSize(1400, 182))
        self.assertEqual(self.panel.orientation, STRIP)
        self._host(STRIP, QSize(200, 900))
        self.assertEqual(self.panel.orientation, SIDE)
        self.assertEqual(self.panel.overflow_widgets, [])
        self._host(SIDE, QSize(1400, 182))
        self.assertEqual(self.panel.orientation, STRIP)
        self._host(SIDE, QSize(500, 600))
        self.assertEqual(self.panel.orientation, SIDE)

    def test_short_strip_collapses_header_into_the_row(self) -> None:
        """A strip too short for the header hides it and moves the More button to the end of the row, and both
        return once the panel is taller. Side panels never collapse their header."""
        self._host(STRIP, QSize(300, 60))
        self.panel.show()
        more_button = self.panel.header.more_button
        self.assertTrue(self.panel.header_collapsed)
        self.assertTrue(self.panel.header.isHidden())
        self.assertFalse(self.panel.header.isAncestorOf(more_button))
        self.assertTrue(more_button.isVisible())
        self._host(STRIP, QSize(300, 400))
        self.assertFalse(self.panel.header.isHidden())
        self.assertTrue(self.panel.header.isAncestorOf(more_button))
        self.assertEqual(more_button.isVisible(), len(self.panel.overflow_widgets) > 0)
        self._host(SIDE, QSize(60, 60))
        self.assertFalse(self.panel.header_collapsed)

    def test_decorative_control_hides_instead_of_moving_to_more(self) -> None:
        """A decorative control that doesn't fit is hidden in place, never added to the More popover."""
        preview = QWidget()
        preview.setMinimumSize(100, 200)

        class _Panel(DockPanel):
            def build(self, ui: PanelLayout) -> None:
                section = ui.section('Stroke')
                section.add(QSlider(Qt.Orientation.Horizontal), REQUIRED)
                section.add(preview, 1, decorative=True)

        panel = _Panel()
        self._host(SIDE, QSize(300, 900), panel)
        self.assertFalse(preview.isHidden())
        self._host(SIDE, QSize(300, 150), panel)
        self.assertTrue(preview.isHidden())
        self.assertEqual(panel.overflow_widgets, [])
        self.assertTrue(panel.sections[0].widget.isAncestorOf(preview))

    def test_control_forms(self) -> None:
        """A control with several forms takes the largest that fits, and its callback runs for it."""
        button = QPushButton('wide')
        forms: list[str] = []

        def _large() -> None:
            forms.append('large')
            button.setMinimumWidth(400)

        def _small() -> None:
            forms.append('small')
            button.setMinimumWidth(0)

        class _Panel(DockPanel):
            def build(self, ui: PanelLayout) -> None:
                ui.section('Mode').add(button, REQUIRED, forms=(_large, _small))

        panel = _Panel()
        self._host(SIDE, QSize(600, 300), panel)
        self.assertEqual(forms[-1], 'large')
        self._host(SIDE, QSize(200, 300), panel)
        self.assertEqual(forms[-1], 'small')

    def test_invalid_controls(self) -> None:
        """Negative priorities and decorative required controls raise ValueError."""
        with self.assertRaises(ValueError):
            self.panel.sections[0].add(QCheckBox(), -1)
        with self.assertRaises(ValueError):
            self.panel.sections[0].add(QCheckBox(), REQUIRED, decorative=True)

    def test_refit_after_content_grows(self) -> None:
        """refit plans again for the same size once a control asks for more room."""
        self._host(*SAMPLE_SIZES['side_wide'])
        self.assertEqual(self.panel.overflow_widgets, [])
        self.panel.size_slider.setMinimumHeight(1000)
        self.panel.refit()
        self.assertIn(self.panel.only_extra, self.panel.overflow_widgets)

    def test_content_that_cannot_shrink_scrolls_on_both_axes(self) -> None:
        """Content taller than a strip or wider than a side panel gets a scroll bar on that axis, so none is cut off."""
        panel = OversizedPanel()
        host = PanelHost(panel)
        try:
            for orientation, size in ((STRIP, QSize(900, 90)), (SIDE, QSize(150, 600))):
                with self.subTest(orientation=orientation):
                    tell_orientation(panel, orientation, size)
                    host.capture(size)
                    scroll_area = panel.findChild(QScrollArea)
                    cross_bar = scroll_area.verticalScrollBar() if orientation == STRIP \
                        else scroll_area.horizontalScrollBar()
                    # The bar's visibility updates on a posted event, so check what decides it: a scroll range, and
                    # a policy that lets Qt show the bar for it.
                    self.assertGreater(cross_bar.maximum(), 0)
                    policy = scroll_area.verticalScrollBarPolicy() if orientation == STRIP \
                        else scroll_area.horizontalScrollBarPolicy()
                    self.assertNotEqual(policy, Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        finally:
            host.release()

    def test_layout_snapshots(self) -> None:
        """The orientation each sample size lays out in, where each control sits, which sections show, their geometry
        and any layout problems."""
        result: dict[str, dict] = {}
        names = {id(self.panel.size_slider): 'size', id(self.panel.name_field): 'name', id(self.panel.flag): 'flag',
                 id(self.panel.extra): 'extra', id(self.panel.only_extra): 'only_extra'}
        host = PanelHost(self.panel)
        try:
            for name, (orientation, size) in SAMPLE_SIZES.items():
                tell_orientation(self.panel, orientation, size)
                host.capture(size)
                shown = [s for s in self.panel.sections if not s.widget.isHidden()]
                result[name] = {
                    'overflow': [names[id(w)] for w in self.panel.overflow_widgets],
                    'visible_sections': [s.title for s in shown],
                    'section_geometry': {s.title: list(s.widget.geometry().getRect()) for s in shown},
                    'orientation': self.panel.orientation.value,
                    'header_collapsed': self.panel.header_collapsed,
                    'more_button': not self.panel.header.more_button.isHidden(),
                    'problems': find_layout_problems(self.panel),
                }
                if orientation == STRIP:
                    for section in shown:
                        self.assertGreaterEqual(section.widget.width(), STRIP_SECTION_MIN_WIDTH)
                        self.assertLessEqual(section.widget.width(), STRIP_SECTION_MAX_WIDTH)
        finally:
            host.release()
        self.assert_json_matches_snapshot(result, os.path.join(SNAPSHOT_DIR, 'dock_panel_sample.json'))

    def _packed_columns(self, panel: PackedPanel) -> list[list[str]]:
        """The titles of each packed column's sections, left to right."""
        sections = {section.widget: section.title for section in panel.sections}
        shown = [section for section in panel.sections if not section.widget.isHidden()]
        by_parent: dict[QWidget, list] = {}
        for section in shown:
            by_parent.setdefault(section.widget.parentWidget(), []).append(section)
        ordered = sorted(by_parent.values(), key=lambda group: group[0].widget.mapTo(panel, QPoint()).x())
        return [[sections[section.widget] for section in group] for group in ordered]

    def _packed_panel(self, size: QSize) -> PackedPanel:
        panel = PackedPanel()
        self._host(STRIP, size, panel)
        panel.show()
        return panel

    def test_packed_sections_share_a_column_while_they_fit_the_height(self) -> None:
        """Two short sections share a column when they fit the strip's height, and split into two columns when the
        strip shrinks. A section that doesn't fit under the previous one starts a new column."""
        panel = self._packed_panel(QSize(1400, 600))
        self.assertEqual(self._packed_columns(panel), [['First', 'Second', 'Third']])
        self._host(STRIP, QSize(1400, 320 + 2 * panel.inset), panel)
        self.assertEqual(self._packed_columns(panel), [['First', 'Second'], ['Third']])
        self._host(STRIP, QSize(1400, 160), panel)
        self.assertEqual(self._packed_columns(panel), [['First'], ['Second'], ['Third']])
        self._host(STRIP, QSize(1400, 600), panel)
        self.assertEqual(self._packed_columns(panel), [['First', 'Second', 'Third']])

    def test_collapsed_section_stacks_above_the_next_one(self) -> None:
        """A collapsed section's header is short, so the next section fits under it, and opening it re-plans into a new
        column."""
        panel = self._packed_panel(QSize(1400, 240))
        first, second = panel.sections[0].widget, panel.sections[1].widget
        self.assertEqual(self._packed_columns(panel)[0], ['First'])
        first.set_expanded(False)
        self.assertEqual(self._packed_columns(panel)[0], ['First', 'Second'])
        first.set_expanded(True)
        self.assertNotEqual(self._packed_columns(panel)[0], ['First', 'Second'])
        self.assertTrue(second.isVisibleTo(panel))

    def test_collapsed_packed_section_draws_its_summary_below_the_title(self) -> None:
        """In a packing strip a collapsed section's header is taller than a one-line header, and returns to one line
        in a side panel."""
        panel = self._packed_panel(QSize(1400, 600))
        section = panel.sections[0].widget
        section.set_summary('512 x 512, batch 4')
        section.set_expanded(False)
        collapsed_height = section.header_button.sizeHint().height()
        section.set_expanded(True)
        self.assertGreater(collapsed_height, section.header_button.sizeHint().height())
        section.set_expanded(False)
        self._host(SIDE, QSize(400, 600), panel)
        self.assertEqual(section.header_button.sizeHint().height(), HEADER_HEIGHT)

    def test_trailing_column_stays_in_place_while_the_middle_scrolls(self) -> None:
        """The trailing column sits at the right edge, beside a scroll area whose content scrolls sideways under the
        strip's width."""
        panel = PackedPanel()
        host = PanelHost(panel)
        try:
            tell_orientation(panel, STRIP, QSize(500, 130))
            host.capture(QSize(500, 130))
            scroll = panel.findChild(QScrollArea)
            self.assertGreater(scroll.horizontalScrollBar().maximum(), 0)
            trailing = _trailing_column(panel)
            self.assertFalse(trailing.isHidden())
            self.assertEqual(trailing.geometry().right() + 1, panel.width() - panel.inset)
            scroll.horizontalScrollBar().setValue(scroll.horizontalScrollBar().maximum())
            self.assertEqual(trailing.geometry().right() + 1, panel.width() - panel.inset)
            self.assertLessEqual(scroll.geometry().right(), trailing.geometry().left())
            tell_orientation(panel, SIDE, QSize(400, 600))
            host.capture(QSize(400, 600))
            self.assertTrue(trailing.isHidden())
        finally:
            host.release()

    def test_trailing_column_set_not_to_scroll_counts_toward_the_minimum_height(self) -> None:
        """A trailing column scrolls in a strip too short for it, unless `set_trailing_scrolls(False)` makes its
        content's height part of the panel's minimum."""
        for scrolls in (True, False):
            with self.subTest(scrolls=scrolls):
                panel = PackedPanel()
                panel.trailing_button.setMinimumHeight(600)
                panel.set_trailing_scrolls(scrolls)
                host = PanelHost(panel)
                try:
                    tell_orientation(panel, STRIP, QSize(1400, 800))
                    host.capture(QSize(1400, 800))
                    self.assertEqual(panel.orientation, STRIP)
                    self.assertEqual(panel.minimumSizeHint().height() > 600, not scrolls)
                    self.assertEqual(panel.measure().height() > 600, not scrolls)
                finally:
                    host.release()

    def test_packed_minimum_size_does_not_depend_on_history(self) -> None:
        """The same size gives the same minimum size hint, whatever the panel showed before."""
        size = QSize(1400, 320)
        fresh = self._packed_panel(size)
        fresh_minimum = fresh.minimumSizeHint()
        used = self._packed_panel(QSize(1400, 600))
        for visited in (QSize(1400, 160), QSize(300, 400), QSize(1400, 600)):
            self._host(STRIP if visited.width() > 1000 else SIDE, visited, used)
        self._host(STRIP, size, used)
        self.assertEqual(used.minimumSizeHint(), fresh_minimum)

    def test_panels_that_do_not_opt_in_keep_one_column_per_section(self) -> None:
        """Without `set_column_packing` each strip section sits directly in the section layout, and no trailing column
        shows."""
        self._host(*SAMPLE_SIZES['strip_wide'])
        for section in self.panel.sections:
            self.assertIs(section.widget.parentWidget(), self.panel.section_layout.parentWidget())
        self.assertEqual(len(self.panel.findChildren(QScrollArea)), 2)


class CollapsibleSectionTest(IntraPaintTestCase):
    """Tests sections that collapse to their summary by fit."""

    def setUp(self) -> None:
        super().setUp()
        self.panel = CollapsiblePanel()
        self.panel.show()

    def _host(self, size: QSize) -> None:
        self.panel.resize(size)
        tell_orientation(self.panel, SIDE, size)

    def test_short_panel_collapses_the_section_before_it_scrolls(self) -> None:
        """A panel too short for the section's body collapses it to its header, keeps the optional field it outranks,
        and does not scroll."""
        self._host(QSize(300, 200))
        section = self.panel.sampling
        self.assertTrue(section.widget.is_collapsed())
        self.assertTrue(section.collapsed_by_fit)
        self.assertTrue(section.widget.isVisibleTo(self.panel))
        self.assertFalse(self.panel.block.isVisibleTo(self.panel))
        self.assertFalse(self.panel.content_scrolls)
        self.assertEqual(self.panel.overflow_widgets, [])

    def test_section_expands_again_once_it_fits_with_room_to_spare(self) -> None:
        """The section stays collapsed within HYSTERESIS of fitting and expands beyond it, without changing the
        remembered choice."""
        self._host(QSize(300, 200))
        needed = self.panel.measure().height()
        self._host(QSize(300, 900))
        expanded_height = self.panel.measure().height()
        self.assertFalse(self.panel.sampling.widget.is_collapsed())
        self.assertTrue(self.panel.sampling.widget.is_expanded())
        self.assertGreater(expanded_height, needed)
        self._host(QSize(300, 200))
        self.assertTrue(self.panel.sampling.widget.is_collapsed())
        self.assertTrue(self.panel.sampling.widget.is_expanded())
        self._host(QSize(300, expanded_height + 2 * self.panel.inset + HYSTERESIS))
        self.assertFalse(self.panel.sampling.widget.is_collapsed())

    def test_optional_controls_with_a_lower_priority_number_move_to_more_first(self) -> None:
        """The optional field outranks the section, so it stays placed while the section collapses."""
        self._host(QSize(300, 200))
        self.assertNotIn(self.panel.optional, self.panel.overflow_widgets)
        self.assertTrue(self.panel.sampling.widget.is_collapsed())

    def test_minimum_size_does_not_depend_on_history(self) -> None:
        """The same size gives the same minimum size hint, whatever the panel showed before."""
        size = QSize(300, 200)
        self._host(size)
        fresh = self.panel.minimumSizeHint()
        used = CollapsiblePanel()
        for visited in (QSize(300, 900), QSize(300, 100), size):
            used.resize(visited)
            tell_orientation(used, SIDE, visited)
        self.assertEqual(used.minimumSizeHint(), fresh)

    def test_clicking_a_collapsed_header_shows_the_body_in_a_popover(self) -> None:
        """A forced-collapsed header opens the body as a popover, and the body returns to the section when it
        closes."""
        self._host(QSize(300, 200))
        widget = self.panel.sampling.widget
        widget.header_button.click()
        popover = self.panel._section_popover  # pylint: disable=protected-access
        self.assertIsNotNone(popover)
        self.assertIs(popover.content, self.panel.sampling.widget.body)
        self.assertTrue(popover.isVisible())
        self.assertTrue(self.panel.block.isVisible())
        popover.hide()
        self.assertIs(self.panel.block.parentWidget(), widget.body)
        self.assertTrue(widget.is_collapsed())
        self.assertFalse(self.panel.block.isVisibleTo(self.panel))

    def test_expanding_closes_the_popover(self) -> None:
        """Planning that expands the section closes its popover and puts the body back."""
        self._host(QSize(300, 200))
        self.panel.sampling.widget.header_button.click()
        self._host(QSize(300, 900))
        popover = self.panel._section_popover  # pylint: disable=protected-access
        self.assertFalse(popover.isVisible())
        self.assertFalse(self.panel.sampling.widget.is_collapsed())
        self.assertTrue(self.panel.block.isVisibleTo(self.panel))

    def test_priority_must_be_above_required(self) -> None:
        """A collapsible section can't be required, since it could never be left out."""
        with self.assertRaises(ValueError):
            PanelLayout().section('Bad', collapsible=True, priority=REQUIRED)
