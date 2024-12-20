"""A horizontal slider and spinbox that both control the same value."""
from typing import Optional

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSlider, QDoubleSpinBox, QSpinBox, QSizePolicy

from src.util.layout import synchronize_row_widths


class _SliderSpinbox(QWidget):

    @staticmethod
    def align_slider_spinboxes(boxes: 'list[_SliderSpinbox]',
                               extra_rows: Optional[list[list[Optional[QWidget]]]] = None) -> None:
        """Adjust inner component layouts so that all parts of a column of slider spinboxes are sized equally"""
        if len(boxes) < 2:
            return
        rows = [] if extra_rows is None else extra_rows
        for box in boxes:
            row = [box.label, box.down_key_label, box.slider, box.up_key_label, box.spinbox]
            rows.append(row)
        synchronize_row_widths(rows)

    def __init__(self, initial_value: float | int, parent: Optional[QWidget] = None, label: Optional[str] = None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setSpacing(2)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._label = QLabel()
        self._layout.addWidget(self._label)
        if label is not None:
            self._label.setText(label)
        else:
            self._label.setVisible(False)
            self._label.setEnabled(False)
        self._down_hint = QWidget(self)
        self._layout.addWidget(self._down_hint)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._layout.addWidget(self._slider, stretch=1)
        self._slider.setValue(initial_value if isinstance(initial_value, int) else int(initial_value * 100))
        self._slider.valueChanged.connect(self.setValue)
        self._slider.setTickPosition(QSlider.TickPosition.TicksAbove)
        self._up_hint = QWidget(self)
        self._layout.addWidget(self._up_hint)
        if isinstance(initial_value, float):
            self._spinbox = QDoubleSpinBox()
        else:
            self._spinbox = QSpinBox()
        self._layout.addWidget(self._spinbox)
        self._spinbox.setValue(initial_value)
        self._spinbox.valueChanged.connect(self.setValue)
        self._spinbox.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Maximum)
        self._label.setBuddy(self._spinbox)

        if initial_value is not None:
            if self.minimum() > initial_value:
                self.setMinimum(initial_value)
            if self.maximum() < initial_value:
                self.setMaximum(initial_value)
            self.setValue(initial_value)

    def _update_slider_ticks(self) -> None:
        full_range = self._slider.maximum() - self._slider.minimum()
        if full_range < 20:
            tick_interval = 1
        elif full_range < 50:
            tick_interval = 5
        elif full_range < 100:
            tick_interval = 10
        elif full_range < 500:
            tick_interval = 50
        else:
            tick_interval = 100
        if isinstance(self._spinbox, QDoubleSpinBox):
            tick_interval *= 100
        self._slider.setTickInterval(tick_interval)

    def insert_key_hint_labels(self, down_hint: QWidget, up_hint: QWidget) -> None:
        """Inserts key hint widgets into the inner layout of the SliderSpinbox."""
        for old_hint in self._down_hint, self._up_hint:
            old_hint.height()
            self._layout.removeWidget(old_hint)
            old_hint.setParent(None)
            old_hint.deleteLater()
        self._down_hint = down_hint
        self._up_hint = up_hint
        slider_index = self._layout.indexOf(self._slider)
        self._layout.insertWidget(slider_index + (1 if self._slider.isVisible() else 2), self._up_hint)
        self._layout.insertWidget(slider_index, self._down_hint)

    def set_key_hints_visible(self, visible: bool) -> None:
        """Show or hide key hint labels, if present."""
        if self._down_hint is not None:
            self._down_hint.setVisible(visible)
        if self._up_hint is not None:
            self._up_hint.setVisible(visible)

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
            if not isinstance(new_value, int):
                raise TypeError(f'expected int value, got {new_value}')
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
        self._update_slider_ticks()

    def minimum(self) -> int | float:
        """Returns the minimum accepted value."""
        return self._spinbox.minimum()

    def setMaximum(self, new_maximum: int | float) -> None:
        """Sets a new maximum accepted value."""
        self._spinbox.setMaximum(new_maximum)
        self._slider.setMaximum(int(new_maximum * 100) if isinstance(self._spinbox, QDoubleSpinBox) else new_maximum)
        self._update_slider_ticks()

    def maximum(self) -> int | float:
        """Returns the maximum accepted value."""
        return self._spinbox.maximum()

    def setRange(self, new_minimum: int | float, new_maximum: int | float) -> None:
        """Sets a new range of accepted values."""
        self.setMinimum(new_minimum)
        self.setMaximum(new_maximum)

    def setSingleStep(self, step_size: int | float) -> None:
        """Set the amount the value changes from a single key/button input."""
        self._slider.setSingleStep(int(step_size * 100) if isinstance(self._spinbox, QDoubleSpinBox) else step_size)
        self._spinbox.setSingleStep(step_size)

    def stepBy(self, steps: int) -> None:
        """Advance the spinbox by a specific number of steps."""
        self._spinbox.stepBy(steps)

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
        if included == self._slider.isVisible() == self._slider.isEnabled():
            return
        self._slider.setVisible(included)
        self._slider.setEnabled(included)
        if self._up_hint is not None:
            self._layout.removeWidget(self._up_hint)
            index = self._layout.indexOf(self._slider) + (1 if included else 2)
            self._layout.insertWidget(index, self._up_hint)

    def slider_included(self) -> bool:
        """Return whether the slider is currently included."""
        return self._slider.isEnabled()

    def send_change_signal(self) -> None:
        """Send the type-specific value change signal."""
        raise NotImplementedError('Implement to send a float or int value change.')

    @property
    def label(self) -> QLabel:
        """Access the internal label"""
        return self._label

    @property
    def slider(self) -> QSlider:
        """Access the internal slider"""
        return self._slider

    @property
    def spinbox(self) -> QSpinBox | QDoubleSpinBox:
        """Access the internal spinbox"""
        return self._spinbox

    @property
    def down_key_label(self) -> QWidget:
        """Access the down keybinding label."""
        return self._down_hint

    @property
    def up_key_label(self) -> QWidget:
        """Access the up keybinding label."""
        return self._up_hint


class IntSliderSpinbox(_SliderSpinbox):
    """A horizontal slider and spinbox that both control the same integer value."""

    valueChanged = Signal(int)

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

    valueChanged = Signal(float)

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
