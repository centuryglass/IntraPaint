"""Tests SegmentedControl: value binding by raw option string, selection by click and arrow keys, hints, display modes
and the combo fallback. Events are synthesized, and nothing waits on the event loop."""
import sys
from enum import Enum

from PySide6.QtCore import QPoint, Qt
from PySide6 import QtTest
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src.ui.input_fields.segmented_control import DisplayMode, Segment, SegmentedControl
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class Fill(Enum):
    """Persisted values for a three-way choice."""
    ALL = 'all'
    SELECTED = 'selected'
    NONE = 'none'


LABELS = {Fill.ALL: 'All', Fill.SELECTED: 'Selected', Fill.NONE: 'None'}


def _control(labels: dict[Fill, str] = LABELS, **kwargs) -> SegmentedControl:
    control = SegmentedControl.from_enum(Fill, labels, **kwargs)
    control.resize(control.sizeHint())
    control.show()
    return control


def _click(control: SegmentedControl, index: int) -> None:
    rect = control.segment_rect(index)
    QtTest.QTest.mouseClick(control, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, rect.center())


class SegmentedControlTest(IntraPaintTestCase):
    """Tests SegmentedControl."""

    def test_rejects_bad_segment_counts_and_duplicates(self) -> None:
        """Fewer than 2 or more than 5 segments, and repeated values, raise ValueError."""
        for count in (0, 1, 6):
            with self.assertRaises(ValueError):
                SegmentedControl([Segment(str(i), str(i)) for i in range(count)])
        with self.assertRaises(ValueError):
            SegmentedControl([Segment('a', 'A'), Segment('a', 'B')])

    def test_value_is_raw_option_string_under_any_translation(self) -> None:
        """Changing every label leaves the stored values alone, and loading a raw value checks its segment."""
        shouted = {mode: f'<<{label.upper()}>>' for mode, label in LABELS.items()}
        for labels in (LABELS, shouted):
            control = _control(labels)
            self.assertEqual(control.value(), 'all')
            control.set_value('selected')
            self.assertEqual(control.value(), 'selected')
            self.assertEqual(control.segments[1].label, labels[Fill.SELECTED])
            with self.assertRaises(ValueError):
                control.set_value(labels[Fill.SELECTED] + 'x')
        with self.assertRaises(ValueError):
            _control(shouted).set_value('<<SELECTED>>')

    def test_set_value_emits_only_on_change(self) -> None:
        """valueChanged carries the raw option string and is emitted once per real change."""
        control = _control()
        emitted: list[str] = []
        control.valueChanged.connect(emitted.append)
        control.set_value('all')
        control.set_value('none')
        control.set_value('none')
        self.assertEqual(emitted, ['none'])

    def test_click_selects_segment(self) -> None:
        """A click checks the segment under it."""
        control = _control()
        emitted: list[str] = []
        control.valueChanged.connect(emitted.append)
        _click(control, 2)
        self.assertEqual(control.value(), 'none')
        _click(control, 1)
        self.assertEqual(control.value(), 'selected')
        self.assertEqual(emitted, ['none', 'selected'])

    def test_arrow_keys_move_between_segments(self) -> None:
        """Arrows, Home and End move the checked segment and stop at the ends."""
        control = _control()
        for key, expected in ((Qt.Key.Key_Right, 'selected'), (Qt.Key.Key_Down, 'none'), (Qt.Key.Key_Right, 'none'),
                              (Qt.Key.Key_Left, 'selected'), (Qt.Key.Key_Up, 'all'), (Qt.Key.Key_Left, 'all'),
                              (Qt.Key.Key_End, 'none'), (Qt.Key.Key_Home, 'all')):
            QtTest.QTest.keyClick(control, key)
            self.assertEqual(control.value(), expected)

    def test_is_one_focus_stop(self) -> None:
        """The control takes focus as a single widget."""
        self.assertEqual(_control().focusPolicy(), Qt.FocusPolicy.StrongFocus)

    def test_hint_does_not_change_value(self) -> None:
        """A hint highlights a segment without changing the value, and clears with None."""
        control = _control()
        emitted: list[str] = []
        control.valueChanged.connect(emitted.append)
        control.set_hint_value('none')
        self.assertEqual(control.hint_value(), 'none')
        self.assertEqual(control.value(), 'all')
        control.set_hint_value(None)
        self.assertIsNone(control.hint_value())
        self.assertEqual(emitted, [])
        with self.assertRaises(ValueError):
            control.set_hint_value('missing')

    def test_icon_only_needs_icons_and_uses_label_tooltip(self) -> None:
        """Icon-only mode requires an icon on every segment, and each tooltip falls back to the label."""
        with self.assertRaises(ValueError):
            _control(display_mode=DisplayMode.ICON)
        control = _control()
        self.assertEqual(control.segment_tooltip(1), 'Selected')
        with_tooltip = SegmentedControl([Segment('a', 'A', QIcon(), 'tip'), Segment('b', 'B', QIcon())])
        self.assertEqual(with_tooltip.segment_tooltip(0), 'tip')
        self.assertEqual(with_tooltip.segment_tooltip(1), 'B')

    def test_icon_only_is_narrower(self) -> None:
        """Hiding labels shrinks the size hint."""
        icons = {mode: QIcon() for mode in Fill}
        control = _control(icons=icons)
        full = control.sizeHint().width()
        control.set_display_mode(DisplayMode.LABEL)
        self.assertLessEqual(control.sizeHint().width(), full)

    def test_combo_fallback_when_narrow(self) -> None:
        """A control narrower than its segments need shows a combo box that edits the same value."""
        control = _control(combo_fallback=True)
        self.assertFalse(control.uses_combo_fallback())
        control.resize(control.sizeHint().width() // 2, control.height())
        self.assertTrue(control.uses_combo_fallback())
        combo = control.findChild(type(control._combo))  # pylint: disable=protected-access
        self.assertTrue(combo.isVisibleTo(control))
        combo.setCurrentIndex(2)
        self.assertEqual(control.value(), 'none')
        control.set_value('selected')
        self.assertEqual(combo.currentData(), 'selected')
        control.resize(control.sizeHint())
        self.assertFalse(combo.isVisibleTo(control))
