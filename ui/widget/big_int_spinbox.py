# from https://stackoverflow.com/a/26861829
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QAbstractSpinBox, QLineEdit
from PyQt5.QtCore import pyqtSignal

class BigIntSpinbox(QAbstractSpinBox):
    # I believe pyqtSignal converts to C integers internally, because if the signal emits an int it is vulnerable
    # to overflow.
    valueChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super(BigIntSpinbox, self).__init__(parent)
        self.setMinimumWidth(40)

        self._singleStep = 1
        self._minimum = -18446744073709551616
        self._maximum = 18446744073709551615

        self.lineEdit = QLineEdit(self)

        rx = QtCore.QRegExp("-?[1-9]\\d{0,20}")
        validator = QtGui.QRegExpValidator(rx, self)

        self.lineEdit.setValidator(validator)
        def onChange(value):
            # Make sure we're not emitting change signals on clear/while typing a new negative number:
            if len(value) > 0 and value != "-":
                self.valueChanged.emit(value)
        self.lineEdit.textChanged.connect(onChange)
        self.setLineEdit(self.lineEdit)

    def value(self):
        try:
            return int(self.lineEdit.text())
        except:
            raise
            return 0

    def setValue(self, value):
        if self._valueInRange(value):
            self.lineEdit.setText(str(value))
        else:
            pass

    def stepBy(self, steps):
        self.setValue(self.value() + steps*self.singleStep())

    def stepEnabled(self):
        return self.StepUpEnabled | self.StepDownEnabled

    def setSingleStep(self, singleStep):
        assert isinstance(singleStep, int)
        # don't use negative values
        self._singleStep = abs(singleStep)

    def singleStep(self):
        return self._singleStep

    def minimum(self):
        return self._minimum

    def setMinimum(self, minimum):
        assert isinstance(minimum, int)
        self._minimum = minimum

    def maximum(self):
        return self._maximum

    def setMaximum(self, maximum):
        assert isinstance(maximum, int)
        self._maximum = maximum

    def setRange(self, minimum, maximum):
        self.setMinimum(minimum)
        self.setMaximum(maximum)

    def _valueInRange(self, value):
        if value >= self.minimum() and value <= self.maximum():
            return True
        else:
            return False

