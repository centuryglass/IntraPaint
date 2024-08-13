"""Provides an input widget for setting a QSize value."""
from typing import Optional

from PySide6.QtCore import Signal, QSize, Qt
from PySide6.QtWidgets import QWidget, QLabel, QSpinBox, QSlider, QGridLayout, QApplication

from src.util.shared_constants import INT_MAX

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.input_fields.size_field'

def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)

WIDTH_LABEL = _tr('W:')
HEIGHT_LABEL = _tr('H:')


class SizeField(QWidget):
    """A QWidget input used to set a QSize value."""

    valueChanged = Signal(QSize)

    def __init__(self, parent: Optional[QWidget] = None, include_sliders: bool = False) -> None:
        super().__init__(parent)
        self._orientation = Qt.Orientation.Horizontal
        self._layout = QGridLayout(self)
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._width_label = QLabel(WIDTH_LABEL)
        if include_sliders:
            self._width_slider: Optional[QSlider] = QSlider(Qt.Orientation.Horizontal)
            self._width_slider.setValue(0)
            self._width_slider.valueChanged.connect(self._width_changed_slot)
            self._height_slider: Optional[QSlider] = QSlider(Qt.Orientation.Horizontal)
            self._height_slider.setValue(0)
            self._height_slider.valueChanged.connect(self._height_changed_slot)
        else:
            self._width_slider = None
            self._height_slider = None
        self._width_box = QSpinBox(self)
        self._width_box.setValue(0)
        self._width_box.valueChanged.connect(self._width_changed_slot)
        self._height_label = QLabel(HEIGHT_LABEL)
        self._height_box = QSpinBox(self)
        self._height_box.setValue(0)
        self._height_box.valueChanged.connect(self._height_changed_slot)
        self._width = 0
        self._height = 0
        self._min_width = 0
        self._max_width = INT_MAX
        self._min_height = 0
        self._max_height = INT_MAX
        self._width_box.setRange(self._min_width, self._max_width)
        self._height_box.setRange(self._min_height, self._max_height)
        self._build_layout()

    def _build_layout(self) -> None:
        for row in range(self._layout.rowCount()):
            self._layout.setRowStretch(row, 0)
        for col in range(self._layout.columnCount()):
            self._layout.setColumnStretch(col, 0)
        for widget in (self._width_box, self._width_label, self._width_slider,
                       self._height_box, self._height_label, self._height_slider):
            if widget is not None and widget in self._layout.findChildren(QWidget):
                self._layout.removeWidget(widget)
        if self._orientation == Qt.Orientation.Horizontal:
            def _add_column(column_widget: Optional[QWidget], column: int, stretch: int = 2) -> None:
                if column_widget is not None:
                    self._layout.addWidget(column_widget, 0, column)
                    self._layout.setColumnStretch(column, stretch)

            self._layout.setRowStretch(0, 1)
            _add_column(self._width_label, 0, 0)
            _add_column(self._width_slider, 1, 0 if self._width_slider is None else 3)
            _add_column(self._width_box, 2)
            _add_column(None, 3, 1)
            _add_column(self._height_label, 4, 0)
            _add_column(self._height_slider, 5, 0 if self._height_slider is None else 3)
            _add_column(self._height_box, 6)
        else:
            row = 0
            self._layout.setColumnStretch(0, 0)
            self._layout.setColumnStretch(1, 0 if self._width_slider is None else 3)
            self._layout.setColumnStretch(2, 2)
            for label, slider, box in ((self._width_label, self._width_slider, self._width_box),
                                       (self._height_label, self._height_slider, self._height_box)):
                self._layout.setRowStretch(row, 1)
                self._layout.addWidget(label, row, 0)
                if slider is not None:
                    self._layout.addWidget(slider, row, 1)
                self._layout.addWidget(box, row, 2)
                row += 1

    def sizeHint(self):
        """Reduce the expected width."""
        base_hint = super().sizeHint()
        base_hint.setWidth(base_hint.width() // 2)
        return base_hint

    def set_labels_visible(self, should_show: bool) -> None:
        """Show or hide width/height labels."""
        self._width_label.setVisible(should_show)
        self._height_label.setVisible(should_show)

    @property
    def orientation(self) -> Qt.Orientation:
        """Return whether boxes are stacked vertically or laid out horizontally."""
        return self._orientation

    @orientation.setter
    def orientation(self, new_orientation: Qt.Orientation) -> None:
        if new_orientation != self._orientation:
            self._orientation = new_orientation
            self._build_layout()

    def value(self) -> QSize:
        """Accesses the current size value."""
        return QSize(self._width, self._height)

    def setValue(self, new_value: QSize) -> None:
        """Updates the current size value."""
        if new_value != self.value():
            if not self._min_width <= new_value.width() <= self._max_width:
                raise ValueError(f'{new_value.width()} not in range {self._min_width} - {self._max_width}')
            if not self._min_height <= new_value.height() <= self._max_height:
                raise ValueError(f'{new_value.width()} not in range {self._min_width} - {self._max_width}')
            self._width = new_value.width()
            self._height = new_value.height()
            self._width_box.valueChanged.disconnect(self._width_changed_slot)
            self._height_box.valueChanged.disconnect(self._height_changed_slot)
            self._width_box.setValue(self._width)
            self._height_box.setValue(self._height)
            self._width_box.valueChanged.connect(self._width_changed_slot)
            self._height_box.valueChanged.connect(self._height_changed_slot)
            self.valueChanged.emit(QSize(self._width, self._height))

    @property
    def minimum(self) -> QSize:
        """Accesses the minimum permitted size."""
        return QSize(self._min_width, self._min_height)

    @minimum.setter
    def minimum(self, new_minimum: QSize) -> None:
        if new_minimum.width() > self._max_width or new_minimum.height() > self._max_height:
            raise ValueError(f'New minimum {new_minimum} would be greater than max size {self.maximum}')
        size_value = self.value()
        if size_value.width() < new_minimum.width():
            size_value.setWidth(new_minimum.width())
        if size_value.height() < new_minimum.height():
            size_value.setHeight(new_minimum.height())
        self.setValue(size_value)
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
            raise ValueError(f'New maximum {new_maximum} would be less than minimum size {self.minimum}')
        size_value = self.value()
        if size_value.width() > new_maximum.width():
            size_value.setWidth(new_maximum.width())
        if size_value.height() > new_maximum.height():
            size_value.setHeight(new_maximum.height())
        self.setValue(size_value)
        self._max_height = new_maximum.height()
        self._max_width = new_maximum.width()
        self._width_box.setMaximum(new_maximum.width())
        self._height_box.setMaximum(new_maximum.height())

    def set_range(self, minimum: QSize, maximum: QSize) -> None:
        """Set the minimum and maximum sizes permitted."""
        if maximum.width() < minimum.width() or maximum.height() < minimum.height():
            raise ValueError(f'Maximum {maximum} not equal to or greater than {minimum}')
        size_value = self.value()
        size_value.setWidth(min(maximum.width(), max(minimum.width(), size_value.width())))
        size_value.setHeight(min(maximum.height(), max(minimum.height(), size_value.height())))
        self._min_height = minimum.height()
        self._max_height = maximum.height()
        self._min_width = minimum.width()
        self._max_width = maximum.width()
        self._width_box.setRange(self._min_width, self._max_width)
        self._height_box.setRange(self._min_height, self._max_height)
        self.setValue(size_value)

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
            self.valueChanged.emit(QSize(self._width, self._height))

    def _height_changed_slot(self, new_height: int) -> None:
        if self._height != new_height:
            if not self._min_height <= new_height <= self._max_height:
                raise ValueError(f'{new_height} not in range {self._min_width} - {self._max_width}')
            self._height = new_height
            self.valueChanged.emit(QSize(self._width, self._height))
