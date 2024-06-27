"""
A shared resource to set inpainting configuration and to provide default values.

Main features
-------------
    - Save and load values from a JSON file.
    - Allow access to those values through config.get()
    - Allow typesafe changes to those values through config.set()
    - Subscribe to specific value changes through config.connect()
"""
import json
import os.path
from inspect import signature
from threading import Lock
from typing import Optional, Any, Callable, List, Dict, cast
import logging

from PyQt5.QtCore import QSize, QTimer, Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QWidget, QComboBox

from src.config.config_entry import ConfigEntry, DefinitionKey, DefinitionType
from src.util.parameter import TYPE_QSIZE
from src.util.validation import assert_type

logger = logging.getLogger(__name__)


class Config:
    """A shared resource to set inpainting configuration and to provide default values.

    Common Exceptions Raised
    ------------------------
    KeyError
        When any function with the `key` parameter is called with an unknown key.
    TypeError
        When a function with the optional `inner_key` parameter is used with a non-empty `inner_key` and a `key`
        that doesn't contain a dict value.
    RuntimeError
        If a function that interacts with lists of accepted value options is called on a value that doesn't have
        a fixed list of acceptable options.
    """

    def __init__(self, definition_path: str, saved_value_path: Optional[str], child_class: type) -> None:
        """Load existing config, or initialize from defaults.

        Parameters
        ----------
        definition_path: str
            Path to a file defining accepted config values.
        saved_value_path: str, optional
            Path where config values will be saved and read. If the file does not exist, it will be created with
            default values. Any expected keys not found in the file will be added with default values. Any unexpected
            values will be removed. If not provided, the Config object won't allow file IO.
        child_class: class
            Child class where definition keys should be written as properties when first initialized.
        """
        self._entries: dict[str, ConfigEntry] = {}
        self._connected: dict[str, dict[Any, Callable[..., None]]] = {}
        self._json_path = saved_value_path
        self._lock = Lock()
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)

        if not os.path.isfile(definition_path):
            raise RuntimeError(f'Config definition file not found at {definition_path}')
        try:
            with open(definition_path, encoding='utf-8') as file:
                json_data = json.load(file)
                for key, definition in json_data.items():
                    assert_type(definition, dict)
                    init_attr_name = key.upper()
                    if not hasattr(child_class, init_attr_name):
                        setattr(child_class, init_attr_name, key)
                    try:
                        if DefinitionKey.DEFAULT in definition:
                            initial_value = definition[DefinitionKey.DEFAULT]
                            match definition[DefinitionKey.TYPE]:
                                case DefinitionType.QSIZE:
                                    initial_value = QSize(*(int(n) for n in initial_value.split('x')))
                                case DefinitionType.INT:
                                    initial_value = int(initial_value)
                                case DefinitionType.FLOAT:
                                    initial_value = float(initial_value)
                                case DefinitionType.STR:
                                    initial_value = str(initial_value)
                                case DefinitionType.BOOL:
                                    initial_value = bool(initial_value)
                                case DefinitionType.LIST:
                                    initial_value = list(initial_value)
                                case DefinitionType.DICT:
                                    initial_value = dict(initial_value)
                                case _:
                                    raise RuntimeError(f'Config value definition for {key} had invalid data type '
                                                       f'{definition[DefinitionKey.TYPE]}')
                        else:  # If no default is provided, use the closest equivalent to an empty value:
                            match definition[DefinitionKey.TYPE]:
                                case DefinitionType.QSIZE:
                                    initial_value = QSize()
                                case DefinitionType.INT:
                                    initial_value = 0
                                case DefinitionType.FLOAT:
                                    initial_value = 0.0
                                case DefinitionType.STR:
                                    initial_value = ''
                                case DefinitionType.BOOL:
                                    initial_value = False
                                case DefinitionType.LIST:
                                    initial_value = []
                                case DefinitionType.DICT:
                                    initial_value = {}
                                case _:
                                    raise RuntimeError(f'Config value definition for {key} had invalid data type '
                                                       f'{definition[DefinitionKey.TYPE]}')
                    except KeyError as err:
                        raise RuntimeError(f'Loading {key} failed: {err}') from err

                    label = definition[DefinitionKey.LABEL]
                    category = definition[DefinitionKey.CATEGORY]
                    tooltip = definition[DefinitionKey.TOOLTIP]
                    options = None if DefinitionKey.OPTIONS not in definition \
                        else list(definition[DefinitionKey.OPTIONS])
                    range_options = None if DefinitionKey.RANGE not in definition \
                        else dict(definition[DefinitionKey.RANGE])
                    if DefinitionKey.SAVED in definition:
                        save_json = definition[DefinitionKey.SAVED]
                    else:
                        save_json = False
                    self._add_entry(key, initial_value, label, category, tooltip, options, range_options, save_json)

        except json.JSONDecodeError as err:
            raise RuntimeError(f'Reading JSON config definitions failed: {err}') from err

        self._adjust_defaults()
        if self._json_path is not None:
            if os.path.isfile(self._json_path):
                self._read_from_json()
            else:
                self._write_to_json()

    def _adjust_defaults(self) -> None:
        """Override this to perform any adjustments to default values needed before file IO, e.g. loading list options
           from an external source."""

    def get(self, key: str, inner_key: Optional[str] = None) -> Any:
        """Returns a value from config.

        Parameters
        ----------
        key : str
            A key tracked by this config file.
        inner_key : str, optional
            If not None, assume the value at `key` is a dict and attempt to return the value within it at `inner_key`.
            If the value is a dict but does not contain `inner_key`, instead return None

        Returns
        -------
        int or float or str or bool or list or dict or QSize or None
            Type varies based on key. Each key is guaranteed to always return the same type, but inner_key values
            are not type-checked.
        """
        if key not in self._entries:
            raise KeyError(f'Tried to get unknown config value "{key}"')
        with self._lock:
            return self._entries[key].get_value(inner_key)

    def get_control_widget(self, key: str, connect_to_config: bool = True, multi_line=False) -> QWidget:
        """Returns a QWidget capable of adjusting the chosen config value. Unless connect_to_config is false, changes
        will immediately propagate to the underlying config file."""
        with self._lock:
            entry = self._entries[key]
            control_widget = entry.get_input_widget(multi_line)
            control_widget.setValue(entry.get_value())
            if connect_to_config:
                def _update_config(new_value: Any, config_key=key) -> None:
                    self.set(config_key, new_value)

                def _update_control(new_value: Any) -> None:
                    control_widget.setValue(new_value)

                assert hasattr(control_widget, 'valueChanged')
                control_widget.valueChanged.connect(_update_config)
                self.connect(control_widget, key, _update_control)
            return  control_widget

    def get_keycodes(self, key: str) -> QKeySequence:
        """Returns a config value as a key sequence, throws RuntimeError if the value isn't a keycode."""
        code_string = self.get(key)
        if not isinstance(code_string, str):
            raise RuntimeError(f'Tried to get key code "{key}", found {code_string}')
        sequence = QKeySequence(code_string)
        if Qt.Key_unknown in sequence:
            raise RuntimeError(f'key "{key}": value "{code_string}" is not a valid key code or code list')
        return sequence

    def get_label(self, key: str) -> str:
        """Gets the label text assigned to a config value."""
        if key not in self._entries:
            raise KeyError(f'Tried to get label for unknown config value "{key}"')
        return self._entries[key].name

    def get_tooltip(self, key: str) -> str:
        """Gets the tooltip text assigned to a config value."""
        if key not in self._entries:
            raise KeyError(f'Tried to get tooltip for unknown config value "{key}"')
        return self._entries[key].description

    def set(self,
            key: str,
            value: Any,
            save_change: bool = True,
            add_missing_options: bool = False,
            inner_key: Optional[str] = None) -> None:
        """Updates a saved value.

        Parameters
        ----------
        key : str
            A key tracked by this config file.
        value : int or float or str or bool or list or dict or QSize or None
            The new value to assign to the key. Unless inner_key is not None, this must have the same type as the
            previous value.
        save_change: bool, default=True
            If true, save the change to the underlying JSON file. Otherwise, the change will be saved the next time
            any value is set with save_change=True
        add_missing_options: bool, default=False
            If the key is associated with a list of valid options and this is true, value will be added to the list
            of options if not already present. Otherwise, RuntimeError is raised if value is not within the list
        inner_key: str, optional
            If not None, assume the value at `key` is a dict and attempt to set the value within it at `inner_key`. If
            the value is a dict but does not contain `inner_key`, instead return None
       
        Raises
        ------
        TypeError
            If `value` does not have the same type as the current value saved under `key`
        RuntimeError
            If `key` has a list of associated valid options, `value` is not one of those options, and
            `add_missing_options` is false.
        """
        if key not in self._entries:
            raise KeyError(f'Tried to set unknown config value "{key}"')
        new_value = value
        # Update existing value:
        with self._lock:
            value_changed = self._entries[key].set_value(value, add_missing_options, inner_key)
        if not value_changed:
            return
        # Schedule save to JSON file:
        if save_change:
            with self._lock:
                if not self._save_timer.isActive():
                    def write_change() -> None:
                        """Copy changes to the file and disconnect the timer."""
                        self._write_to_json()
                        self._save_timer.timeout.disconnect(write_change)

                    self._save_timer.timeout.connect(write_change)
                    self._save_timer.start(100)
        # Pass change to connected callback functions
        for callback in self._connected[key].values():
            num_args = len(signature(callback).parameters)
            if num_args == 0 and inner_key is None:
                callback()
            elif num_args == 1 and inner_key is None:
                callback(new_value)
            elif num_args == 2:
                callback(new_value, inner_key)
            if self.get(key, inner_key) != value:
                break

    def connect(self,
                connected_object: Any,
                key: str,
                on_change_fn: Callable[..., None],
                inner_key: Optional[str] = None) -> None:
        """
        Registers a callback function that should run when a particular key is changed.

        Parameters
        ----------
        connected_object: object
            An object to associate with this connection. Only one connection can be made for a connected_object.
        key: str
            A key tracked by this config file.
        on_change_fn: function(new_value) or function(new_value, previous_value)
            The function to run when the value changes.
        inner_key: str, optional
            If not None, assume the value at `key` is a dict and ensure on_change_fn only runs when `inner_key`
            changes within the value.
        """
        if key not in self._connected:
            raise KeyError(f'Tried to connect to unknown config value "{key}"')
        num_args = len(signature(on_change_fn).parameters)
        if num_args > 2:
            raise RuntimeError(f'callback function connected to {key} value takes {num_args} '
                               'parameters, expected 0-2')
        if inner_key is None:
            self._connected[key][connected_object] = on_change_fn
        else:
            def wrapper_fn(value: Any, changed_inner_key: str) -> None:
                """Call connected function only if the inner key changes."""
                if changed_inner_key == inner_key:
                    on_change_fn(value)

            self._connected[key][connected_object] = wrapper_fn

    def disconnect(self, connected_object: Any, key: str) -> None:
        """
        Removes a callback function previously registered through config.connect() for a particular object and key.
        """
        if key not in self._connected:
            raise KeyError(f'Tried to disconnect from unknown config value "{key}"')
        self._connected[key].pop(connected_object, None)

    def list(self) -> List[str]:
        """Returns all keys tracked by this Config object."""
        return list(self._entries.keys())

    def get_option_index(self, key: str) -> int:
        """Returns the index of the selected option for a given key.

        Raises
        ------
        RuntimeError
            If the value associated with the key does not have a predefined list of options
        """
        if key not in self._entries:
            raise KeyError(f'Tried to get unknown config value "{key}"')
        with self._lock:
            return self._entries[key].option_index

    def get_options(self, key: str) -> List[str]:
        """Returns all valid options accepted for a given key.

        Raises
        ------
        RuntimeError
            If the value associated with the key does not have a predefined list of options.
        """
        if key not in self._entries:
            raise KeyError(f'Tried to set unknown config value "{key}"')
        return self._entries[key].options

    def update_options(self, key: str, options_list: List[str]) -> None:
        """
        Replaces the list of accepted options for a given key.

        Raises
        ------
        RuntimeError
            If the value associated with the key does not have a predefined list of options.
        """
        if key not in self._entries:
            raise KeyError(f'Tried to get unknown config value "{key}"')
        last_value = self.get(key)
        self._entries[key].set_valid_options(options_list)
        if last_value not in options_list:
            self.set(key, options_list[0])

    def add_option(self, key: str, option: str) -> None:
        """
        Adds a new item to the list of accepted options for a given key.

        Raises
        ------
        RuntimeError
            If the value associated with the key does not have a predefined list of options.
        """
        if key not in self._entries:
            raise KeyError(f'Tried to get unknown config value "{key}"')
        self._entries[key].add_option(option)

    def get_categories(self) -> List[str]:
        """Returns all unique category strings."""
        categories = []
        for value in self._entries.values():
            if value.category not in categories:
                categories.append(value.category)
        return categories

    def get_category_keys(self, category: str) -> List[str]:
        """Returns all keys with the given category."""
        keys = []
        for key, value in self._entries.items():
            if value.category == category:
                keys.append(key)
        return keys

    def get_keys(self) -> List[str]:
        """Returns all keys defined for a config class."""
        return list(self._entries.keys())

    def _add_entry(self,
                   key: str,
                   initial_value: Any,
                   label: str,
                   category: str,
                   tooltip: str,
                   options: Optional[List[str]] = None,
                   range_options: Optional[Dict[str, int | float]] = None,
                   save_json: bool = True) -> None:
        if key in self._entries:
            raise KeyError(f'Tried add duplicate config entry "{key}"')
        entry = ConfigEntry(key, initial_value, label, category, tooltip, options, range_options, save_json)
        self._entries[key] = entry
        self._connected[key] = {}

    def _write_to_json(self) -> None:
        if self._json_path is None:
            return
        converted_dict: Dict[str, Any] = {}
        with self._lock:
            for entry in self._entries.values():
                entry.save_to_json_dict(converted_dict)
            with open(self._json_path, 'w', encoding='utf-8') as file:
                json.dump(converted_dict, file, ensure_ascii=False, indent=4)

    def _read_from_json(self) -> None:
        if self._json_path is None:
            return
        json_data = None
        try:
            with open(self._json_path, encoding='utf-8') as file:
                json_data = json.load(file)
        except json.JSONDecodeError as err:
            logger.error(f'Reading JSON config failed: {err}')
        if json_data is None:   # Invalid JSON, replace it with defaults
            self._write_to_json()
            return
        with self._lock:
            for entry in self._entries.values():
                entry.load_from_json_dict(json_data)
