"""`NumberField` with a fill that shows the value's place in a finite range. See `number_field.py` for the shared
behavior."""
from typing import Optional

from PySide6.QtWidgets import QWidget

from src.ui.input_fields.number_field import NumberField
from src.util.parameter import Parameter, TYPE_FLOAT, TYPE_INT


class SliderField(NumberField):
    """A `NumberField` over a finite range, drawn with a fill from the left edge to the value's position.

    A drag moves the value by the fraction of the range the pointer moved across the field's width, so the fill's edge
    follows the pointer.

    Parameters
    ----------
    label: str
        Text on the left of the field.
    value: int | float
        Initial value.
    minimum: int | float
        Smallest accepted value, shown as an empty fill.
    maximum: int | float
        Largest accepted value, shown as a full fill.
    **kwargs
        The remaining `NumberField` options.
    """

    def __init__(self, label: str, value: int | float, minimum: int | float, maximum: int | float,
                 parent: Optional[QWidget] = None, **kwargs) -> None:
        if minimum >= maximum:
            raise ValueError(f'SliderField needs minimum < maximum, got {minimum} and {maximum}')
        super().__init__(label, value, minimum, maximum, parent=parent, **kwargs)

    def set_range(self, minimum: Optional[int | float], maximum: Optional[int | float]) -> None:
        """Sets the accepted range, which must be finite."""
        if minimum is None or maximum is None or minimum >= maximum:
            raise ValueError(f'SliderField needs minimum < maximum, got {minimum} and {maximum}')
        super().set_range(minimum, maximum)

    def _fill_fraction(self) -> Optional[float]:
        assert self._minimum is not None and self._maximum is not None
        return (self._value - self._minimum) / (self._maximum - self._minimum)

    def _scrub_delta(self, delta_x: int) -> int | float:
        assert self._minimum is not None and self._maximum is not None
        return delta_x / max(self.width(), 1) * (self._maximum - self._minimum)


def number_field_for_parameter(parameter: Parameter, value: Optional[int | float] = None, **kwargs) -> NumberField:
    """Creates a `SliderField` for an int or float `Parameter` with a finite range, or a `NumberField` for one without.

    The label, tooltip, limits and step come from the parameter. The initial value is `value`, or the parameter's
    default. `kwargs` are passed on as `NumberField` options.

    Raises
    ------
    TypeError
        If the parameter isn't an int or float.
    """
    if parameter.type_name not in (TYPE_INT, TYPE_FLOAT):
        raise TypeError(f'Parameter {parameter.name} has type {parameter.type_name}, expected a number')
    if value is None:
        value = parameter.default_value if isinstance(parameter.default_value, (int, float)) else 0
    default_step = 1 if parameter.type_name == TYPE_INT else 0.01
    step = parameter.single_step if parameter.single_step is not None else default_step
    minimum, maximum = parameter.minimum, parameter.maximum
    field: NumberField
    if minimum is not None and maximum is not None:
        field = SliderField(parameter.name, value, minimum, maximum, step=step, **kwargs)
    else:
        field = NumberField(parameter.name, value, minimum, maximum, step=step, **kwargs)
    field.setToolTip(parameter.description)
    return field
