"""Creates input widgets for the library's ControlNet `ParameterDef` values.

Labels and tooltips come from `src.util.parameter_def_labels`.
"""
from typing import Any, Callable, cast

from sd_backend_client import ParameterDef

from src.ui.input_fields.number_field import NumberField
from src.ui.input_fields.slider_field import number_field_for_parameter
from src.util.parameter_def_labels import parameter_label, parameter_tooltip
from src.util.parameter import Parameter, DynamicFieldWidget, TYPE_BOOL, TYPE_FLOAT, TYPE_INT, TYPE_STR
from src.util.shared_constants import INT_MAX, INT_MIN


def _parameter_and_value(param: ParameterDef, value: Any) -> tuple[Parameter, Any]:
    """Returns the `Parameter` a widget for `param` is built from, and `value` converted to its type."""
    default = param.default_value
    minimum, maximum, step = param.min_val, param.max_val, param.step_val
    if isinstance(default, int) and not isinstance(default, bool) \
            and any(isinstance(limit, float) and limit % 1 != 0 for limit in (minimum, maximum, step)):
        default = float(default)
        value = float(value)
    if isinstance(default, float):
        minimum = None if minimum is None else float(minimum)
        maximum = None if maximum is None else float(maximum)
        step = None if step is None else float(step)
    elif isinstance(default, int) and not isinstance(default, bool):
        minimum = None if minimum is None else round(minimum)
        maximum = None if maximum is None else round(maximum)
        step = None if step is None else round(step)
    elif default is not None:
        minimum = maximum = step = None
    value_type = {bool: TYPE_BOOL, int: TYPE_INT, float: TYPE_FLOAT, str: TYPE_STR}[type(default)]
    parameter = Parameter(parameter_label(param), value_type, default, parameter_tooltip(param), minimum, maximum,
                          step)
    if param.option_list is not None and len(param.option_list) > 0:
        parameter.set_valid_options(cast(Any, list(param.option_list)))
    return parameter, value


def create_parameter_widget(param: ParameterDef, value: Any,
                            on_changed: Callable[[Any], None],
                            multiline: bool = False) -> DynamicFieldWidget:
    """Creates an input widget for a parameter, initialized to a value.

    Parameters
    ----------
    param: ParameterDef
        The parameter definition, supplying the value type, limits and options.
    value: Any
        The initial widget value. It falls back to the parameter's default value if the widget rejects it.
    on_changed: Callable[[Any], None]
        Called with the new value whenever the user changes the widget.
    multiline: bool, default=False
        Whether a free-form text parameter uses a multi-line text box.
    """
    parameter, value = _parameter_and_value(param, value)
    widget = parameter.get_input_widget(multiline and param.option_list is None and parameter.type_name == TYPE_STR)
    widget.setValue(value if parameter.validate(value) else parameter.default_value)  # type: ignore[arg-type]
    widget.valueChanged.connect(on_changed)
    return widget


def is_numeric_field_parameter(param: ParameterDef) -> bool:
    """Returns whether `create_parameter_field` makes a `NumberField` for a parameter, which carries its own label."""
    default = param.default_value
    return isinstance(default, (int, float)) and not isinstance(default, bool) \
        and (param.option_list is None or len(param.option_list) == 0)


def create_parameter_field(param: ParameterDef, value: Any, on_changed: Callable[[Any], None]) -> NumberField:
    """Creates a `SliderField` for a numeric parameter with a finite range that fits an int, or a `NumberField`
    otherwise, initialized to a value. The field carries the parameter's label.

    `value` falls back to the parameter's default when the parameter rejects it. `on_changed` is called with each new
    value.

    Raises
    ------
    TypeError
        If `is_numeric_field_parameter` is false for the parameter.
    """
    if not is_numeric_field_parameter(param):
        raise TypeError(f'Parameter {param.key} is not numeric')
    parameter, value = _parameter_and_value(param, value)
    if not parameter.validate(value):
        value = parameter.default_value
    minimum, maximum = parameter.minimum, parameter.maximum
    field: NumberField
    if minimum is not None and maximum is not None and (minimum < INT_MIN or maximum > INT_MAX):
        # A fill over a range this wide can't be scrubbed to a chosen value:
        step = parameter.single_step if parameter.single_step is not None else 1
        field = NumberField(parameter.name, value, minimum, maximum, step=step)
        field.setToolTip(parameter.description)
    else:
        field = number_field_for_parameter(parameter, value)
    field.valueChanged.connect(on_changed)
    return field
