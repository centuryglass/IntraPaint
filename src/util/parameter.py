"""Represents a value with a fixed type, descriptive metadata, and optional limitations and defaults."""
from typing import Any, Optional, TypeAlias, List, cast, Callable

from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QWidget, QComboBox, QDoubleSpinBox, QLineEdit, QCheckBox, QHBoxLayout, QLabel

from src.ui.widget.big_int_spinbox import BigIntSpinbox
from src.ui.widget.size_field import SizeField
from src.ui.widget.slider_spinbox import IntSliderSpinbox, FloatSliderSpinbox
from src.util.shared_constants import INT_MIN, INT_MAX, FLOAT_MIN, FLOAT_MAX

# Accepted parameter types:
TYPE_INT = 'int'
TYPE_FLOAT = 'float'
TYPE_STR = 'str'
TYPE_BOOL = 'bool'
TYPE_QSIZE = 'Size'
TYPE_LIST = 'list'
TYPE_DICT = 'dict'

WIDTH_LABEL = "W:"
HEIGHT_LABEL = "H:"

PARAMETER_TYPES = [TYPE_INT, TYPE_FLOAT, TYPE_STR, TYPE_BOOL, TYPE_QSIZE, TYPE_LIST, TYPE_DICT]


def get_parameter_type(value: Any) -> str:
    """Returns a values parameter type, or throws TypeError if it isn't one of the expected types."""
    if isinstance(value, int):
        return TYPE_INT
    if isinstance(value, float):
        return TYPE_FLOAT
    if isinstance(value, str):
        return TYPE_STR
    if isinstance(value, bool):
        return TYPE_BOOL
    if isinstance(value, QSize):
        return TYPE_QSIZE
    if isinstance(value, list):
        return TYPE_LIST
    if isinstance(value, dict):
        return TYPE_DICT
    raise TypeError(f'Unsupported type encountered: {type(value)}')


ParamType: TypeAlias = int | float | str | bool | QSize | list | dict


class Parameter:
    """Represents a value with a fixed type, descriptive metadata, and optional limitations and defaults."""

    def __init__(self,
                 name: str,
                 value_type: str,
                 default_value: Optional[ParamType] = None,
                 description: str = '',
                 minimum: Optional[int | float] = None,
                 maximum: Optional[int | float] = None,
                 single_step: Optional[int | float] = None) -> None:
        self._name = name
        assert len(name) > 0
        if value_type not in PARAMETER_TYPES:
            raise ValueError(f'Invalid parameter type for {name}: {value_type}')
        self._type = value_type
        self._default_value = default_value
        self._options = []
        if default_value is not None:
            default_type = get_parameter_type(default_value)
            if default_type != value_type:
                raise TypeError(f'Value {name}: type is {value_type}, but default value was type {default_type}')
        self._description = description
        self._minimum = minimum
        self._maximum = maximum
        self._step = single_step

        if minimum is not None or maximum is not None or single_step is not None:
            if value_type not in (TYPE_INT, TYPE_FLOAT, TYPE_QSIZE):
                raise TypeError(f'Param {name}: range parameter found for invalid type {value_type}')
            for range_param in (minimum, maximum, single_step):
                if range_param is None:
                    continue
                range_param_type = get_parameter_type(range_param)
                if value_type == TYPE_QSIZE:
                    if range_param_type != TYPE_INT:
                        raise TypeError(f'Param {name}: size parameter step values must be int or None, found'
                                        f' {range_param_type}')
                elif range_param_type != value_type:
                    raise TypeError(f'Param {name}: range parameter type {range_param_type} does not match value type'
                                    f' {value_type}')

    def set_valid_options(self, valid_options: List[ParamType]) -> None:
        """Set a restricted list of valid options to accept."""
        for option in valid_options:
            option_type = get_parameter_type(option)
            if option_type != self._type:
                raise TypeError(f'Param {self.name}: option parameter type {option_type} does not match value type'
                                f' {self._type}')
            if (self._maximum is not None or self._minimum is not None) and not _in_range(option, self._minimum,
                                                                                          self._maximum):

                raise ValueError(f'Param {self.name}: Option {option} is not in range {self._minimum}-{self._maximum}')
        if self._default_value is not None and self._default_value not in valid_options:
            raise ValueError(f'Param {self.name}: options list excludes default value {self._default_value}')
        self._options = [*valid_options]

    @property
    def name(self) -> str:
        """Returns the parameter's display name."""
        return self._name

    @property
    def type_name(self) -> str:
        """Returns the parameter's type name."""
        return self._type

    @property
    def default_value(self) -> Optional[ParamType]:
        """Returns the parameter's default value."""
        return self._default_value

    @property
    def description(self) -> str:
        """Returns the parameter's description string."""
        return self._description

    @property
    def minimum(self) -> Optional[int | float]:
        """Returns the parameter's minimum value, or None if ranges are unspecified or not applicable."""
        return self._minimum

    @property
    def maximum(self) -> Optional[int | float]:
        """Returns the parameter's maximum value, or None if ranges are unspecified or not applicable."""
        return self._maximum

    @property
    def single_step(self) -> Optional[int | float]:
        """Returns the parameter's step value, or None if ranges are unspecified or not applicable."""
        return self._step

    def validate(self, test_value: Any) -> bool:
        """Returns whether a test value is acceptable for this parameter"""
        try:
            test_type = get_parameter_type(test_value)
            if test_type != self._type:
                return False
        except TypeError:
            return False
        if (self._maximum is not None or self._minimum is not None) and not _in_range(test_value, self._minimum,
                                                                                      self._maximum):
            return False
        if len(self._options) > 0:
            return test_value in self._options
        return True

    def get_input_widget(self) -> QWidget:
        """Creates a widget that can be used to set this parameter."""
        input_field = None
        if len(self._options) > 0:
            combo_box = QComboBox()
            for option in self._options:
                combo_box.addItem(str(option), userData=option)
            if self._default_value is not None:
                index = combo_box.find(str(self._default_value))
                assert index >= 0
                combo_box.setCurrentIndex(index)
            input_field = cast(QWidget, combo_box)
        elif self._type == TYPE_INT:
            spin_box = IntSliderSpinbox()
            spin_box.setMinimum(self._minimum if self._minimum is not None else INT_MIN)
            spin_box.setMaximum(self._maximum if self._maximum is not None else INT_MAX)
            if self._step is not None:
                spin_box.setSingleStep(self._step)
            spin_box.setValue(self._default_value if self._default_value is not None else max(0, spin_box.minimum()))
            if self._minimum is None or self._maximum is None:
                spin_box.set_slider_included(False)
            input_field = cast(QWidget, spin_box)
        elif self._type == TYPE_FLOAT:
            spin_box = FloatSliderSpinbox()
            spin_box.setMinimum(self._minimum if self._minimum is not None else FLOAT_MIN)
            spin_box.setMaximum(self._maximum if self._maximum is not None else FLOAT_MAX)
            if self._step is not None:
                spin_box.setSingleStep(self._step)
            spin_box.setValue(self._default_value if self._default_value is not None else max(0.0, spin_box.minimum()))
            if self._minimum is None or self._maximum is None:
                spin_box.set_slider_included(False)
            input_field = cast(QWidget, spin_box)
        elif self._type == TYPE_STR:
            text_box = QLineEdit()
            if self._default_value is not None:
                text_box.setText(self._default_value)
            input_field = cast(QWidget, text_box)
        elif self._type == TYPE_BOOL:
            check_box = QCheckBox()
            if self._default_value is not None:
                check_box.setChecked(self._default_value)
            input_field = cast(QWidget, check_box)
        elif self._type == TYPE_QSIZE:
            size_field = SizeField()
            if self._minimum is not None:
                size_field.minimum = self._minimum
            if self._maximum is not None:
                size_field.maximum = self._maximum
            if self._step is not None:
                size_field.set_single_step(self._step)
            if self._default_value is not None:
                size_field.value = self._default_value
            input_field = cast(QWidget, size_field)
        else:
            RuntimeError(f'get_input_widget not supported for type {self._type}')
        assert input_field is not None
        if len(self._description) > 0:
            input_field.setToolTip(self._description)
        return input_field

    def get_widget_param_value(self, input_widget: QWidget) -> ParamType:
        """Return the parameter value from a field provided by get_input_widget."""
        if isinstance(input_widget, QComboBox):
            input_widget = cast(QComboBox, input_widget)
            value = input_widget.currentData()
            assert value in self._options
            return value
        if isinstance(input_widget, QCheckBox):
            assert self._type == TYPE_BOOL
            return input_widget.isChecked()
        if isinstance(input_widget, QLineEdit):
            assert self._type == TYPE_STR
            return input_widget.text()
        if hasattr(input_widget, 'value'):
            return input_widget.value()
        raise ValueError(f'Expected valid input widget, got {input_widget}')

    def connect_widget_change_handler(self, input_widget: QWidget, change_slot: Callable[[Any], None]) -> None:
        """Connect a change signal to a field provided by get_input_widget"""
        if isinstance(input_widget, QComboBox):
            assert len(self._options) > 0
            input_widget = cast(QComboBox, input_widget)
            input_widget.currentIndexChanged.connect(change_slot)
        elif isinstance(input_widget, QCheckBox):
            assert self._type == TYPE_BOOL
            input_widget = cast(QCheckBox, input_widget)
            input_widget.stateChanged.connect(change_slot)
        elif isinstance(input_widget, QLineEdit):
            assert self._type == TYPE_STR
            input_widget.textChanged.connect(change_slot)
        elif isinstance(input_widget, SizeField):
            assert self._type == TYPE_QSIZE
            input_widget.value_changed.connect(change_slot)
        elif hasattr(input_widget, 'valueChanged'):
            input_widget.valueChanged.connect(change_slot)
        else:
            raise ValueError(f'Expected valid input widget, got {input_widget}')


def _in_range(value: int | float | QSize,
              minimum: Optional[int | float | QSize],
              maximum: Optional[int | float | QSize]) -> bool:
    value_type = get_parameter_type(value)
    if minimum is not None and get_parameter_type(minimum) != value_type:
        raise TypeError(f'Value type={value_type} but minimum was type {get_parameter_type(minimum)}')
    if maximum is not None and get_parameter_type(maximum) != value_type:
        raise TypeError(f'Value type={value_type} but maximum was type {get_parameter_type(maximum)}')
    if minimum is None:
        if value_type == TYPE_INT:
            minimum = INT_MIN
        elif value_type == TYPE_FLOAT:
            minimum = FLOAT_MIN
        else:  # QSize
            minimum = QSize(INT_MIN, INT_MIN)
    if maximum is None:
        if value_type == TYPE_INT:
            maximum = INT_MAX
        elif value_type == TYPE_FLOAT:
            minimum = FLOAT_MAX
        else:  # QSize
            minimum = QSize(INT_MAX, INT_MAX)
    if value_type == TYPE_QSIZE:
        return minimum.width() <= value.width() <= maximum.width() \
            and minimum.height() <= value.height() <= maximum.height()
    return minimum <= value <= maximum

