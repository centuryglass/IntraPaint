"""Defines an input parameter and the associated value for a ControlNet preprocessor or unit."""
import json
from typing import Optional, TypeAlias, cast, TypedDict, Any, Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QLabel

from src.ui.input_fields.big_int_spinbox import BigIntSpinbox
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.combo_box import ComboBox
from src.ui.input_fields.dual_toggle import DualToggle
from src.ui.input_fields.line_edit import LineEdit
from src.ui.input_fields.plain_text_edit import PlainTextEdit
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox, FloatSliderSpinbox
from src.util.parameter import Parameter, TYPE_BOOL, TYPE_STR, TYPE_FLOAT, TYPE_INT

ControlParamType: TypeAlias = int | float | str | bool
ControlParamTypeList: TypeAlias = list[int] | list[float] | list[str] | list[bool]

DynamicControlFieldWidget: TypeAlias = (BigIntSpinbox | CheckBox | ComboBox | DualToggle | LineEdit | PlainTextEdit |
                                        IntSliderSpinbox | FloatSliderSpinbox)

CONTROL_PARAMETER_TYPES = [TYPE_INT, TYPE_FLOAT, TYPE_STR, TYPE_BOOL]


class ControlParameter(QObject):
    """Defines an input parameter and the associated value for a ControlNet preprocessor or unit."""

    value_changed = Signal(object)

    def __init__(self,
                 key: str,
                 display_name: str,
                 value_type: str,
                 default_value: ControlParamType,
                 description: str = '',
                 minimum: Optional[int | float] = None,
                 maximum: Optional[int | float] = None,
                 single_step: Optional[int | float] = None,
                 options: Optional[ControlParamTypeList] = None):
        """
        Initializes a new ControlParameter, setting its value to the default.

        Parameters:
        -----------
        key: str
            The string used to reference the parameter in API requests and responses.
        display_name: str
            The name this parameter uses when labeling associated input widgets
        value_type: str
            A string identifying the type of value being stored.  Valid options are defined in src.util.parameter.py
            and listed in src.api.controlnet.control_parameter.py as CONTROL_PARAMETER_TYPES.
        default_value: ControlParamType
            Initial parameter value, to use if no alternative is specified.
        description: str = ''
            Description string to use as a tooltip on associated control widgets.
        minimum: Optional[int | float] = None
            Minimum permitted value, ignored if the parameter is not an int or float.
        maximum: Optional[int | float] = None
            Maximum permitted value, ignored if the parameter is not an int or float.
        single_step: Optional[int | float] = None
            Minimum interval between accepted values, ignored if the parameter is not an int or float.
        options: Optional[ControlParamTypeList] = None
            If not None, accepted values will be limited to the entries in thie slist.
        """
        super().__init__()
        if value_type not in CONTROL_PARAMETER_TYPES:
            raise ValueError(f'Invalid ControlNet parameter type for {key}: {value_type}')
        self._parameter = Parameter(display_name, value_type, default_value, description, minimum, maximum, single_step)
        self._key = key
        self._value = default_value
        self._multiline = False

        # map input widgets to disconnect functions:
        self._input_widgets: dict[DynamicControlFieldWidget, Callable[..., None]] = {}
        if options is not None:
            self._parameter.set_valid_options(options)

    def __deepcopy__(self, memo: dict[int, Any]) -> 'ControlParameter':
        copy_param = ControlParameter.deserialize(self.serialize())
        memo[id(self)] = copy_param
        return copy_param

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ControlParameter):
            return False
        return self._key == other.key and self.value == other.value \
            and self._multiline == other._multiline and self._parameter == other._parameter

    @property
    def display_name(self) -> str:
        """Returns the parameter's display name."""
        return self._parameter.name

    @property
    def key(self) -> str:
        """Returns the key string used when applying this parameter."""
        return self._key

    @property
    def value(self) -> ControlParamType:
        """Accesses the value currently stored with this parameter."""
        return self._value

    @value.setter
    def value(self, new_value: ControlParamType) -> None:
        if new_value == self._value:
            return
        self._parameter.validate(new_value, True)
        self._value = new_value
        self.value_changed.emit(new_value)

    @property
    def default_value(self) -> ControlParamType:
        """Returns the parameter's default value."""
        default_value = self._parameter.default_value
        assert isinstance(default_value, (int, float, str, bool))
        return default_value

    def set_multiline(self, multiline: bool) -> None:
        """Sets whether this parameter should use a multi-line text box.  This will be ignored if the parameter is not
           a string without specific options."""
        self._multiline = multiline

    def get_input_widget(self, include_label: bool) -> tuple[DynamicControlFieldWidget, Optional[QLabel]]:
        """Returns a control widget that synchronizes with this parameter."""
        input_widget = cast(DynamicControlFieldWidget, self._parameter.get_input_widget(self._multiline))
        assert isinstance(input_widget, (BigIntSpinbox, CheckBox, ComboBox, DualToggle, LineEdit, PlainTextEdit,
                          IntSliderSpinbox, FloatSliderSpinbox))
        input_widget.setValue(self._value)  # type: ignore
        label = QLabel(self._parameter.name) if include_label else None

        def _update_parameter(new_value: ControlParamType) -> None:
            self.value = new_value
        input_widget.valueChanged.connect(_update_parameter)

        def _update_control(new_value: ControlParamType) -> None:
            if input_widget.value() != new_value:
                input_widget.setValue(new_value)  # type: ignore
        self.value_changed.connect(_update_control)

        def _disconnect_fn(control_widget=input_widget, param_callback=_update_control,
                           control_callback=_update_parameter) -> None:
            self.value_changed.disconnect(param_callback)
            control_widget.valueChanged.disconnect(control_callback)
        self._input_widgets[input_widget] = _disconnect_fn

        return input_widget, label

    def disconnect_input_widget(self, input_widget: DynamicControlFieldWidget) -> None:
        """Removes any connections between this parameter and an input widget it created."""
        if input_widget in self._input_widgets:
            # Run saved disconnect function:
            self._input_widgets[input_widget]()
            del self._input_widgets[input_widget]

    class _DataFormat(TypedDict):
        key: str
        value: ControlParamType
        parameter: str
        multiline: bool

    def serialize(self) -> str:
        """Serialize this control parameter to a JSON string."""
        data_dict: ControlParameter._DataFormat = {
            'key': self._key,
            'value': self._value,
            'parameter': self._parameter.serialize(),
            'multiline': self._multiline
        }
        return json.dumps(data_dict)

    @staticmethod
    def deserialize(data_str: str) -> 'ControlParameter':
        """Parse a ControlParameter from serialized text data."""
        data_dict = cast(ControlParameter._DataFormat, json.loads(data_str))
        parameter = Parameter.deserialize(data_dict['parameter'])
        value = data_dict['value']
        default_value = parameter.default_value
        min_value = parameter.minimum
        max_value = parameter.maximum
        options = cast(ControlParamTypeList, parameter.options)
        assert isinstance(default_value, (int, float, str, bool))
        assert min_value is None or isinstance(min_value, (int, float))
        assert max_value is None or isinstance(max_value, (int, float))
        assert options is None or isinstance(options, list)
        control_param = ControlParameter(data_dict['key'], parameter.name, parameter.type_name, default_value,
                                         parameter.description, min_value, max_value, parameter.single_step,
                                         options)
        control_param.value = value
        if data_dict['multiline'] is not None:
            control_param.set_multiline(data_dict['multiline'])
        return control_param
