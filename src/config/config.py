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
import logging
import os
import tempfile
import weakref
from inspect import signature
from threading import Lock
from typing import Optional, Any, Callable

from PySide6.QtCore import QObject, QSize, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QKeySequence, QColor
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from src.config.config_entry import ConfigEntry, DefinitionKey, DefinitionType
from src.config.definition_tr_contexts import DEFINITION_TR_CONTEXTS
from src.util.main_thread import assert_main_thread
from src.util.parameter import ParamType, ParamTypeList, get_parameter_type

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'config.config'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


MISSING_DEF_ERROR = _tr('Config definition file not found at {definition_path}')
INVALID_CONFIG_TYPE_ERROR = _tr('Config value definition for {key} had invalid data type {value_type}')
INVALID_KEY_ERROR = _tr('Loading {key} failed: {err}')
INVALID_JSON_DEFINITION_ERROR = _tr('Reading JSON config definitions failed: {err}')
INVALID_JSON_ERROR = _tr('Reading JSON config values failed: {err}')
UNKNOWN_KEY_ERROR = _tr('Tried to access unknown config value "{key}"')
INVALID_OPTION_KEY_ERROR = _tr('Tried to track fixed options for key "{key}", which does not have a fixed list of'
                               ' options.')
INVALID_KEYCODE_ERROR = _tr('Tried to get key code "{key}", found "{code_string}"')
DUPLICATE_KEY_ERROR = _tr('Tried to add duplicate config entry for key "{key}"')
NEWER_VERSION_WARNING = _tr('{path} was written by a newer version of IntraPaint (config version {version}). Its'
                            ' values will load, but changes won\'t be saved.')

# Top-level key holding the integer version of a saved config file. It isn't a config entry.
CONFIG_VERSION_KEY = 'config_version'

SAVE_DELAY_MS = 10


def _definition_tr_context(definition_path: str) -> str:
    """Returns the translation context of a definition file's strings (`DEFINITION_TR_CONTEXTS`)."""
    return DEFINITION_TR_CONTEXTS.get(os.path.basename(definition_path), '')


class _KeyNotifier(QObject):
    """Emits one config key's change signals. Lives on the thread that constructed the `Config`."""
    # (new value, inner key or None)
    value_changed = Signal(object, object)
    options_changed = Signal(list)


class _ConfigConnection(QObject):
    """One registered callback, connected to a `_KeyNotifier` signal.

    `Config.connect` and `Config.connect_to_option_changes` own these through their registries. A connection is
    deliberately unparented, so it creates no parent/child reference cycle with a widget owner. When the owner is a
    `QObject`, its `destroyed` signal removes the connection.
    """

    def __init__(self, config: 'Config', key: str, owner: Any, callback: Callable[..., None],
                 options: bool) -> None:
        super().__init__()
        self._config = weakref.ref(config)  # A strong reference would cycle with the config's registry.
        self.key = key
        self.owner = owner
        self.options = options
        self._callback = callback
        # Connected to the owner's `destroyed` signal. A slot on this object would make PySide hold the connection
        # from the owner, which cycles with `owner`; this closure holds the connection weakly instead.
        self.destroyed_handler: Optional[Callable[..., None]] = None
        if isinstance(owner, QObject):
            self_ref = weakref.ref(self)

            def _owner_destroyed(*_args: Any) -> None:
                connection = self_ref()
                if connection is not None:
                    connection.on_owner_destroyed()
            self.destroyed_handler = _owner_destroyed

    @Slot(object, object)
    def on_value_changed(self, value: Any, inner_key: Optional[str]) -> None:
        """Runs the callback unless a callback that ran earlier for this change has since changed the value again."""
        config = self._config()
        if config is None or config.get(self.key, inner_key) != value:
            return
        self._callback(value, inner_key)

    @Slot(list)
    def on_options_changed(self, options: ParamTypeList) -> None:
        """Passes a copy of the new option list to the callback."""
        self._callback([*options])

    def on_owner_destroyed(self) -> None:
        """Removes the connection when its owner `QObject` is destroyed."""
        config = self._config()
        if config is not None:
            config._remove_connection(self)  # pylint: disable=protected-access


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

    Saved files hold only entries that differ from their definition's default, plus a `config_version`. Child
    classes can set these class attributes:

    PREVIOUS_DEFAULTS: dict[str, list[Any]]
        Maps a key to defaults it had in earlier releases, in their saved JSON form. An unversioned file holding one of
        them for a non-pinned key sheds it on migration, so the key follows the current default. When a default
        changes, add the old value here if any release or the integration branch may have written it.
    RESET_KEYS: tuple[str, ...]
        Keys dropped from unversioned files whatever they hold.
    """
    PREVIOUS_DEFAULTS: dict[str, list[Any]] = {}
    RESET_KEYS: tuple[str, ...] = ()

    def __init__(self, definition_path: str, saved_value_path: Optional[str]) -> None:
        """Load existing config, or initialize from defaults.

        Parameters
        ----------
        definition_path: str
            Path to a file defining accepted config values.
        saved_value_path: str, optional
            Path where config values will be saved and read. If the file does not exist, it will be created with
            default values. Only values that differ from their definition's default are saved (plus entries
            defined with `"pinned": true`), and any expected key not found in the file loads with its current default.
            Any unexpected values will be removed. If not provided, the Config object won't allow file IO.
        """
        self._entries: dict[str, ConfigEntry] = {}
        self._newer_file = False
        self._notifiers: dict[str, _KeyNotifier] = {}
        self._connected: dict[str, dict[Any, _ConfigConnection]] = {}
        self._option_connected: dict[str, dict[Any, _ConfigConnection]] = {}
        self._json_path = saved_value_path
        self._tr_context = ''
        self._lock = Lock()
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(SAVE_DELAY_MS)
        self._save_timer.timeout.connect(self._write_to_json)

        if not os.path.isfile(definition_path):
            raise RuntimeError(MISSING_DEF_ERROR.format(definition_path=definition_path))
        try:
            with open(definition_path, encoding='utf-8') as file:
                self._tr_context = _definition_tr_context(definition_path)
                config_text_key = self._tr_context

                def _tr_cfg(text: str) -> str:
                    return QApplication.translate(config_text_key, text)

                json_data = json.load(file)
                for key, definition in json_data.items():
                    assert isinstance(definition, dict)
                    try:
                        if DefinitionKey.DEFAULT in definition:
                            initial_value = definition[DefinitionKey.DEFAULT]
                            match definition[DefinitionKey.TYPE]:
                                case DefinitionType.QSIZE:
                                    width, height = (int(n) for n in initial_value.split('x'))
                                    initial_value = QSize(width, height)
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
                                    raise RuntimeError(INVALID_CONFIG_TYPE_ERROR.format(key=key,
                                                                                        value_type=definition[
                                                                                            DefinitionKey.TYPE]))
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
                                    raise RuntimeError(INVALID_CONFIG_TYPE_ERROR.format(key=key,
                                                                                        value_type=definition[
                                                                                            DefinitionKey.TYPE]))
                    except KeyError as err:
                        raise RuntimeError(INVALID_KEY_ERROR.format(key=key, err=err)) from err

                    label = _tr_cfg(definition[DefinitionKey.LABEL])
                    category = _tr_cfg(definition[DefinitionKey.CATEGORY])
                    subcategory = None if DefinitionKey.SUBCATEGORY not in definition \
                        else _tr_cfg(definition[DefinitionKey.SUBCATEGORY])
                    tooltip = _tr_cfg(definition[DefinitionKey.TOOLTIP])
                    options = None if DefinitionKey.OPTIONS not in definition \
                        else list(definition[DefinitionKey.OPTIONS])
                    range_options = None if DefinitionKey.RANGE not in definition \
                        else dict(definition[DefinitionKey.RANGE])
                    if DefinitionKey.SAVED in definition:
                        save_json = definition[DefinitionKey.SAVED]
                    else:
                        save_json = False
                    pinned = bool(definition.get(DefinitionKey.PINNED, False))
                    control_hint = definition.get(DefinitionKey.CONTROL)
                    self._add_entry(key, initial_value, label, category, subcategory, tooltip, options, range_options,
                                    save_json, pinned, control_hint)

        except json.JSONDecodeError as err:
            raise RuntimeError(INVALID_JSON_DEFINITION_ERROR.format(err=err)) from err

        self._adjust_defaults()
        if self._json_path is not None:
            if os.path.isfile(self._json_path):
                self._read_from_json()
            else:
                self._write_to_json()
        # The state `_reset` restores:
        self._initial_state = {key: entry.snapshot_state() for key, entry in self._entries.items()}

    def _reset(self) -> None:
        """Restores every entry to its state at the end of construction, and discards all connections. For testing use
        only.

        Pending saves are cancelled, so a change made before the reset never reaches the JSON file.
        """
        self._save_timer.stop()
        with self._lock:
            for key, entry in self._entries.items():
                entry.restore_state(self._initial_state[key])
            for registry in (self._connected, self._option_connected):
                for connections in registry.values():
                    for connection in [*connections.values()]:
                        self._remove_connection(connection)

    def _adjust_defaults(self) -> None:
        """Override this to perform any adjustments to default values needed before file IO, e.g. loading list options
           from an external source."""

    def _migrate_legacy_keys(self, json_data: dict[str, Any]) -> None:
        """Override this to rewrite values saved under keys that no longer exist, in place. Runs as part of the
           migration from unversioned files (version 0 to 1)."""

    def _migrate_unversioned(self, json_data: dict[str, Any]) -> None:
        """Migration from version 0 to 1: converts legacy keys, then drops saved values that only held a default.

        A non-pinned value is dropped when it equals the current default or one in `PREVIOUS_DEFAULTS`. Keys in
        `RESET_KEYS` are dropped whatever they hold.
        """
        self._migrate_legacy_keys(json_data)
        for key in self.RESET_KEYS:
            json_data.pop(key, None)
        for key, entry in self._entries.items():
            if key not in json_data or entry.pinned:
                continue
            saved_value = entry.saved_json_value(json_data[key])
            if saved_value == entry.default_json_value() or saved_value in self.PREVIOUS_DEFAULTS.get(key, []):
                del json_data[key]

    def _migrations(self) -> list[Callable[[dict[str, Any]], None]]:
        """Returns the ordered migrations over the raw saved dict. Entry N migrates version N to version N + 1, and
           `CONFIG_VERSION` is the length of the list."""
        return [self._migrate_unversioned]

    @property
    def json_path(self) -> Optional[str]:
        """Returns the path where this config object saves changes. If None, the config object does not save data to
         disk."""
        return self._json_path

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
            raise KeyError(UNKNOWN_KEY_ERROR.format(key=key))
        with self._lock:
            return self._entries[key].get_value(inner_key)

    def get_default(self, key: str) -> Any:
        """Returns the default value the definition file gives a key, or None if it has none.

        Raises
        ------
        KeyError
            If the key isn't tracked by this config file.
        """
        if key not in self._entries:
            raise KeyError(UNKNOWN_KEY_ERROR.format(key=key))
        return self._entries[key].default_value

    def get_data_type(self, key: str) -> str:
        """Gets the data type associated with a config key, raising KeyError if the key isn't found."""
        if key not in self._entries:
            raise KeyError(UNKNOWN_KEY_ERROR.format(key=key))
        return self._entries[key].type_name

    def get_category(self, key: str) -> str:
        """Returns a config value's category, raising KeyError if the value does not exist."""
        if key not in self._entries:
            raise KeyError(UNKNOWN_KEY_ERROR.format(key=key))
        return self._entries[key].category

    def get_subcategory(self, key: str) -> Optional[str]:
        """Returns a config value's subcategory, raising KeyError if the value does not exist."""
        if key not in self._entries:
            raise KeyError(UNKNOWN_KEY_ERROR.format(key=key))
        return self._entries[key].subcategory

    def get_control_hint(self, key: str) -> Optional[str]:
        """Returns the `ControlHint` a key's definition names, or None. Raises KeyError for an unknown key."""
        if key not in self._entries:
            raise KeyError(UNKNOWN_KEY_ERROR.format(key=key))
        return self._entries[key].control_hint

    def get_color(self, key: str, default_color: QColor | Qt.GlobalColor) -> QColor:
        """Returns a color value from config.

        Parameters
        ----------
        key : str
            A key tracked by this config file.
        default_color : QColor | Qt.GlobalColor
            Color value to return if the key doesn't map to a valid color string.

        Returns
        -------
        The configured color, or the default if the color isn't valid."""
        color_str = self.get(key)
        if not QColor(color_str).isValid():
            if isinstance(default_color, Qt.GlobalColor):
                default_color = QColor(default_color)
            return default_color
        return QColor(color_str)

    def set_color(self, key: str, color: QColor | Qt.GlobalColor, save_change: bool = True) -> None:
        """Saves a color value to config as a lowercase `#aarrggbb` string, the one form color keys use.

        Mixing cases for the same color makes `set` see a change and notify every listener again, so all color writes
        go through this method.
        """
        self.set(key, QColor(color).name(QColor.NameFormat.HexArgb), save_change)

    def get_entry(self, key: str) -> ConfigEntry:
        """Returns the entry holding a key's value and metadata. Widget factories read it; don't mutate it directly."""
        with self._lock:
            return self._entries[key]

    def get_keycodes(self, key: str) -> QKeySequence:
        """Returns a config value as a key sequence, throws RuntimeError if the value isn't a keycode."""
        code_string = self.get(key)
        if not isinstance(code_string, str):
            raise RuntimeError(INVALID_KEYCODE_ERROR.format(key=key, code_string=code_string))
        sequence = QKeySequence(code_string)
        if Qt.Key.Key_unknown in sequence:
            raise RuntimeError(INVALID_KEYCODE_ERROR.format(key=key, code_string=code_string))
        return sequence

    def get_label(self, key: str) -> str:
        """Gets the label text assigned to a config value."""
        if key not in self._entries:
            raise KeyError(UNKNOWN_KEY_ERROR.format(key=key))
        return self._entries[key].name

    def get_range(self, key: str) -> tuple[Optional[int | float], Optional[int | float], Optional[int | float]]:
        """Returns the minimum, maximum and step defined for a numeric key, with None for any that isn't defined."""
        entry = self._entries[key]
        return entry.minimum, entry.maximum, entry.single_step

    def get_tooltip(self, key: str) -> str:
        """Gets the tooltip text assigned to a config value."""
        if key not in self._entries:
            raise KeyError(UNKNOWN_KEY_ERROR.format(key=key))
        return self._entries[key].description

    def get_option_display(self, option: Any) -> str:
        """Returns the text to show for one of this config's options.

        The stored value is always the untranslated option. This text is for display only, and widgets should keep the
        option itself as item data. Options with no translation, including ones loaded from a backend, display as
        written.
        """
        if not isinstance(option, str):
            return str(option)
        return QApplication.translate(self._tr_context, option)

    def set(self,
            key: str,
            value: Any,
            save_change: bool = True,
            add_missing_options: bool = False,
            inner_key: Optional[str] = None) -> None:
        """Updates a saved value. Must be called on the main thread.

        Callbacks and the save timer run on the calling thread, and callbacks update widgets. Worker code stages the
        value and applies it in a finish handler or through `run_on_main_thread`.

        Connected callbacks stop running for this change once one of them changes the value again. An exception
        raised by a callback goes to `sys.excepthook`, not to the caller, and the remaining callbacks still run.

        Parameters
        ----------
        key : str
            A key tracked by this config file.
        value : int or float or str or bool or list or dict or QSize or None
            The new value to assign to the key. Unless inner_key is not None, this must have the same type as the
            previous value. An int key whose range exceeds a C int also accepts decimal text, which it stores as an
            int (`Parameter.accepts_int_text`).
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
        RuntimeError
            If called from any thread other than the main thread.
        """
        assert_main_thread('Config.set')
        if key not in self._entries:
            raise KeyError(UNKNOWN_KEY_ERROR.format(key=key))
        # Update existing value:
        with self._lock:
            value_changed = self._entries[key].set_value(value, add_missing_options, inner_key)
            # The entry can store a converted value, such as a seed spinbox's text as an int:
            new_value = self._entries[key].get_value(inner_key)
        if not value_changed:
            return
        # Schedule save to JSON file:
        if save_change:
            with self._lock:
                if not self._save_timer.isActive():
                    self._save_timer.start()
        # Delivered synchronously: set() runs on the main thread, where the connections live.
        self._notifiers[key].value_changed.emit(new_value, inner_key)

    def save_pending_changes(self) -> None:
        """Writes changes `set` scheduled to the JSON file immediately.

        Scheduled writes need the event loop, so a value set just before the application exits is lost unless this is
        called first.
        """
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._write_to_json()

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
            An object to associate with this connection. Only one connection can be made between a given key and
            connected_object: a second connect with the same object and key replaces the first.
        key: str
            A key tracked by this config file.
        on_change_fn: function(new_value), function(new_value, inner_key)
            The function to run when the value changes. It must be a Python function or method: `inspect.signature`
            reads its argument count, and before Python 3.13 it raises ValueError for Qt's built-in methods, such as
            `QAbstractButton.setChecked`.
        inner_key: str, optional
            If not None, assume the value at `key` is a dict and ensure on_change_fn only runs when `inner_key`
            changes within the value.
        """
        if key not in self._connected:
            raise KeyError(UNKNOWN_KEY_ERROR.format(key=key))
        num_args = len(signature(on_change_fn).parameters)
        if num_args > 2:
            raise RuntimeError(f'callback function connected to {key} value takes {num_args} '
                               'parameters, expected 0-2')

        def deliver(value: Any, changed_inner_key: Optional[str]) -> None:
            """Adapts the callback's argument count to the signal's (value, inner_key)."""
            if inner_key is not None:
                if changed_inner_key == inner_key:
                    on_change_fn(value)
            elif num_args == 2:
                on_change_fn(value, changed_inner_key)
            elif changed_inner_key is None:
                if num_args == 1:
                    on_change_fn(value)
                else:
                    on_change_fn()

        self._add_connection(connected_object, key, deliver, False)

    def connect_to_option_changes(self,
                                  connected_object: Any,
                                  key: str,
                                  on_change_fn: Callable[[ParamTypeList], None]) -> None:
        """
        Registers a callback function that should run when fixed options change for a particular key.

        Parameters
        ----------
        connected_object: object
            An object to associate with this connection. Only one options connection can be made between a given key and
            connected_object.
        key: str
            A key tracked by this config file.
        on_change_fn: function(new_options), function(new_value, inner_key)
            The function to run when the option list changes.
        """
        if key not in self._option_connected:
            raise KeyError(INVALID_OPTION_KEY_ERROR.format(key=key))
        self._add_connection(connected_object, key, on_change_fn, True)

    def disconnect(self, connected_object: Any, key: str) -> None:
        """
        Removes a callback function previously registered through config.connect() or config.connect_to_option_changes
        for a particular object and key.
        """
        if key not in self._connected:
            raise KeyError(UNKNOWN_KEY_ERROR.format(key=key))
        for registry in (self._connected, self._option_connected):
            connection = registry.get(key, {}).get(connected_object)
            if connection is not None:
                self._remove_connection(connection)

    def disconnect_all(self, connected_object: Any) -> None:
        """Removes all connections associated with a particular object."""
        for registry in (self._connected, self._option_connected):
            for connections in registry.values():
                connection = connections.get(connected_object)
                if connection is not None:
                    self._remove_connection(connection)

    def _add_connection(self,
                        owner: Any,
                        key: str,
                        callback: Callable[..., None],
                        options: bool) -> None:
        """Connects `callback` to a key's value or option signal, replacing the owner's earlier connection."""
        registry = self._option_connected if options else self._connected
        previous = registry[key].get(owner)
        if previous is not None:
            self._remove_connection(previous)
        connection = _ConfigConnection(self, key, owner, callback, options)
        notifier = self._notifiers[key]
        if options:
            notifier.options_changed.connect(connection.on_options_changed)
        else:
            notifier.value_changed.connect(connection.on_value_changed)
        if connection.destroyed_handler is not None:
            owner.destroyed.connect(connection.destroyed_handler)
        registry[key][owner] = connection

    def _remove_connection(self, connection: _ConfigConnection) -> None:
        """Disconnects a connection and drops it from its registry. Safe to call more than once."""
        registry = self._option_connected if connection.options else self._connected
        connections = registry.get(connection.key, {})
        if connections.get(connection.owner) is connection:
            del connections[connection.owner]
        # At application shutdown Qt can delete the notifier, the connection or the owner before this runs. Their
        # signals are gone with them, so there is nothing left to disconnect.
        notifier = self._notifiers.get(connection.key)
        if notifier is not None and isValid(notifier) and isValid(connection):
            try:
                if connection.options:
                    notifier.options_changed.disconnect(connection.on_options_changed)
                else:
                    notifier.value_changed.disconnect(connection.on_value_changed)
            except (RuntimeError, SystemError):
                pass
        if connection.destroyed_handler is not None and isValid(connection.owner):
            try:
                connection.owner.destroyed.disconnect(connection.destroyed_handler)
            except (RuntimeError, SystemError):
                pass

    def get_option_index(self, key: str) -> int:
        """Returns the index of the selected option for a given key.

        Raises
        ------
        RuntimeError
            If the value associated with the key does not have a predefined list of options
        """
        if key not in self._entries:
            raise KeyError(UNKNOWN_KEY_ERROR.format(key=key))
        with self._lock:
            return self._entries[key].option_index

    def get_options(self, key: str) -> ParamTypeList:
        """Returns all valid options accepted for a given key.

        Raises
        ------
        RuntimeError
            If the value associated with the key does not have a predefined list of options.
        """
        if key not in self._entries:
            raise KeyError(UNKNOWN_KEY_ERROR.format(key=key))
        options = self._entries[key].options
        if options is None:
            raise RuntimeError(f'{key} has no options list.')
        return options

    def get_default_options(self, key: str) -> ParamTypeList:
        """Returns the default set of valid options accepted for a given key.

        Raises
        ------
        RuntimeError
            If the value associated with the key does not have a predefined list of options.
        """
        if key not in self._entries:
            raise KeyError(UNKNOWN_KEY_ERROR.format(key=key))
        options = self._entries[key].default_options()
        if options is None:
            raise RuntimeError(f'{key} has no default options list.')
        return options

    def update_options(self, key: str, options_list: ParamTypeList) -> None:
        """
        Replaces the list of accepted options for a given key.

        Raises
        ------
        RuntimeError
            If the value associated with the key does not have a predefined list of options.
        """
        if key not in self._entries:
            raise KeyError(UNKNOWN_KEY_ERROR.format(key=key))
        last_value = self.get(key)
        self._entries[key].set_valid_options(options_list)

        self._notifiers[key].options_changed.emit([*options_list])
        if last_value not in options_list and len(options_list) > 0:
            self.set(key, options_list[0])

    def restore_default_options(self, key: str) -> None:
        """
        Restores the default options list for a given key.

        Raises
        ------
        RuntimeError
            If the value associated with the key does not have a predefined list of options.
        """
        if key not in self._entries:
            raise KeyError(UNKNOWN_KEY_ERROR.format(key=key))
        default_options = self._entries[key].default_options()
        if default_options is not None:
            self.update_options(key, default_options)

    def add_option(self, key: str, option: ParamType) -> None:
        """
        Adds a new item to the list of accepted options for a given key.

        Raises
        ------
        RuntimeError
            If the value associated with the key does not have a predefined list of options.
        """
        if key not in self._entries:
            raise KeyError(UNKNOWN_KEY_ERROR.format(key=key))
        option_param_type = get_parameter_type(option)
        if option_param_type != self._entries[key].type_name:
            raise TypeError(f'Key "{key}": expected type "{self._entries[key].type_name}", but new option "{option}" '
                            f'has type {option_param_type}')
        all_options = self._entries[key].options
        assert all_options is not None
        if option not in all_options:
            all_options.append(option)  # type: ignore
            self.update_options(key, all_options)

    def get_categories(self) -> list[str]:
        """Returns all unique category strings."""
        categories = []
        for value in self._entries.values():
            if value.category not in categories:
                categories.append(value.category)
        return categories

    def get_subcategories(self, category: str) -> list[str]:
        """Returns all unique subcategories within a category."""
        subcategories = []
        for value in self._entries.values():
            if value.category != category:
                continue
            if value.subcategory is not None and value.subcategory not in subcategories:
                subcategories.append(value.subcategory)
        return subcategories

    def get_category_keys(self, category: str, subcategory: Optional[str] = None) -> list[str]:
        """Returns all keys with the given category."""
        keys = []
        for key, value in self._entries.items():
            if value.category == category and (subcategory is None or subcategory == value.subcategory):
                keys.append(key)
        return keys

    def get_keys(self) -> list[str]:
        """Returns all keys defined for a config class."""
        return list(self._entries.keys())

    def _add_entry(self,
                   key: str,
                   initial_value: Any,
                   label: str,
                   category: str,
                   subcategory: Optional[str],
                   tooltip: str,
                   options: Optional[list[ParamType]] = None,
                   range_options: Optional[dict[str, int | float]] = None,
                   save_json: bool = True,
                   pinned: bool = False,
                   control_hint: Optional[str] = None) -> None:
        if key in self._entries:
            raise KeyError(DUPLICATE_KEY_ERROR.format(key=key))
        entry = ConfigEntry(key, initial_value, label, category, subcategory, tooltip, options, range_options,
                            save_json, pinned, control_hint)
        self._entries[key] = entry
        self._notifiers[key] = _KeyNotifier()
        self._connected[key] = {}
        if options is not None:
            self._option_connected[key] = {}

    def _write_to_json(self) -> None:
        if self._json_path is None or self._newer_file:
            return
        converted_dict: dict[str, Any] = {CONFIG_VERSION_KEY: len(self._migrations())}
        with self._lock:
            for entry in self._entries.values():
                entry.save_to_json_dict(converted_dict)
            fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(self._json_path) or '.')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as file:
                    # noinspection PyTypeChecker
                    json.dump(converted_dict, file, ensure_ascii=False, indent=4)
                os.replace(temp_path, self._json_path)
            except Exception:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise

    def _read_from_json(self) -> None:
        if self._json_path is None:
            return
        json_data = None
        try:
            with open(self._json_path, encoding='utf-8') as file:
                json_data = json.load(file)
        except json.JSONDecodeError as err:
            logger.error(INVALID_JSON_ERROR.format(err=err))
        if json_data is None:  # Invalid JSON, replace it with defaults
            self._write_to_json()
            return
        if not isinstance(json_data, dict):
            logger.error(INVALID_JSON_ERROR.format(err='expected a JSON object'))
            self._write_to_json()
            return
        migrations = self._migrations()
        file_version = json_data.pop(CONFIG_VERSION_KEY, 0)
        if not isinstance(file_version, int) or isinstance(file_version, bool) or file_version < 0:
            file_version = 0
        if file_version > len(migrations):
            logger.warning(NEWER_VERSION_WARNING.format(path=self._json_path, version=file_version))
            self._newer_file = True
        for migration in migrations[file_version:]:
            migration(json_data)
        with self._lock:
            for entry in self._entries.values():
                entry.load_from_json_dict(json_data)
        if file_version < len(migrations):
            self._write_to_json()
