"""Tests NumberField and SliderField: scrubbing, click-to-type, wheel and key stepping, clamping, display mapping,
the pen pressure link, and accessibility text. Events are synthesized, and nothing waits on the event loop."""
import sys

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QHoverEvent, QWheelEvent
from PySide6 import QtTest
from PySide6.QtWidgets import QApplication, QLineEdit

from src.ui.input_fields.number_field import NumberField, PIXELS_PER_STEP, PRESSURE_LINK_WIDTH
from src.ui.input_fields.slider_field import SliderField, number_field_for_parameter
from src.util.parameter import Parameter, TYPE_FLOAT, TYPE_INT
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

WIDTH = 200
CENTER_Y = 12


def _shown(field: NumberField) -> NumberField:
    field.resize(WIDTH, field.height())
    field.show()
    return field


def _scrub(field: NumberField, delta_x: int, start_x: int = 100) -> None:
    QtTest.QTest.mousePress(field, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(start_x, CENTER_Y))
    QtTest.QTest.mouseMove(field, QPoint(start_x + delta_x, CENTER_Y))
    QtTest.QTest.mouseRelease(field, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                       QPoint(start_x + delta_x, CENTER_Y))


def _wheel(field: NumberField, notches: int) -> None:
    event = QWheelEvent(QPointF(10, 10), QPointF(10, 10), QPoint(), QPoint(0, 120 * notches),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(field, event)


class NumberFieldTest(IntraPaintTestCase):
    """Tests the behavior shared by NumberField and SliderField."""

    def _slider(self, value: int | float = 40, **kwargs) -> SliderField:
        return _shown(SliderField('Size', value, 0, 100, **kwargs))

    def test_drag_scrubs_by_width_fraction(self) -> None:
        """Dragging a slider field across half its width changes the value by half its range."""
        field = self._slider(20)
        changes: list = []
        field.valueChanged.connect(changes.append)
        _scrub(field, 50)
        self.assertEqual(field.value(), 45)
        self.assertEqual(changes[-1], 45)

    def test_drag_clamps(self) -> None:
        """A drag past either end stops at the limit."""
        field = self._slider(90)
        _scrub(field, 150)
        self.assertEqual(field.value(), 100)
        _scrub(field, -400, start_x=195)
        self.assertEqual(field.value(), 0)

    def test_unbounded_drag_changes_by_steps(self) -> None:
        """A number field scrubs one step per few pixels."""
        field = _shown(NumberField('X', -4, step=2))
        _scrub(field, 5 * PIXELS_PER_STEP)
        self.assertEqual(field.value(), 6)
        _scrub(field, -10 * PIXELS_PER_STEP)
        self.assertEqual(field.value(), -14)

    def test_drag_is_one_gesture(self) -> None:
        """dragStarted and dragFinished fire once around a drag, and not at all for a click."""
        field = self._slider()
        events: list[str] = []
        field.dragStarted.connect(lambda: events.append('start'))
        field.dragFinished.connect(lambda: events.append('finish'))
        field.valueChanged.connect(lambda _: events.append('change'))
        _scrub(field, 20)
        self.assertEqual(events[0], 'start')
        self.assertEqual(events[-1], 'finish')
        self.assertEqual(events.count('start'), 1)
        self.assertEqual(events.count('finish'), 1)
        events.clear()
        QtTest.QTest.mouseClick(field, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(100, CENTER_Y))
        self.assertNotIn('start', events)
        self.assertNotIn('finish', events)

    def test_click_opens_text_entry(self) -> None:
        """A click without a drag opens the text entry and doesn't change the value."""
        field = self._slider()
        QtTest.QTest.mouseClick(field, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(100, CENTER_Y))
        self.assertTrue(field.editing())
        self.assertEqual(field.value(), 40)
        editor = field.findChild(QLineEdit)
        assert editor is not None
        self.assertEqual(editor.text(), '40')

    def test_typed_value_applies_and_clamps(self) -> None:
        """Typed text sets the value, clamping out of range numbers, and ignoring text that isn't a number."""
        field = self._slider()
        for text, expected in (('75', 75), ('250', 100), ('-3', 0), ('abc', 0), ('12', 12)):
            with self.subTest(text=text):
                field.begin_edit()
                editor = field.findChild(QLineEdit)
                assert editor is not None
                editor.setText(text)
                field.commit_edit()
                self.assertFalse(field.editing())
                self.assertEqual(field.value(), expected)

    def test_escape_cancels_text_entry(self) -> None:
        """Escape closes the text entry and discards what was typed."""
        field = self._slider()
        field.begin_edit()
        editor = field.findChild(QLineEdit)
        assert editor is not None
        editor.setText('90')
        QtTest.QTest.keyClick(editor, Qt.Key.Key_Escape)
        self.assertFalse(field.editing())
        self.assertEqual(field.value(), 40)

    def test_enter_key_opens_text_entry(self) -> None:
        """A user with only a keyboard can type a value: Enter opens the entry."""
        field = self._slider()
        QtTest.QTest.keyClick(field, Qt.Key.Key_Return)
        self.assertTrue(field.editing())

    def test_wheel_steps_and_clamps(self) -> None:
        """Each wheel notch is one step, and the value stops at the limits."""
        field = self._slider(98, step=1)
        _wheel(field, 1)
        self.assertEqual(field.value(), 99)
        _wheel(field, 5)
        self.assertEqual(field.value(), 100)
        _wheel(field, -3)
        self.assertEqual(field.value(), 97)

    def test_keys_step_and_clamp(self) -> None:
        """Arrow keys step, Page Up and Down move ten steps, Home and End jump to the limits."""
        field = self._slider(50, step=2)
        for key, expected in ((Qt.Key.Key_Right, 52), (Qt.Key.Key_Up, 54), (Qt.Key.Key_Left, 52),
                              (Qt.Key.Key_Down, 50), (Qt.Key.Key_PageUp, 70), (Qt.Key.Key_PageDown, 50),
                              (Qt.Key.Key_End, 100), (Qt.Key.Key_Right, 100), (Qt.Key.Key_Home, 0),
                              (Qt.Key.Key_Left, 0)):
            with self.subTest(key=key):
                QtTest.QTest.keyClick(field, key)
                self.assertEqual(field.value(), expected)

    def test_set_value_round_trip(self) -> None:
        """set_value emits only when the value changes, so a bound value can echo back without a loop."""
        field = self._slider()
        changes: list = []
        field.valueChanged.connect(changes.append)
        field.set_value(40)
        self.assertEqual(changes, [])
        field.set_value(55)
        field.set_value(55)
        self.assertEqual(changes, [55])
        self.assertEqual(field.value(), 55)

    def test_float_values_snap_to_step(self) -> None:
        """Float fields keep floats, snapped to the step without rounding noise."""
        field = _shown(SliderField('Opacity', 0.5, 0.0, 1.0, step=0.05))
        field.set_value(0.333)
        self.assertEqual(field.value(), 0.35)
        QtTest.QTest.keyClick(field, Qt.Key.Key_Right)
        self.assertEqual(field.value(), 0.4)
        self.assertIsInstance(field.value(), float)

    def test_display_mapping(self) -> None:
        """The shown text and typed entry use the display scale, suffix and zero text; the stored value doesn't."""
        field = _shown(SliderField('Opacity', 0.75, 0.0, 1.0, step=0.01, display_scale=100, suffix='%', decimals=0,
                                   zero_text='none'))
        self.assertEqual(field.value_text(), '75%')
        self.assertEqual(field.value_text(0), 'none')
        field.begin_edit()
        editor = field.findChild(QLineEdit)
        assert editor is not None
        editor.setText('20%')
        field.commit_edit()
        self.assertEqual(field.value(), 0.2)
        self.assertEqual(field.parse_text('none'), 0)

    def test_integer_field_value_type(self) -> None:
        """An all-int field stores and emits ints."""
        field = self._slider(10, suffix=' px')
        field.set_value(33.6)
        self.assertEqual(field.value(), 34)
        self.assertIsInstance(field.value(), int)
        self.assertEqual(field.value_text(), '34 px')

    def test_unbounded_number_field_has_no_fill(self) -> None:
        """A number field accepts negative and large values."""
        field = _shown(NumberField('Offset', 0))
        field.set_value(-1000000)
        self.assertEqual(field.value(), -1000000)
        self.assertEqual(field.value_text(), '-1000000')

    def test_slider_field_requires_finite_range(self) -> None:
        """A slider field's range must have a minimum below its maximum."""
        with self.assertRaises(ValueError):
            SliderField('Bad', 0, 5, 5)
        with self.assertRaises(ValueError):
            self._slider().set_range(None, 10)

    def test_pressure_link_uses_default_cursor(self) -> None:
        """Hovering the link shows the arrow cursor, and the rest of the field shows the scrub cursor."""
        field = self._slider()
        field.set_pressure_link_available(True)
        link_pos = QPointF(WIDTH - PRESSURE_LINK_WIDTH // 2, CENTER_Y)
        body_pos = QPointF(WIDTH // 4, CENTER_Y)
        hover = QEvent.Type.HoverMove
        field.event(QHoverEvent(hover, link_pos, link_pos, body_pos))
        self.assertEqual(field.cursor().shape(), Qt.CursorShape.ArrowCursor)
        field.event(QHoverEvent(hover, body_pos, body_pos, link_pos))
        self.assertEqual(field.cursor().shape(), Qt.CursorShape.SizeHorCursor)

    def test_pressure_link(self) -> None:
        """The link is clickable only when shown, toggles with a click or Space, and doesn't resize the field."""
        field = self._slider()
        toggles: list[bool] = []
        field.pressureLinkToggled.connect(toggles.append)
        size = field.size()
        link_pos = QPoint(WIDTH - PRESSURE_LINK_WIDTH // 2, CENTER_Y)
        QtTest.QTest.mouseClick(field, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, link_pos)
        self.assertEqual(toggles, [])
        self.assertTrue(field.editing())
        field.cancel_edit()
        field.set_pressure_link_available(True)
        self.assertEqual(field.size(), size)
        QtTest.QTest.mouseClick(field, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, link_pos)
        self.assertEqual(toggles, [True])
        self.assertFalse(field.editing())
        QtTest.QTest.keyClick(field, Qt.Key.Key_Space)
        self.assertEqual(toggles, [True, False])
        self.assertEqual(field.value(), 40)

    def test_accessibility(self) -> None:
        """The label is the accessible name, and the description tracks the value and range."""
        field = self._slider(suffix=' px')
        self.assertEqual(field.accessibleName(), 'Size')
        self.assertEqual(field.accessibleDescription(), '40 px (0 px - 100 px)')
        field.set_value(60)
        self.assertEqual(field.accessibleDescription(), '60 px (0 px - 100 px)')
        self.assertEqual(field.focusPolicy(), Qt.FocusPolicy.StrongFocus)

    def test_width_limits(self) -> None:
        """A field reads at 110 px and no more than about 300 px, at 24 px tall."""
        field = self._slider()
        self.assertEqual((field.minimumSizeHint().width(), field.maximumWidth(), field.height()), (110, 300, 24))

    def test_from_parameter(self) -> None:
        """A ranged parameter makes a slider field with its label, limits and tooltip, and an open one a number field."""
        ranged = Parameter('Strength', TYPE_FLOAT, 0.5, 'How strong', 0.0, 1.0, 0.1)
        field = number_field_for_parameter(ranged)
        self.assertIsInstance(field, SliderField)
        self.assertEqual((field.label(), field.value(), field.minimum(), field.maximum(), field.toolTip()),
                         ('Strength', 0.5, 0.0, 1.0, 'How strong'))
        open_ended = Parameter('Offset', TYPE_INT, 3, 'Shift')
        field = number_field_for_parameter(open_ended, 7)
        self.assertNotIsInstance(field, SliderField)
        self.assertEqual(field.value(), 7)
