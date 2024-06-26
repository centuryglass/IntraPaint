"""Provides an input widget for setting a QSize value."""
from typing import Optional

from PyQt5.QtCore import pyqtSignal, QSize, Qt
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QSpinBox, QSlider

from src.util.shared_constants import INT_MAX

WIDTH_LABEL = 'W:'
HEIGHT_LABEL = 'H:'


class SizeField(QWidget):
    """A QWidget input used to set a QSize value."""

    value_changed = pyqtSignal(QSize)

    def __init__(self, parent: Optional[QWidget] = None, include_sliders: bool = False) -> None:
        super().__init__(parent)
        bar_layout = QHBoxLayout(self)
        bar_layout.setSpacing(0)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.addWidget(QLabel(WIDTH_LABEL))
        if include_sliders:
            self._width_slider: Optional[QSlider] = QSlider(Qt.Orientation.Horizontal)
            self._width_slider.setValue(0)
            self._width_slider.valueChanged.connect(self._width_changed_slot)
            bar_layout.addWidget(self._width_slider)
        else:
            self._width_slider = None
        self._width_box = QSpinBox(self)
        self._width_box.setValue(0)
        self._width_box.valueChanged.connect(self._width_changed_slot)
        bar_layout.addWidget(self._width_box)
        bar_layout.addWidget(QLabel(HEIGHT_LABEL))
        self._height_box = QSpinBox(self)
        self._height_box.setValue(0)
        self._height_box.valueChanged.connect(self._height_changed_slot)
        bar_layout.addWidget(self._height_box)
        self._width = 0
        self._height = 0
        self._min_width = 0
        self._max_width = INT_MAX
        self._min_height = 0
        self._max_height = INT_MAX
        self._width_box.setRange(self._min_width, self._max_width)
        self._height_box.setRange(self._min_height, self._max_height)

    @property
    def value(self) -> QSize:
        """Accesses the current size value."""
        return QSize(self._width, self._height)

    @value.setter
    def value(self, new_value: QSize) -> None:
        if new_value != self.value:
            if not self._min_width <= new_value.width() <= self._max_width:
                raise ValueError(f'{new_value.width()} not in range {self._min_width} - {self._max_width}')
            if not self._min_height <= new_value.height() <= self._max_height:
                raise ValueError(f'{new_value.width()} not in range {self._min_width} - {self._max_width}')
            self._width = new_value.width()
            self._height = new_value.height()
            self.value_changed.emit(QSize(self._width, self._height))

    @property
    def minimum(self) -> QSize:
        """Accesses the minimum permitted size."""
        return QSize(self._min_width, self._min_height)

    @minimum.setter
    def minimum(self, new_minimum: QSize) -> None:
        if new_minimum.width() > self._max_width or new_minimum.height() > self._max_height:
            raise ValueError(f'New minimum {new_minimum} would be greater than max size {self.maximum}')
        size_value = self.value
        if size_value.width() < new_minimum.width():
            size_value.setWidth(new_minimum.width())
        if size_value.height() < new_minimum.height():
            size_value.setHeight(new_minimum.height())
        self.value = size_value
        self._min_height = new_minimum.height()
        self._min_width = new_minimum.width()
        self._width_box.setMinimum(new_minimum.width())
        self._height_box.setMinimum(new_minimum.height())

    @property
    def maximum(self) -> QSize:
        """Accesses the maximum permitted size."""
        return QSize(self._max_width, self._max_height)

    @maximum.setter
    def maximum(self, new_maximum: QSize) -> None:
        if new_maximum.width() < self._min_width or new_maximum.height() < self._min_height:
            raise ValueError(f'New maximum {new_maximum} would be less than minimum size {self.minimumn}')
        size_value = self.value
        if size_value.width() > new_maximum.width():
            size_value.setWidth(new_maximum.width())
        if size_value.height() > new_maximum.height():
            size_value.setHeight(new_maximum.height())
        self.value = size_value
        self._max_height = new_maximum.height()
        self._max_width = new_maximum.width()
        self._width_box.setMaximum(new_maximum.width())
        self._height_box.setMaximum(new_maximum.height())

    def set_range(self, minimum: QSize, maximum: QSize) -> None:
        """Set the minimum and maximum sizes permitted."""
        if maximum.width() < minimum.width() or maximum.height() < minimum.height():
            raise ValueError(f'Maximum {maximum} not equal to or greater than {minimum}')
        size_value = self.value
        size_value.setWidth(min(maximum.width(), max(minimum.width(), size_value.width())))
        size_value.setHeight(min(maximum.height(), max(minimum.height(), size_value.height())))
        self._min_height = minimum.height()
        self._max_height = maximum.height()
        self._min_width = minimum.width()
        self._max_width = maximum.width()
        self._width_box.setRange(self._min_width, self._max_width)
        self._height_box.setRange(self._min_height, self._max_height)
        self.value = size_value

    def set_single_step(self, step_value: int) -> None:
        """Change the amount the fields increase/decrease per step."""
        assert step_value > 0
        self._width_box.setSingleStep(step_value)
        self._height_box.setSingleStep(step_value)

    def _width_changed_slot(self, new_width: int) -> None:
        if self._width != new_width:
            if not self._min_width <= new_width <= self._max_width:
                raise ValueError(f'{new_width} not in range {self._min_width} - {self._max_width}')
            self._width = new_width
            self.value_changed.emit(QSize(self._width, self._height))

    def _height_changed_slot(self, new_height: int) -> None:
        if self._height != new_height:
            if not self._min_height <= new_height <= self._max_height:
                raise ValueError(f'{new_height} not in range {self._min_width} - {self._max_width}')
            self._height = new_height
            self.value_changed.emit(QSize(self._width, self._height))