"""Represents configurable typed values loaded from JSON definitions."""
import logging
from copy import deepcopy
from typing import Any, Optional

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from src.util.parameter import Parameter, get_parameter_type, TYPE_DICT, TYPE_INT, TYPE_FLOAT, TYPE_QSIZE, ParamTypeList

logger = logging.getLogger(__name__)

VALUE_KEY = 'value'

# The attributes `ConfigEntry.snapshot_state` copies. An attribute that tests can change and that is missing here
# carries over from one test to the next.
_STATE_ATTRIBUTES = ('_value', '_default_value', '_options', '_default_options', '_minimum', '_maximum', '_step')


# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'config.config_entry'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


INVALID_INNER_KEY_TYPE_ERROR = _tr('Tried to set "{key}.{inner_key}" to value "{value}", but {key} is type'
                                   ' "{type_name}"')
INVALID_INNER_KEY_ERROR = _tr('Tried to read {key}.{inner_key} from type {type_name}')
MISSING_OPTION_LIST_ERROR = _tr('Config value "{key}" does not have an associated options list')
UNEXPECTED_TYPE_ERROR = _tr('unexpected type:')
MISSING_VALUE_ERROR = _tr('{key}: missing value')


def _json_scalar(value: Any) -> Any:
    """Converts a value to its JSON form, writing sizes as 'WxH'."""
    if isinstance(value, QSize):
        return f'{value.width()}x{value.height()}'
    return value


class DefinitionKey:
    """Config definition key constants."""
    DEFAULT = 'default'
    TYPE = 'type'
    LABEL = 'label'
    CATEGORY = 'category'
    SUBCATEGORY = 'subcategory'
    TOOLTIP = 'description'
    OPTIONS = 'options'
    RANGE = 'range_options'
    SAVED = 'saved'
    # Optional bool. When true, a saved entry stays in the config file even when it equals the default, so a later
    # change to the default doesn't alter it for installs that already saved it.
    PINNED = 'pinned'
    # Optional string naming the control a settings window shows for a string value: one of the `ControlHint`
    # constants. A string with no hint is a text field.
    CONTROL = 'control'


class ControlHint:
    """Values of a definition's `control` key."""
    # A color string. An empty value means "use the theme's color" and the control offers that state.
    COLOR = 'color'
    # A color string that is always set.
    COLOR_REQUIRED = 'color_required'
    # A directory path, with a Browse button.
    DIRECTORY = 'directory'


class DefinitionType:
    """Config definition type constants."""
    QSIZE = 'Size'
    INT = 'int'
    FLOAT = 'float'
    STR = 'string'
    BOOL = 'bool'
    LIST = 'list'
    DICT = 'dict'


class RangeKey:
    """Config definition range key constants."""
    MIN = 'min'
    MAX = 'max'
    STEP = 'step'
    ALL = [MIN, MAX, STEP]


class ConfigEntry(Parameter):
    """Represents a configurable typed value with associated limits and descriptions."""

    def __init__(self,
                 key: str,
                 initial_value: Any,
                 label: str,
                 category: str,
                 subcategory: Optional[str],
                 tooltip: str,
                 options: Optional[ParamTypeList] = None,
                 range_options: Optional[dict[str, int | float]] = None,
                 save_json: bool = True,
                 pinned: bool = False,
                 control_hint: Optional[str] = None) -> None:
        minimum = None
        maximum = None
        step = None
        if range_options is not None:
            minimum = None if RangeKey.MIN not in range_options else range_options[RangeKey.MIN]
            maximum = None if RangeKey.MAX not in range_options else range_options[RangeKey.MAX]
            step = None if RangeKey.STEP not in range_options else range_options[RangeKey.STEP]
        super().__init__(label,
                         get_parameter_type(initial_value),
                         initial_value,
                         tooltip,
                         minimum,
                         maximum,
                         step)
        self._key = key
        self._value = deepcopy(initial_value)  # Mutating the value in place must not change the default.
        self._default_range = (minimum, maximum, step)
        self._category = category
        self._subcategory = subcategory
        self.save_json = save_json
        self.pinned = pinned
        self.control_hint = control_hint
        self._default_options: Optional[ParamTypeList] = None
        if options is not None:
            self._default_options = [*options]
            self.set_valid_options(options)

    def set_value(self,
                  value: Any,
                  add_missing_options: bool = False,
                  inner_key: Optional[str] = None) -> bool:
        """Updates the value or one of its properties, returning whether the value changed."""
        # Handle inner key changes:
        if inner_key is not None:
            if isinstance(self._value, dict):
                prev_value = None if inner_key not in self._value else self._value[inner_key]
                value_changed = prev_value != value
                self._value[inner_key] = value
                return value_changed
            raise TypeError(INVALID_INNER_KEY_TYPE_ERROR.format(key=self._key, inner_key=inner_key, value=value,
                                                                type_name=self.type_name))

        # Handle changes to values with predefined options lists:
        if self.options is not None and value not in self.options and add_missing_options:
            valid_options = self.options
            valid_options.append(value)
            self.set_valid_options(valid_options)

        # Validate type, range, accepted options:
        self.validate(value, True)
        value_changed = self._value != value
        self._value = value
        return value_changed

    def get_value(self, inner_key: Optional[str] = None) -> Any:
        """Gets the current value, or an inner value if inner_key is not None."""
        if inner_key is not None:
            if isinstance(self._value, dict):
                return None if inner_key not in self._value else self._value[inner_key]
            if inner_key == RangeKey.MIN:
                return self.minimum
            if inner_key == RangeKey.MAX:
                return self.maximum
            if inner_key == RangeKey.STEP:
                return self.single_step
            raise TypeError(INVALID_INNER_KEY_ERROR.format(key=self._key, inner_key=inner_key,
                                                           type_name=type(self._value)))
        if isinstance(self._value, QSize):
            return QSize(self._value)
        if isinstance(self._value, list):
            return [*self._value]
        if isinstance(self._value, dict):
            return self._value.copy()
        return self._value

    def snapshot_state(self) -> dict[str, Any]:
        """Returns a copy of the entry's value, default, options and range, for `restore_state`."""
        return {name: deepcopy(getattr(self, name)) for name in _STATE_ATTRIBUTES}

    def restore_state(self, state: dict[str, Any]) -> None:
        """Restores the value, default, options and range saved by `snapshot_state`. `state` stays unchanged."""
        for name, value in state.items():
            setattr(self, name, deepcopy(value))

    def default_options(self) -> Optional[ParamTypeList]:
        """Returns a copy of the list of default options provided when the entry was created, if any."""
        if self._default_options is None:
            return None
        return [*self._default_options]

    @property
    def category(self) -> str:
        """Gets the config option's category name."""
        return self._category

    @property
    def subcategory(self) -> Optional[str]:
        """Gets the config option's subcategory name, if any."""
        return self._subcategory

    @property
    def option_index(self) -> int:
        """ Returns the index of the selected option."""
        if self.options is None:
            raise RuntimeError(MISSING_OPTION_LIST_ERROR.format(key=self._key))
        return self.options.index(self._value)

    def add_option(self, option: Any) -> None:
        """Adds a new item to the list of accepted options."""
        if self._options is None:
            raise RuntimeError(MISSING_OPTION_LIST_ERROR.format(key=self._key))
        options = self._options
        if option not in options:
            options.append(option)
        self.set_valid_options(options)

    def is_default_state(self) -> bool:
        """Returns whether the value, and for ranged entries the min, max and step, all match the definition."""
        return self._value == self._default_value and \
            (self.minimum, self.maximum, self.single_step) == self._default_range

    def default_json_state(self) -> tuple[Any, tuple[Any, ...]]:
        """Returns the definition's default as `json_state` describes saved values: (value, (min, max, step))."""
        return _json_scalar(self._default_value), tuple(_json_scalar(item) for item in self._default_range)

    def json_state(self, json_value: Any) -> tuple[Any, tuple[Any, ...]]:
        """Splits a saved JSON value into (value, (min, max, step)), filling absent range parts from the default."""
        default_range = self.default_json_state()[1]
        if isinstance(json_value, dict) and self.type_name != TYPE_DICT:
            saved_range = tuple(json_value.get(inner_key) for inner_key in RangeKey.ALL)
            return json_value.get(VALUE_KEY), tuple(saved if saved is not None else default
                                                    for saved, default in zip(saved_range, default_range))
        return json_value, default_range

    def save_to_json_dict(self, json_dict: dict[str, Any]) -> None:
        """Adds the value to a dict in a format that can be written to a JSON file.

        Nothing is added for an entry that is unsaved, or that matches its definition and isn't pinned.
        """
        if not self.save_json or (self.is_default_state() and not self.pinned):
            return
        minimum = self.minimum
        maximum = self.maximum
        step = self.single_step
        if minimum is not None or maximum is not None or step is not None:
            json_dict[self._key] = {}
            for config_param, inner_key in ((minimum, RangeKey.MIN),
                                            (maximum, RangeKey.MAX),
                                            (step, RangeKey.STEP),
                                            (self._value, VALUE_KEY)):
                if config_param is None:
                    continue
                json_dict[self._key][inner_key] = _json_scalar(config_param)
        else:
            json_dict[self._key] = _json_scalar(self._value)

    def load_from_json_dict(self, json_dict: dict[str, Any]) -> None:
        """Reads the value from a dict that was loaded from a JSON file."""
        if self._key not in json_dict:
            return

        def _apply_type(value, param_type):
            if param_type == TYPE_INT:
                return int(value)
            if param_type == TYPE_FLOAT:
                return float(value)
            if param_type == TYPE_QSIZE:
                width, height = (int(n) for n in value.split('x'))
                return QSize(width, height)
            raise ValueError(UNEXPECTED_TYPE_ERROR, param_type)

        json_value = json_dict[self._key]
        if isinstance(json_value, dict) and self.type_name != TYPE_DICT:
            if self.type_name in (TYPE_INT, TYPE_FLOAT, TYPE_QSIZE):
                if RangeKey.MIN in json_value and json_value[RangeKey.MIN] is not None:
                    self.minimum = _apply_type(json_value[RangeKey.MIN], self.type_name)
                if RangeKey.MAX in json_value and json_value[RangeKey.MAX] is not None:
                    self.maximum = _apply_type(json_value[RangeKey.MAX], self.type_name)
                if RangeKey.STEP in json_value and json_value[RangeKey.STEP] is not None:
                    step_type = TYPE_FLOAT if self.type_name == TYPE_FLOAT else TYPE_INT
                    self.single_step = _apply_type(json_value[RangeKey.STEP], step_type)
                if VALUE_KEY not in json_value:
                    logger.error(MISSING_VALUE_ERROR.format(key=self._key))
                    json_value = self.default_value
                else:
                    json_value = json_value[VALUE_KEY]
            else:
                logger.error(f'"{self.name}" expected type {self.type_name}, got dict. Replacing with default value.')
                json_value = self.default_value

        if self.type_name == TYPE_QSIZE:
            json_value = _apply_type(json_value, TYPE_QSIZE)
        if self.options is not None and len(self.options) == 0:
            self.set_valid_options([json_value])
        if not self.validate(json_value):
            logger.error(f'{self.name} skipping invalid saved value {json_value}')
        else:
            self._value = json_value
