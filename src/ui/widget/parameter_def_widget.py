"""Creates input widgets for the library's ControlNet `ParameterDef` values.

Labels and tooltips come from `src.util.parameter_def_labels`.
"""
from typing import Any, Callable, cast

from sd_backend_client import ParameterDef

from src.util.parameter_def_labels import parameter_label, parameter_tooltip
from src.util.parameter import Parameter, DynamicFieldWidget, TYPE_BOOL, TYPE_FLOAT, TYPE_INT, TYPE_STR

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
    widget = parameter.get_input_widget(multiline and param.option_list is None and value_type == TYPE_STR)
    widget.setValue(value if parameter.validate(value) else default)  # type: ignore[arg-type]
    widget.valueChanged.connect(on_changed)
    return widget
