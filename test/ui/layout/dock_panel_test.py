"""Tests DockPanel: placement by fit in tall, short, wide and narrow panels of both orientations, the "More" overflow,
decorative controls, control forms, re-planning without rebuilding widgets, scrolling, and a layout snapshot at each
sample size."""
import os
import sys

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QLineEdit, QPushButton, QScrollArea, QSlider, QWidget

from src.ui.layout.dock_panel import DockPanel, PanelLayout
from src.ui.layout.panel_fit import REQUIRED, STRIP_SECTION_MAX_WIDTH, STRIP_SECTION_MIN_WIDTH, Orientation
from test.base_test_case import IntraPaintTestCase, TEST_RESOURCE_DIR
from test.ui.panel_capture import PanelHost, find_layout_problems, tell_orientation

app = QApplication.instance() or QApplication(sys.argv)

SNAPSHOT_DIR = os.path.join(TEST_RESOURCE_DIR, 'layout_snapshots')
SIDE = Orientation.SIDE
STRIP = Orientation.STRIP
# Sample sizes, named by shape. Every control fits in side_tall_narrow, side_wide, strip_wide and strip_regular:
SAMPLE_SIZES = {
    'side_tall_narrow': (SIDE, QSize(200, 900)),
    'side_short': (SIDE, QSize(340, 120)),
    'side_wide': (SIDE, QSize(500, 600)),
    'strip_short': (STRIP, QSize(1400, 90)),
    'strip_wide': (STRIP, QSize(1400, 160)),
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


class OversizedPanel(DockPanel):
    """A tall column of required fields and a required button wider than a narrow side panel."""

    def build(self, ui: PanelLayout) -> None:
        fields = ui.section('Fields')
        for i in range(6):
            fields.add(QLineEdit(str(i)), REQUIRED)
        ui.section('Wide').add(QPushButton('A button label far wider than a narrow side panel'), REQUIRED)


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

    def test_roomy_panels_show_everything(self) -> None:
        """A tall, narrow side panel and a wide strip under 170 px tall have room for every control, so nothing moves
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
        measures: list[QSize] = []
        original_measure = self.panel.measure
        self.panel.measure = lambda: (measures.append(QSize()), original_measure())[1]  # type: ignore[method-assign]
        self.panel.set_host_facts(QSize(300, 500))
        count = len(measures)
        self.panel.set_host_facts(QSize(300, 500))
        self.assertEqual(len(measures), count)
        self.panel.set_host_facts(QSize(310, 500))
        self.assertGreater(len(measures), count)

    def test_orientation_follows_the_size_no_matter_its_area(self) -> None:
        """A panel takes the orientation its size suggests, whatever orientation the host reports: a wide space lays
        out as a strip even in a side dock, and a tall one as a side panel even in a bottom dock."""
        self._host(STRIP, QSize(1400, 160))
        self.assertEqual(self.panel.orientation, STRIP)
        self._host(STRIP, QSize(200, 900))
        self.assertEqual(self.panel.orientation, SIDE)
        self.assertEqual(self.panel.overflow_widgets, [])
        self._host(SIDE, QSize(1400, 160))
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
