"""
QSpinbox implementation that supports a larger range of integer values.
Adapted from https://stackoverflow.com/a/26861829
"""
from PyQt5.QtWidgets import QAbstractSpinBox, QLineEdit
from PyQt5.QtCore import pyqtSignal, QRegExp
from PyQt5.QtGui import QRegExpValidator

class BigIntSpinbox(QAbstractSpinBox):
    """BigIntSpinbox is a QSpinBox supporting integers between -18446744073709551616 and 18446744073709551615."""

    # I believe pyqtSignal converts to C integers internally, because if the signal emits an int it is vulnerable
    # to overflow.
    valueChanged = pyqtSignal(str)

    MINIMUM= -18446744073709551616
    MAXIMUM= 18446744073709551615

    def __init__(self, parent=None):
        """Optionally initialize with a parent widget."""
        super().__init__(parent)
        self.setMinimumWidth(40)

        self._single_step = 1
        self._line_edit = QLineEdit(self)
        self._minimum = BigIntSpinbox.MINIMUM
        self._maximum = BigIntSpinbox.MAXIMUM

        rx = QRegExp("-?[1-9]\\d{0,20}")
        validator = QRegExpValidator(rx, self)

        self._line_edit.setValidator(validator)
        def on_change(value):
            # Make sure we're not emitting change signals on clear/while typing a new negative number:
            if len(value) > 0 and value != "-":
                self.valueChanged.emit(value)
        self._line_edit.textChanged.connect(on_change)
        self.setLineEdit(self._line_edit)


    def value(self):
        """Returns the current numeric value as an int."""
        return int(self._line_edit.text())

    def setValue(self, value):
        """Sets a new integer value if within the accepted range."""
        if self._value_in_range(value):
            self._line_edit.setText(str(value))
        else:
            pass

    def setSingleStep(self, single_step):
        """Sets the amount the spinbox value should change when the controls are used to change the value once."""
        assert isinstance(single_step, int)
        # don't use negative values
        self._single_step = abs(single_step)


    def stepBy(self, steps):
        """Offset the current value based on current step size and some integer step count."""
        self.setValue(self.value() + steps*self.singleStep())

    def stepEnabled(self):
        """Resurns whether incrementing/decrementing the value by steps is enabled."""
        return self.StepUpEnabled | self.StepDownEnabled


    def singleStep(self):
        """Returns the amount the spinbox value changes when controls are clicked once. """
        return self._single_step

    def minimum(self):
        """Returns the current minimum accepted value."""
        return self._minimum

    def setMinimum(self, minimum):
        """Sets the minimum value accepted, must be an integer no less than -18446744073709551616."""
        assert isinstance(minimum, int)
        if minimum < BigIntSpinbox.MINIMUM:
            raise ValueError(f"Minimum cannot be less that {BigIntSpinbox.MINIMUM}, got {minimum}")
        self._minimum = minimum

    def maximum(self):
        """Returns the current maximum accepted value."""
        return self._maximum

    def setMaximum(self, maximum):
        """Sets the maximum value accepted, must be an integer no greater than 18446744073709551615."""
        assert isinstance(maximum, int)
        if maximum > BigIntSpinbox.MAXIMUM:
            raise ValueError(f"Maximum cannot be greater that {BigIntSpinbox.MAXIMUM}, got {maximum}")
        self._maximum = maximum

    def setRange(self, minimum, maximum):
        """Sets the range of accepted values."""
        self.setMinimum(minimum)
        self.setMaximum(maximum)

    def _value_in_range(self, value):
        return bool(self.minimum() <= value <= self.maximum())
