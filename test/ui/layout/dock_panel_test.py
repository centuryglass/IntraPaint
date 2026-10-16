"""Tests DockPanel: priority placement in every size class, the "More" overflow, re-arranging without rebuilding
widgets, and a layout snapshot at each class."""
import os
import sys

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QCheckBox, QLineEdit, QSlider, QWidget

from src.ui.layout.dock_panel import P1, P2, P3, DockPanel, PanelLayout
from src.ui.layout.panel_size_class import Orientation, SizeClass
from test.base_test_case import IntraPaintTestCase, TEST_RESOURCE_DIR

app = QApplication.instance() or QApplication(sys.argv)

SNAPSHOT_DIR = os.path.join(TEST_RESOURCE_DIR, 'layout_snapshots')
# One representative size per class, per orientation:
SIDE_SIZES = {SizeClass.COMPACT: QSize(200, 600), SizeClass.REGULAR: QSize(340, 600), SizeClass.WIDE: QSize(500, 600)}
STRIP_SIZES = {SizeClass.COMPACT: QSize(900, 120), SizeClass.REGULAR: QSize(900, 240), SizeClass.WIDE: QSize(900, 400)}


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


class DockPanelTest(IntraPaintTestCase):
    """Tests DockPanel with a fake host that calls set_host_facts."""

    def setUp(self) -> None:
        super().setUp()
        self.panel = SamplePanel()

    def _place(self, widget: QWidget) -> str:
        if widget in self.panel.overflow_widgets:
            return 'more'
        return 'section'

    def test_priority_placement_per_class(self) -> None:
        """P1 always stays in its section, P2 from REGULAR up, P3 only at WIDE, in both orientations."""
        expected = {
            SizeClass.COMPACT: ('section', 'more', 'more'),
            SizeClass.REGULAR: ('section', 'section', 'more'),
            SizeClass.WIDE: ('section', 'section', 'section'),
        }
        for orientation, sizes in ((Orientation.SIDE, SIDE_SIZES), (Orientation.STRIP, STRIP_SIZES)):
            for size_class, size in sizes.items():
                with self.subTest(orientation=orientation, size_class=size_class):
                    self.panel.set_host_facts(orientation, size)
                    self.assertEqual(self.panel.size_class, size_class)
                    placed = (self._place(self.panel.size_slider), self._place(self.panel.name_field),
                              self._place(self.panel.flag))
                    self.assertEqual(placed, expected[size_class])

    def test_overflowed_controls_stay_usable(self) -> None:
        """An overflowed control is still parented to the panel, still enabled, and keeps its value."""
        self.panel.set_host_facts(Orientation.SIDE, SIDE_SIZES[SizeClass.COMPACT])
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
        self.panel.set_host_facts(Orientation.SIDE, SIDE_SIZES[SizeClass.WIDE])
        self.panel.show()
        self.assertFalse(self.panel.header.more_button.isVisible())
        self.assertIsNone(self.panel.header.popover.content)
        self.assertEqual(self.panel.overflow_widgets, [])

    def test_section_with_no_shown_controls_is_hidden(self) -> None:
        """A section whose controls all overflowed is hidden, and its heading appears in the More area."""
        self.panel.set_host_facts(Orientation.SIDE, SIDE_SIZES[SizeClass.COMPACT])
        self.panel.show()
        advanced = self.panel.sections[1]
        self.assertFalse(advanced.widget.isVisibleTo(self.panel))
        self.assertFalse(advanced.overflow_title.isHidden())
        self.assertEqual(len(self.panel.overflow_widgets), 4)

    def test_host_change_keeps_widgets_and_state(self) -> None:
        """Changing orientation and class re-arranges the same widget objects, with their state intact."""
        widgets = (self.panel.size_slider, self.panel.name_field, self.panel.flag)
        self.panel.set_host_facts(Orientation.SIDE, SIDE_SIZES[SizeClass.WIDE])
        self.panel.size_slider.setValue(42)
        self.panel.name_field.setText('typed')
        self.panel.flag.setChecked(True)
        for orientation, size in ((Orientation.STRIP, STRIP_SIZES[SizeClass.COMPACT]),
                                  (Orientation.SIDE, SIDE_SIZES[SizeClass.COMPACT]),
                                  (Orientation.STRIP, STRIP_SIZES[SizeClass.WIDE])):
            self.panel.set_host_facts(orientation, size)
            self.assertEqual((self.panel.size_slider, self.panel.name_field, self.panel.flag), widgets)
            self.assertEqual(self.panel.size_slider.value(), 42)
            self.assertEqual(self.panel.name_field.text(), 'typed')
            self.assertTrue(self.panel.flag.isChecked())

    def test_unchanged_class_does_not_rearrange(self) -> None:
        """A resize inside one class doesn't call arrange again."""
        calls: list[tuple[Orientation, SizeClass]] = []
        original = self.panel.arrange
        self.panel.arrange = lambda o, c: (calls.append((o, c)), original(o, c))[1]  # type: ignore[method-assign]
        self.panel.set_host_facts(Orientation.SIDE, QSize(300, 500))
        self.panel.set_host_facts(Orientation.SIDE, QSize(310, 500))
        self.assertEqual(len(calls), 1)

    def test_strip_short_moves_more_button_out_of_hidden_header(self) -> None:
        """In Strip Short the header is hidden and the More button moves to the end of the row, and returns later."""
        self.panel.set_host_facts(Orientation.STRIP, STRIP_SIZES[SizeClass.COMPACT])
        self.panel.show()
        more_button = self.panel.header.more_button
        self.assertTrue(self.panel.header.isHidden())
        self.assertFalse(self.panel.header.isAncestorOf(more_button))
        self.assertTrue(more_button.isVisible())
        self.panel.set_host_facts(Orientation.STRIP, STRIP_SIZES[SizeClass.REGULAR])
        self.assertFalse(self.panel.header.isHidden())
        self.assertTrue(self.panel.header.isAncestorOf(more_button))
        self.assertTrue(more_button.isVisible())

    def test_invalid_priority(self) -> None:
        """Priorities other than P1-P3 raise ValueError."""
        with self.assertRaises(ValueError):
            self.panel.sections[0].add(QCheckBox(), 4)

    def test_layout_snapshots(self) -> None:
        """Where each control sits, and which sections show, at each class in both orientations."""
        result: dict[str, dict] = {}
        names = {id(self.panel.size_slider): 'size', id(self.panel.name_field): 'name', id(self.panel.flag): 'flag',
                 id(self.panel.extra): 'extra', id(self.panel.only_extra): 'only_extra'}
        for orientation, sizes in ((Orientation.SIDE, SIDE_SIZES), (Orientation.STRIP, STRIP_SIZES)):
            for size_class, size in sizes.items():
                self.panel.set_host_facts(orientation, size)
                result[f'{orientation.value}_{size_class.name.lower()}'] = {
                    'overflow': [names[id(w)] for w in self.panel.overflow_widgets],
                    'visible_sections': [s.title for s in self.panel.sections if not s.widget.isHidden()],
                    'more_button': not self.panel.header.more_button.isHidden(),
                }
        self.assert_json_matches_snapshot(result, os.path.join(SNAPSHOT_DIR, 'dock_panel_sample.json'))
