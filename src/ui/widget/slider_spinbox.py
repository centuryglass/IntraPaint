"""A horizontal slider and spinbox that both control the same value."""
from typing import Optional

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QSlider, QDoubleSpinBox, QSpinBox


class _SliderSpinbox(QWidget):

    def __init__(self, initial_value: float | int, parent: Optional[QWidget] = None, label: Optional[str] = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel()
        layout.addWidget(self._label)
        if label is not None:
            self._label.setText(label)
        else:
            self._label.setVisible(False)
            self._label.setEnabled(False)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        layout.addWidget(self._slider)
        self._slider.setValue(initial_value if isinstance(initial_value, int) else float(initial_value * 100))
        self._slider.valueChanged.connect(self.setValue)
        if isinstance(initial_value, float):
            self._spinbox = QDoubleSpinBox()
        else:
            self._spinbox = QSpinBox()
        layout.addWidget(self._spinbox)
        self._spinbox.setValue(initial_value)
        self._spinbox.valueChanged.connect(self.setValue)
        self._label.setBuddy(self._spinbox)

    def value(self) -> int | float:
        """Returns the input field's current value."""
        return self._spinbox.value()

    def setValue(self, new_value: int | float) -> None:
        """Updates the input field's current value."""
        if isinstance(self._spinbox, QDoubleSpinBox) and isinstance(new_value, int):
            slider_int_value = new_value
            spinbox_value: float | int = new_value / 100
        elif isinstance(self._spinbox, QDoubleSpinBox) and isinstance(new_value, float):
            slider_int_value = int(new_value * 100)
            spinbox_value = new_value
        else:
            assert isinstance(new_value, int)
            slider_int_value = new_value
            spinbox_value = new_value
        if self._spinbox.value() != spinbox_value:
            self._spinbox.setValue(spinbox_value)
        elif self._slider.value() != slider_int_value:
            self._slider.setValue(slider_int_value)
        else:
            return
        self.send_change_signal()

    def setMinimum(self, new_minimum: int | float) -> None:
        """Sets a new minimum accepted value."""
        self._spinbox.setMinimum(new_minimum)
        self._slider.setMinimum(int(new_minimum * 100) if isinstance(self._spinbox, QDoubleSpinBox) else new_minimum)

    def setMaximum(self, new_maximum: int | float) -> None:
        """Sets a new maximum accepted value."""
        self._spinbox.setMaximum(new_maximum)
        self._slider.setMaximum(int(new_maximum * 100) if isinstance(self._spinbox, QDoubleSpinBox) else new_maximum)

    def setRange(self, new_minimum: int | float, new_maximum: int | float) -> None:
        """Sets a new range of accepted values."""
        self.setMinimum(new_minimum)
        self.setMaximum(new_maximum)

    def setSingleStep(self, step_size: int | float) -> None:
        """Set the amount the value changes from a single key/button input."""
        self._slider.setSingleStep(step_size * 100 if isinstance(self._spinbox, QDoubleSpinBox) else step_size)
        self._spinbox.setSingleStep(step_size)

    def text(self) -> str:
        """Returns the current label text."""
        return self._label.text()

    def setText(self, text: Optional[str]) -> None:
        """Updates or clears the label text."""
        if text is None:
            text = ''
        self._label.setText(text)
        self._label.setVisible(text != '')
        self._label.setEnabled(text != '')

    def set_slider_included(self, included: bool) -> None:
        """Show or hide the slider."""
        self._slider.setVisible(included)
        self._slider.setEnabled(included)

    def slider_included(self) -> bool:
        """Return whether the slider is currently included."""
        return self._slider.isEnabled()

    def send_change_signal(self) -> None:
        """Send the type-specific value change signal."""
        raise NotImplementedError('Implement to send a float or int value change.')


class IntSliderSpinbox(_SliderSpinbox):
    """A horizontal slider and spinbox that both control the same integer value."""

    valueChanged = pyqtSignal(int)

    def __init__(self, initial_value: Optional[int] = None, parent: Optional[QWidget] = None,
                 label: Optional[str] = None):
        if initial_value is None:
            initial_value = 0
        else:
            initial_value = int(initial_value)
        super().__init__(initial_value, parent, label)

    def send_change_signal(self) -> None:
        """Emits the int valueChanged signal."""
        self.valueChanged.emit(int(self.value()))


class FloatSliderSpinbox(_SliderSpinbox):
    """A horizontal slider and spinbox that both control the same float value."""

    valueChanged = pyqtSignal(float)

    def __init__(self, initial_value: Optional[float] = None, parent: Optional[QWidget] = None,
                 label: Optional[str] = None):
        if initial_value is None:
            initial_value = 0.0
        else:
            initial_value = float(initial_value)
        super().__init__(initial_value, parent, label)

    def send_change_signal(self) -> None:
        """Emits the float valueChanged signal."""
        self.valueChanged.emit(float(self.value()))

