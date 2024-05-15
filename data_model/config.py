"""
A shared resource to set inpainting configuration and to provide default values.

Main features
-------------
    - Save and load values from a JSON file.
    - Allow access to those values through config.get()
    - Allow typesafe changes to those values through config.set()
    - Subscribe to specific value changes through config.connect()
"""
import sys
import json
import os.path
import importlib.util
from threading import Lock
from inspect import signature
from PyQt5.QtWidgets import QStyleFactory
from PyQt5.QtCore import QObject, QSize, QTimer


class Config(QObject):
    """
    A shared resource to set inpainting configuration and to provide default values.

    Common Exceptions Raised
    ------------------------
    KeyError
        When any function with the `key` parameter is called with an unknown key.
    TypeError
        When a function with the optional `inner_key` parameter is used with a non-empty `inner_key` and a `key`
        that doesn't contain a dict value.
    RuntimeError
        If a function that interacts with lists of accepted value options is called on a value that doesn't have
        a fixed list of acceptable options.  keys in the file will be ignored.
    """

    DEFAULT_CONFIG_PATH = 'config.json'
    CONFIG_DEFINITIONS = 'resources/config_defs.json'

    class DefinitionKey():
        """Config definition key constants."""
        DEFAULT = 'default'
        TYPE = 'type'
        LABEL = 'label'
        CATEGORY = 'category'
        TOOLTIP = 'description'
        OPTIONS = 'options'
        RANGE = 'range_options'
        SAVED = 'saved'

    class DefinitionType():
        """Config definition type constants."""
        QSIZE = 'Size'
        INT = 'int'
        FLOAT = 'float'
        STR = 'string'
        BOOL = 'bool'
        LIST = 'list'
        DICT = 'dict'

    class RangeKey():
        """Config definition range key constants."""
        MIN = 'min'
        MAX = 'max'
        STEP = 'step'
        ALL = [MIN, MAX, STEP]


    # System-based theme/style init constants
    DEFAULT_THEME_OPTIONS = ['None']
    DARK_THEME_MODULE = 'qdarktheme'
    DARK_THEME_OPTIONS = ['qdarktheme_dark', 'qdarktheme_light', 'qdarktheme_auto']
    MATERIAL_THEME_MODULE = 'qt_material'


    def __init__(self, json_path=None):
        """
        Load existing config, or initialize from defaults.

        Parameters
        ----------
        json_path: str
            Path where config values will be saved and read. If the file does not exist, it will be created with
            default values. Any expected keys not found in the file will be added with default values. Any unexpected

        """
        if json_path is None:
            json_path = Config.DEFAULT_CONFIG_PATH
        self._entries = {}
        self._connected = {}
        self._json_path = json_path
        self._lock = Lock()
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)

        if not os.path.isfile(Config.CONFIG_DEFINITIONS):
            raise RuntimeError(f'Config definition file not found at {Config.CONFIG_DEFINITIONS}')
        try:
            with open(Config.CONFIG_DEFINITIONS, encoding='utf-8') as file:
                json_data = json.load(file)
                for key, definition in json_data.items():
                    try:
                        initial_value = definition[Config.DefinitionKey.DEFAULT]
                        match definition[Config.DefinitionKey.TYPE]:
                            case Config.DefinitionType.QSIZE:
                                initial_value = QSize(*(int(n) for n in initial_value.split('x')))
                            case Config.DefinitionType.INT:
                                initial_value = int(initial_value)
                            case Config.DefinitionType.FLOAT:
                                initial_value = float(initial_value)
                            case Config.DefinitionType.STR:
                                initial_value = str(initial_value)
                            case Config.DefinitionType.BOOL:
                                initial_value = bool(initial_value)
                            case Config.DefinitionType.LIST:
                                initial_value = list(initial_value)
                            case Config.DefinitionType.DICT:
                                initial_value = dict(initial_value)
                            case _:
                                raise RuntimeError(f'Config value definition for {key} had invalid data type ' + \
                                        f'{definition[Config.DefinitionKey.TYPE]}')
                    except KeyError as err:
                        raise RuntimeError(f'Loading {key} failed: {err}') from err

                    label = definition[Config.DefinitionKey.LABEL]
                    category = definition[Config.DefinitionKey.CATEGORY]
                    tooltip  = definition[Config.DefinitionKey.TOOLTIP]
                    options = None if Config.DefinitionKey.OPTIONS not in definition \
                              else list(definition[Config.DefinitionKey.OPTIONS])
                    range_options = None if Config.DefinitionKey.RANGE not in definition \
                                    else dict(definition[Config.DefinitionKey.RANGE])
                    save_json = definition[Config.DefinitionKey.SAVED]
                    self._add_entry(key, initial_value, label, category, tooltip, options, range_options, save_json)

        except json.JSONDecodeError as err:
            raise RuntimeError(f'Reading JSON config definitions failed: {err}') from err

        # Before reading existing config, dynamically initialize style and theme options:
        theme_options = Config.DEFAULT_THEME_OPTIONS
        def module_installed(name):
            if name in sys.modules:
                return True
            return bool((spec := importlib.util.find_spec(name)) is not None)
        if module_installed(Config.DARK_THEME_MODULE):
            theme_options += Config.DARK_THEME_OPTIONS
        if module_installed(Config.MATERIAL_THEME_MODULE):
            from qt_material import list_themes
            theme_options += [ f'{Config.MATERIAL_THEME_MODULE}_{theme}' for theme in list_themes() ]
        self.update_options(Config.THEME, theme_options)
        self.update_options(Config.STYLE, list(QStyleFactory.keys()))


        if os.path.isfile(self._json_path):
            self._read_from_json()
        else:
            self._write_to_json()


    def get(self, key, inner_key=None):
        """
        Returns a value from config.

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
        if not key in self._entries:
            raise KeyError(f'Tried to get unknown config value "{key}"')
        with self._lock:
            return self._entries[key].get_value(inner_key)


    def get_label(self, key):
        """Gets the label text assigned to a config value."""
        if not key in self._entries:
            raise KeyError(f'Tried to get label for unknown config value "{key}"')
        return self._entries[key].get_label()


    def get_tooltip(self, key):
        """Gets the tooltip text assigned to a config value."""
        if not key in self._entries:
            raise KeyError(f'Tried to get tooltip for unknown config value "{key}"')
        return self._entries[key].get_tooltip()


    def set(self, key, value, save_change=True, add_missing_options=False, inner_key=None):
        """
        Updates a saved value.

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
        if not key in self._entries:
            raise KeyError(f'Tried to set unknown config value "{key}"')
        value_changed = False
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
                    def write_change():
                        self._write_to_json()
                        self._save_timer.timeout.disconnect(write_change)
                    self._save_timer.timeout.connect(write_change)
                    self._save_timer.start(100)
        # Pass change to connected callback functions
        for callback in self._connected[key].values():
            num_args = len(signature(callback).parameters)
            if num_args == 1 and inner_key is None:
                callback(new_value)
            elif num_args == 2:
                callback(new_value, inner_key)
            if self.get(key, inner_key) != value:
                break


    def connect(self, connected_object, key, on_change_fn, inner_key = None):
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
        if not key in self._connected:
            raise KeyError(f'Tried to connect to unknown config value "{key}"')
        num_args = len(signature(on_change_fn).parameters)
        if num_args < 1 or num_args > 2:
            raise RuntimeError(f'callback function connected to {key} value takes {num_args} ' + \
                                'parameters, expected 1-2')
        if inner_key is None:
            self._connected[key][connected_object] = on_change_fn
        else:
            def wrapper_fn(value, changed_inner_key):
                if changed_inner_key == inner_key:
                    on_change_fn(value)
            self._connected[key][connected_object] = wrapper_fn


    def disconnect(self, connected_object, key):
        """
        Removes a callback function previously registered through config.connect() for a particular object and key.
        """
        if not key in self._connected:
            raise KeyError(f'Tried to disconnect from unknown config value "{key}"')
        self._connected[key].pop(connected_object, None)


    def list(self):
        """Returns all keys tracked by this Config object."""
        return self._entries.keys()


    def get_option_index(self, key):
        """
        Returns the index of the selected option for a given key.

        Raises
        ------
        RuntimeError
            If the value associated with the key does not have a predefined list of options
        """
        if not key in self._entries:
            raise KeyError(f'Tried to get unknown config value "{key}"')
        with self._lock:
            return self._entries[key].get_option_index()


    def get_options(self, key):
        """
        Returns all valid options accepted for a given key.

        Raises
        ------
        RuntimeError
            If the value associated with the key does not have a predefined list of options.
        """
        if not key in self._entries:
            raise KeyError(f'Tried to set unknown config value "{key}"')
        return self._entries[key].get_options()


    def update_options(self, key, options_list):
        """
        Replaces the list of accepted options for a given key.

        Raises
        ------
        RuntimeError
            If the value associated with the key does not have a predefined list of options.
        """
        if not key in self._entries:
            raise KeyError(f'Tried to get unknown config value "{key}"')
        self._entries[key].update_options(options_list)


    def add_option(self, key, option):
        """
        Adds a new item to the list of accepted options for a given key.

        Raises
        ------
        RuntimeError
            If the value associated with the key does not have a predefined list of options.
        """
        if not key in self._entries:
            raise KeyError(f'Tried to get unknown config value "{key}"')
        self._entries[key].add_option(option)


    def apply_args(self, args):
        """Loads expected parameters from command line arguments"""
        expected = {
            args.text: Config.PROMPT,
            args.negative: Config.NEGATIVE_PROMPT,
            args.num_batches: Config.BATCH_COUNT,
            args.batch_size: Config.BATCH_SIZE,
            args.cutn: Config.CUTN
        }
        for arg_value, key in expected.items():
            if arg_value:
                self.set(key, arg_value)
        if args.width and args.height:
            self.set(Config.EDIT_SIZE, QSize(args.width, args.height))


    def _add_entry(self, key, initial_value, label, category, tooltip, options=None, range_options=None,
            save_json=True):
        if key in self._entries:
            raise KeyError(f'Tried add duplicate config entry "{key}"')
        entry = _Entry(key, initial_value, label, category, tooltip, options, range_options, save_json)
        self._entries[key] = entry
        self._connected[key] = {}


    def _write_to_json(self):
        converted_dict = {}
        with self._lock:
            for entry in self._entries.values():
                entry.save_to_json_dict(converted_dict)
            with open(self._json_path, 'w', encoding='utf-8') as file:
                json.dump(converted_dict, file, ensure_ascii=False, indent=4)


    def _read_from_json(self):
        try:
            with open(self._json_path, encoding='utf-8') as file:
                json_data = json.load(file)
        except json.JSONDecodeError as err:
            print(f'Reading JSON config failed: {err}')
        with self._lock:
            for entry in self._entries.values():
                entry.load_from_json_dict(json_data)


class _Entry():
    def __init__(self, key, initial_value, label, category, tooltip, options=None, range_options=None, save_json=True):
        self._key = key
        self._value = initial_value
        self._label = label
        self._category = category
        self._tooltip = tooltip
        self.save_json = save_json
        if options is not None:
            if (not isinstance(options, list) or initial_value not in options):
                raise ValueError(f'Invalid options for key {key} with initial value {initial_value}: {options}')
            self._options = options
        else:
            self._options = None
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
        else:
            self._range_options = None


    def set_value(self, value, add_missing_options=False, inner_key=None):
        """Updates the value or one of its properties, returning value_changed and previous_value"""
        # Handle inner key changes:
        if inner_key is not None:
            # changes to numeric ranges:
            if self._range_options is not None:
                if inner_key not in Config.RangeKey.ALL:
                    raise ValueError(f'Invalid inner_key for {self._key}, expected {Config.RangeKey.ALL}, " + \
                            f"got {inner_key}')
                if type(self._value) != type(value):
                    raise TypeError(f'Cannot set {self._key}.{inner_key} to {type(value)} "{value}", type is ' + \
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
            raise TypeError(f'Tried to set "{self._key}.{inner_key}" to value "{value}", but ' + \
                            f'{self._key} is type "{type(self._value)}"')

        # Enforce type consistency for values other than inner dict values:
        if type(value) != type(self._value):
            raise TypeError(f'Expected "{self._key}" value "{value}" to have type "{type(self._value)}", found ' + \
                            f'"{type(value)}"')

        # Handle changes to values with predefined options lists:
        if self._options is not None and not value in self._options:
            if add_missing_options:
                self.add_option(value)
            else:
                raise RuntimeError(f'"{self._key}" value "{value}" is not a valid option in ' + \
                        f'{json.dumps(self._options)}')
        value_changed = self._value != value
        self._value = value
        return value_changed


    def get_value(self, inner_key=None):
        """Gets the current value, or an inner value or range option if inner_key is not None."""
        if inner_key is not None:
            if self._range_options is not None:
                if inner_key not in Config.RangeKey.ALL:
                    raise ValueError(f'Invalid inner_key for {self._key}, expected {Config.RangeKey.ALL}, ' + \
                            f'got {inner_key}')
                return self._range_options[inner_key]
            if isinstance(self._value, dict):
                return None if inner_key not in self._value else self._value[inner_key]
            raise TypeError(f'Tried to read {self._key}.{inner_key} from type {type(self._value)}')
        return self._value


    def get_category(self):
        """Gets the config option's category name."""
        return self._category


    def get_label(self):
        """Gets the config option's label text."""
        return self._label


    def get_tooltip(self):
        """Gets the config option's tooltip description."""
        return self._tooltip


    def get_option_index(self):
        """ Returns the index of the selected option."""
        if self._options is None:
            raise RuntimeError(f'Config value "{self._key}" does not have an associated options list')
        return self._options.index(self._value)


    def get_options(self):
        """Returns all valid options accepted."""
        if self._options is None:
            raise RuntimeError(f'Config value "{self._key}" does not have an associated options list')
        return self._options.copy()

    def add_option(self, option):
        """Adds a new item to the list of accepted options."""
        if self._options is None:
            raise RuntimeError(f'Config value "{self._key}" does not have an associated options list')
        if option not in self._options:
            self._options.append(option)


    def update_options(self, options_list):
        """Replaces the list of accepted options."""
        if self._options is None:
            raise RuntimeError(f'Config value "{self._key}" does not have an associated options list')
        if not isinstance(options_list, list) or len(options_list) == 0:
            raise RuntimeError(f'Provided invalid options for config value "{self._key}"')
        self._options = options_list.copy()
        if not self._value in options_list:
            self.set_value(options_list[0], False)


    def save_to_json_dict(self, json_dict):
        """Adds the value to a dict in a format that can be written to a JSON file."""
        if self.save_json is True:
            if isinstance(self._value, QSize):
                json_dict[self._key] = f'{self._value.width()}x{self._value.height()}'
            elif self._range_options is not None:
                json_dict[self._key] = dict(self._range_options)
                json_dict[self._key]['value'] = self._value
            else:
                json_dict[self._key] = self._value


    def load_from_json_dict(self, json_dict):
        """Reads the value from a dict that was loaded from a JSON file."""
        if self._key not in json_dict:
            return
        json_value = json_dict[self._key]
        if isinstance(self._value, QSize):
            self._value = QSize(*(int(n) for n in json_value.split('x')))
        elif self._range_options is not None and isinstance(json_value, dict):
            for range_key in Config.RangeKey.ALL:
                if range_key in json_value:
                    self._range_options[range_key] = json_value[range_key]
            self._value = json_dict[self._key]['value']
        else:
            self._value = json_value


# Add config keys as Config class constants:
with open(Config.CONFIG_DEFINITIONS, encoding='utf-8') as init_file:
    init_json_data = json.load(init_file)
    for init_key in init_json_data.keys():
        init_attr_name = init_key.upper()
        if hasattr(Config, init_attr_name):
            raise RuntimeError(f'Config key {init_key} conflicts with existing class attribute {init_attr_name}')
        setattr(Config, init_attr_name, init_key)
