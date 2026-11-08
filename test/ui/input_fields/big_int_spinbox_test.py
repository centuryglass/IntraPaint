"""Tests BigIntSpinbox with values beyond the range of C integers, which Qt signals would overflow."""
import sys

from PySide6 import QtTest
from PySide6.QtWidgets import QApplication

from src.ui.input_fields.big_int_spinbox import BigIntSpinbox
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

# Values at and past the limits of 32- and 64-bit integers:
LARGE_VALUES = (2 ** 31, 2 ** 32, 2 ** 63 - 1, 2 ** 63, BigIntSpinbox.MAXIMUM, -2 ** 63 - 1, BigIntSpinbox.MINIMUM)


class BigIntSpinboxTest(IntraPaintTestCase):
    """Tests BigIntSpinbox values, signals and stepping at large magnitudes."""

    def test_set_value_round_trips_large_values(self) -> None:
        """`setValue` and `value` keep every value in the spinbox's range intact, as an int."""
        spinbox = BigIntSpinbox()
        for value in LARGE_VALUES:
            with self.subTest(value=value):
                spinbox.setValue(value)
                self.assertEqual(spinbox.value(), value)
                self.assertIs(type(spinbox.value()), int)

    def test_value_changed_emits_large_values_as_text(self) -> None:
        """`valueChanged` carries large values as exact decimal text, whether set or typed."""
        spinbox = BigIntSpinbox()
        emitted: list[str] = []
        spinbox.valueChanged.connect(emitted.append)
        for value in LARGE_VALUES:
            with self.subTest(value=value):
                spinbox.setValue(value)
                self.assertEqual(emitted[-1], str(value))
        spinbox.lineEdit().clear()
        QtTest.QTest.keyClicks(spinbox.lineEdit(), str(BigIntSpinbox.MAXIMUM))
        self.assertEqual(emitted[-1], str(BigIntSpinbox.MAXIMUM))
        self.assertEqual(spinbox.value(), BigIntSpinbox.MAXIMUM)

    def test_out_of_range_values_are_ignored(self) -> None:
        """Values outside the range neither change the value nor emit `valueChanged`."""
        spinbox = BigIntSpinbox()
        spinbox.setRange(-1, BigIntSpinbox.MAXIMUM)
        spinbox.setValue(5)
        emitted: list[str] = []
        spinbox.valueChanged.connect(emitted.append)
        for value in (BigIntSpinbox.MAXIMUM + 1, -2):
            with self.subTest(value=value):
                spinbox.setValue(value)
                self.assertEqual(spinbox.value(), 5)
        spinbox.lineEdit().setText(str(BigIntSpinbox.MAXIMUM + 1))
        self.assertEqual(emitted, [])

    def test_step_by_at_large_values(self) -> None:
        """Stepping works past 64-bit signed values and stops at the maximum."""
        spinbox = BigIntSpinbox()
        spinbox.setValue(2 ** 63 - 1)
        spinbox.stepBy(1)
        self.assertEqual(spinbox.value(), 2 ** 63)
        spinbox.setValue(BigIntSpinbox.MAXIMUM - 1)
        spinbox.stepBy(1)
        self.assertEqual(spinbox.value(), BigIntSpinbox.MAXIMUM)
        spinbox.stepBy(1)
        self.assertEqual(spinbox.value(), BigIntSpinbox.MAXIMUM)
