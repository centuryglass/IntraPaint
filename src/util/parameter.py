"""Represents a value with a fixed type, descriptive metadata, and optional limitations and defaults."""
from typing import Any, Optional, TypeAlias, List, cast

from PySide6.QtCore import QSize

from src.ui.input_fields.big_int_spinbox import BigIntSpinbox
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.combo_box import ComboBox
from src.ui.input_fields.dual_toggle import DualToggle
from src.ui.input_fields.line_edit import LineEdit
from src.ui.input_fields.plain_text_edit import PlainTextEdit
from src.ui.input_fields.size_field import SizeField
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox, FloatSliderSpinbox
from src.util.shared_constants import INT_MIN, INT_MAX, FLOAT_MIN, FLOAT_MAX

# Accepted parameter types:
TYPE_BOOL = 'bool'
TYPE_INT = 'int'
TYPE_FLOAT = 'float'
TYPE_STR = 'str'
TYPE_QSIZE = 'Size'
TYPE_LIST = 'list'
TYPE_DICT = 'dict'

WIDTH_LABEL = 'W:'
HEIGHT_LABEL = 'H:'

PARAMETER_TYPES = [TYPE_INT, TYPE_FLOAT, TYPE_STR, TYPE_BOOL, TYPE_QSIZE, TYPE_LIST, TYPE_DICT]


def get_parameter_type(value: Any) -> str:
    """Returns a values parameter type, or throws TypeError if it isn't one of the expected types."""
    if isinstance(value, bool):
        return TYPE_BOOL
    if isinstance(value, int):
        return TYPE_INT
    if isinstance(value, float):
        return TYPE_FLOAT
    if isinstance(value, str):
        return TYPE_STR
    if isinstance(value, QSize):
        return TYPE_QSIZE
    if isinstance(value, list):
        return TYPE_LIST
    if isinstance(value, dict):
        return TYPE_DICT
    raise TypeError(f'Unsupported type encountered: {type(value)}')


ParamType: TypeAlias = int | float | str | bool | QSize | list | dict

DynamicFieldWidget: TypeAlias = (BigIntSpinbox | CheckBox | ComboBox | DualToggle | LineEdit | PlainTextEdit |
                                 SizeField | IntSliderSpinbox | FloatSliderSpinbox)


class Parameter:
    """Represents a value with a fixed type, descriptive metadata, and optional limitations and defaults."""

    def __init__(self,
                 name: str,
                 value_type: str,
                 default_value: Optional[ParamType] = None,
                 description: str = '',
                 minimum: Optional[int | float | QSize] = None,
                 maximum: Optional[int | float | QSize] = None,
                 single_step: Optional[int | float] = None) -> None:
        self._name = name
        assert len(name) > 0
        if value_type not in PARAMETER_TYPES:
            raise ValueError(f'Invalid parameter type for {name}: {value_type}')
        self._type = value_type
        self._default_value = default_value
        self._options: Optional[List[ParamType]] = None
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
            if minimum is not None:
                self.minimum = minimum
            if maximum is not None:
                self.maximum = maximum
            if single_step is not None:
                self.single_step = single_step

    def set_valid_options(self, valid_options: List[ParamType]) -> None:
        """Set a restricted list of valid options to accept."""
        for option in valid_options:
            option_type = get_parameter_type(option)
            if option_type != self._type:
                raise TypeError(f'Param {self.name}: option parameter type {option_type} does not match value type'
                                f' {self._type}')
            if self._maximum is not None or self._minimum is not None:
                assert isinstance(option, (int, float, QSize))
                if not _in_range(option, self._minimum, self._maximum):
                    raise ValueError(f'Param {self.name}: Option {option} is not in range'
                                     f' {self._minimum}-{self._maximum}')
        if self._default_value is not None and self._default_value not in valid_options and len(valid_options) > 0:
            self._default_value = valid_options[0]
        self._options = [*valid_options]

    @property
    def options(self) -> Optional[List[ParamType]]:
        """Accesses the list of accepted options, if any."""
        if self._options is None:
            return None
        return [*self._options]

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

    @minimum.setter
    def minimum(self, new_minimum: Any) -> None:
        min_type = get_parameter_type(new_minimum)
        if min_type != self.type_name:
            raise TypeError(f'Param {self.name}: minimum type {min_type} does not match value type'
                            f' {self.type_name}')
        self._minimum = new_minimum

    @property
    def maximum(self) -> Optional[int | float]:
        """Returns the parameter's maximum value, or None if ranges are unspecified or not applicable."""
        return self._maximum

    @maximum.setter
    def maximum(self, new_maximum: Any) -> None:
        max_type = get_parameter_type(new_maximum)
        if max_type != self.type_name:
            raise TypeError(f'Param {self.name}: maximum type {max_type} does not match value type'
                            f' {self.type_name}')
        self._maximum = new_maximum

    @property
    def single_step(self) -> Optional[int | float]:
        """Returns the parameter's step value, or None if ranges are unspecified or not applicable."""
        return self._step

    @single_step.setter
    def single_step(self, single_step: int | float) -> None:
        if (self.type_name == TYPE_FLOAT and not isinstance(single_step, float)) \
                or (self.type_name != TYPE_FLOAT and not isinstance(single_step, int)):
            raise TypeError(f'Param {self.name}: invalid step value {single_step} for type {self.type_name}')
        self._step = single_step

    def validate(self, test_value: Any, raise_on_failure=False) -> bool:
        """Returns whether a test value is acceptable for this parameter"""
        try:
            if self.type_name == TYPE_INT and ((self.minimum is not None and self.minimum < INT_MIN) or
                                               (self.maximum is not None and self.maximum > INT_MAX)):
                test_value = int(test_value)  # BigIntSpinbox needs to emit as str, so convert before validating.
            test_type = get_parameter_type(test_value)
            if test_type != self._type:
                if raise_on_failure:
                    raise TypeError(f'{self.name} parameter: expected {self._type}, got {test_type}')
                return False
        except TypeError as err:
            if raise_on_failure:
                raise TypeError(f'{self.name} parameter: expected {self._type},'
                                f' got {test_value} {type(test_value)}') from err
            return False
        if (self._maximum is not None or self._minimum is not None) and not _in_range(test_value, self._minimum,
                                                                                      self._maximum):
            if raise_on_failure:
                raise ValueError(f'{self.name} parameter: {test_value} not in range {self._minimum}-{self.maximum}')
            return False
        if self._options is not None and len(self._options) > 0 and test_value not in self._options:
            if raise_on_failure:
                raise ValueError(f'{self.name} parameter: {test_value} not found in {len(self._options)} available'
                                 f' options {self._options}')
            return False
        return True

    def get_input_widget(self, multi_line=False) -> DynamicFieldWidget:
        """Creates a widget that can be used to set this parameter."""
        if multi_line and self._type != TYPE_STR:
            raise ValueError(f'multi_line=True is only valid for text parameters, value {self.name}'
                             f' is {self.type_name}')
        if self._options is not None and len(self._options) > 0:
            if multi_line:
                raise ValueError('multi_line=True is not valid for parameters with fixed option lists')
            assert self.type_name == TYPE_STR, 'Widget support for non-string option lists is not implemented'
            if len(self._options) == 2:
                toggle = DualToggle(parent=None, options=cast(list[str], self.options))
                assert self._default_value is None or isinstance(self._default_value, str)
                toggle.setValue(self._default_value)
                input_field = cast(DynamicFieldWidget, toggle)
            else:
                combo_box = ComboBox()
                for option in self._options:
                    combo_box.addItem(str(option), userData=option)
                if self._default_value is not None:
                    index = combo_box.findText(str(self._default_value))
                    assert index >= 0
                    combo_box.setCurrentIndex(index)
                input_field = cast(DynamicFieldWidget, combo_box)
        elif self._type == TYPE_INT:
            if (self._maximum is not None and self._maximum > INT_MAX) or (self._minimum is not None
                                                                           and self._minimum < INT_MIN):
                spin_box = BigIntSpinbox()
            else:
                spin_box = IntSliderSpinbox()
            spin_box.setMinimum(cast(int, self._minimum) if self._minimum is not None else INT_MIN)
            spin_box.setMaximum(cast(int, self._maximum) if self._maximum is not None else INT_MAX)
            if self._step is not None:
                spin_box.setSingleStep(int(self._step))
            assert self._default_value is None or isinstance(self._default_value, int)
            spin_box.setValue(self._default_value if self._default_value is not None else max(0, spin_box.minimum()))
            if isinstance(spin_box, IntSliderSpinbox) and (self._minimum is None or self._maximum is None):
                spin_box.set_slider_included(False)
            input_field = cast(DynamicFieldWidget, spin_box)
        elif self._type == TYPE_FLOAT:
            spin_box = FloatSliderSpinbox()
            spin_box.setMinimum(cast(float, self._minimum) if self._minimum is not None else FLOAT_MIN)
            spin_box.setMaximum(cast(float, self._maximum) if self._maximum is not None else FLOAT_MAX)
            if self._step is not None:
                spin_box.setSingleStep(float(self._step))
            assert self._default_value is None or isinstance(self._default_value, float)
            spin_box.setValue(self._default_value if self._default_value is not None else max(0.0, spin_box.minimum()))
            if self._minimum is None or self._maximum is None:
                spin_box.set_slider_included(False)
            input_field = cast(DynamicFieldWidget, spin_box)
        elif self._type == TYPE_STR:
            text_box: PlainTextEdit | LineEdit = PlainTextEdit() if multi_line else LineEdit()
            if self._default_value is not None:
                assert isinstance(self._default_value, str)
                text_box.setValue(self._default_value)
            input_field = cast(DynamicFieldWidget, text_box)
        elif self._type == TYPE_BOOL:
            check_box = CheckBox()
            if self._default_value is not None:
                check_box.setChecked(bool(self._default_value))
            input_field = cast(DynamicFieldWidget, check_box)
        elif self._type == TYPE_QSIZE:
            size_field = SizeField()
            if self._minimum is not None:
                assert isinstance(self._minimum, QSize)
                size_field.minimum = self._minimum
            if self._maximum is not None:
                assert isinstance(self._maximum, QSize)
                size_field.maximum = self._maximum
            if self._step is not None:
                size_field.set_single_step(int(self._step))
            if self._default_value is not None:
                assert isinstance(self._default_value, QSize)
                size_field.setValue(self._default_value)
            input_field = cast(DynamicFieldWidget, size_field)
        else:
            raise RuntimeError(f'get_input_widget not supported for type {self._type}')
        if len(self._description) > 0:
            input_field.setToolTip(self._description)
        return input_field


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
            maximum = FLOAT_MAX
        else:  # QSize
            maximum = QSize(INT_MAX, INT_MAX)
    if value_type == TYPE_QSIZE:
        assert isinstance(minimum, QSize)
        assert isinstance(maximum, QSize)
        assert isinstance(value, QSize)
        return minimum.width() <= value.width() <= maximum.width() \
            and minimum.height() <= value.height() <= maximum.height()
    assert isinstance(minimum, (int, float)),  f'Expected numeric minimum, got {minimum}'
    assert isinstance(maximum, (int, float)),  f'Expected numeric maximum, got {maximum}'
    return minimum <= value <= maximum
