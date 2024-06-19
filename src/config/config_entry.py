"""Represents configurable typed values loaded from JSON definitions."""
import json
from typing import Any, Optional, List, Dict

from PyQt5.QtCore import QSize


class DefinitionKey:
    """Config definition key constants."""
    DEFAULT = 'default'
    TYPE = 'type'
    LABEL = 'label'
    CATEGORY = 'category'
    TOOLTIP = 'description'
    OPTIONS = 'options'
    RANGE = 'range_options'
    SAVED = 'saved'


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


class ConfigEntry:
    """Represents a configurable typed value with associated limits and descriptions."""

    def __init__(self,
                 key: str,
                 initial_value: Any,
                 label: str,
                 category: str,
                 tooltip: str,
                 options: Optional[list[str]] = None,
                 range_options: Optional[dict[str, int | float]] = None,
                 save_json: bool = True) -> None:
        self._key = key
        self._value = initial_value
        self._label = label
        self._category = category
        self._tooltip = tooltip
        self.save_json = save_json
        if options is not None and (not isinstance(options, list) or (initial_value not in options
                                                                      and len(options) > 0)):
            raise ValueError(f'Invalid options for key {key} with initial value {initial_value}: {options}')
        elif isinstance(options, list) and len(options) == 0:
            self._options = [initial_value]  # Entries with empty options lists will load those lists dynamically.
        else:
            self._options = options
        if range_options is not None:
            if not isinstance(initial_value, float) and not isinstance(initial_value, int):
                raise TypeError(f'range_options provided but {key}={initial_value} is not int or float')
            if not isinstance(range_options, dict):
                raise TypeError(f'range_options provided, expected dict but got {range_options}')
            if 'min' not in range_options or 'max' not in range_options:
                raise ValueError(f'min and max missing from range options, got {range_options}')
            range_keys = ['min', 'max', 'step']
            if isinstance(initial_value, float):
                if any(k in range_options and not isinstance(range_options[k], float) for k in range_keys):
                    raise ValueError(f'{key}: initial value is float but range_options are not all float values')
            if isinstance(initial_value, int):
                if any(k in range_options and not isinstance(range_options[k], int) for k in range_keys):
                    raise ValueError(f'{key}: initial value is float but range_options are not all float values')
        self._range_options = range_options

    def set_value(self,
                  value: Any,
                  add_missing_options: bool = False,
                  inner_key: Optional[str] = None) -> bool:
        """Updates the value or one of its properties, returning whether the value changed."""
        # Handle inner key changes:
        if inner_key is not None:
            # changes to numeric ranges:
            if self._range_options is not None:
                if inner_key not in RangeKey.ALL:
                    raise ValueError(f'Invalid inner_key for {self._key}, expected {RangeKey.ALL}, '
                                     f'got {inner_key}')
                if not isinstance(self._value, type(value)):
                    raise TypeError(f'Cannot set {self._key}.{inner_key} to {type(value)} "{value}", type is '
                                    f'{type(self._value)}')
                value_changed = self._range_options[inner_key] != value
                self._range_options[inner_key] = value
                return value_changed

            # changes to dict properties:
            if isinstance(self._value, dict):
                prev_value = None if inner_key not in self._value else self._value[inner_key]
                value_changed = prev_value != value
                self._value[inner_key] = value
                return value_changed
            raise TypeError(f'Tried to set "{self._key}.{inner_key}" to value "{value}", but '
                            f'{self._key} is type "{type(self._value)}"')

        # Enforce type consistency for values other than inner dict values:
        if not isinstance(value, type(self._value)):
            raise TypeError(f'Expected "{self._key}" value "{value}" to have type "{type(self._value)}", found '
                            f'"{type(value)}"')

        # Handle changes to values with predefined options lists:
        if self._options is not None and value not in self._options:
            if add_missing_options:
                self.add_option(value)
            else:
                raise RuntimeError(f'"{self._key}" value "{value}" is not a valid option in '
                                   f'{json.dumps(self._options)}')
        value_changed = self._value != value
        self._value = value
        return value_changed

    def get_value(self, inner_key: Optional[str] = None) -> Any:
        """Gets the current value, or an inner value or range option if inner_key is not None."""
        if inner_key is not None:
            if self._range_options is not None:
                if inner_key not in RangeKey.ALL:
                    raise ValueError(f'Invalid inner_key for {self._key}, expected {RangeKey.ALL}, '
                                     f'got {inner_key}')
                return self._range_options[inner_key]
            if isinstance(self._value, dict):
                return None if inner_key not in self._value else self._value[inner_key]
            raise TypeError(f'Tried to read {self._key}.{inner_key} from type {type(self._value)}')
        if isinstance(self._value, QSize):
            return QSize(self._value)
        return self._value

    @property
    def category(self) -> str:
        """Gets the config option's category name."""
        return self._category

    @property
    def label(self) -> str:
        """Gets the config option's label text."""
        return self._label

    @property
    def tooltip(self) -> str:
        """Gets the config option's tooltip description."""
        return self._tooltip

    @property
    def option_index(self) -> int:
        """ Returns the index of the selected option."""
        if self._options is None:
            raise RuntimeError(f'Config value "{self._key}" does not have an associated options list')
        return self._options.index(self._value)

    @property
    def options(self) -> list:
        """Returns all valid options accepted."""
        if self._options is None:
            raise RuntimeError(f'Config value "{self._key}" does not have an associated options list')
        return self._options.copy()

    @options.setter
    def options(self, options_list: List[str]) -> None:
        """Replaces the list of accepted options."""
        if self._options is None:
            raise RuntimeError(f'Config value "{self._key}" does not have an associated options list')
        if not isinstance(options_list, list) or len(options_list) == 0:
            raise RuntimeError(f'Provided invalid options for config value "{self._key}"')
        self._options = options_list.copy()
        if self._value not in options_list:
            self.set_value(options_list[0], False)

    def add_option(self, option: str) -> None:
        """Adds a new item to the list of accepted options."""
        if self._options is None:
            raise RuntimeError(f'Config value "{self._key}" does not have an associated options list')
        if option not in self._options:
            self._options.append(option)

    def save_to_json_dict(self, json_dict: Dict[str, Any]) -> None:
        """Adds the value to a dict in a format that can be written to a JSON file."""
        if self.save_json is True:
            if isinstance(self._value, QSize):
                json_dict[self._key] = f'{self._value.width()}x{self._value.height()}'
            elif self._range_options is not None:
                json_dict[self._key] = dict(self._range_options)
                json_dict[self._key]['value'] = self._value
            else:
                json_dict[self._key] = self._value

    def load_from_json_dict(self, json_dict: Dict[str, Any]) -> None:
        """Reads the value from a dict that was loaded from a JSON file."""
        if self._key not in json_dict:
            return
        json_value = json_dict[self._key]
        if isinstance(self._value, QSize):
            self._value = QSize(*(int(n) for n in json_value.split('x')))
        elif self._range_options is not None and isinstance(json_value, dict):
            for range_key in RangeKey.ALL:
                if range_key in json_value:
                    self._range_options[range_key] = json_value[range_key]
            self._value = json_dict[self._key]['value']
        else:
            self._value = json_value
