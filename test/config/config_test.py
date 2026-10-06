"""Tests for `Config` behavior that doesn't depend on a particular config file's contents, and for how the real
definition files map onto the config classes.

Most tests use `_ScratchConfig`, a private `Config` backed by a temporary definition file that covers every value type.
The shared singletons stay untouched, so these tests can construct, save and reload a config freely.
"""
import json
import os
import shutil
import tempfile
import threading
from typing import Any
from unittest.mock import patch

import pytest
from PySide6.QtCore import QSize

from src.config import application_config
from src.config.a1111_config import A1111Config
from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.config import Config
from src.config.config_entry import RangeKey
from src.config.config_from_key import get_config_from_key
from src.config.key_config import KeyConfig
from src.util.singleton import Singleton
from test.base_test_case import IntraPaintTestCase, PROJECT_ROOT

# Upper bound for a worker thread that should finish immediately. Only a deadlock reaches it.
THREAD_JOIN_TIMEOUT_SECONDS = 10.0

TEST_KEY = 'test_flag'

# Definitions for _ScratchConfig, one or more for each value type the definition format supports:
BOOL_KEY = 'test_flag'
INT_KEY = 'test_int'
FLOAT_KEY = 'test_float'
STR_KEY = 'test_str'
OPTION_KEY = 'test_option'
SIZE_KEY = 'test_size'
LIST_KEY = 'test_list'
DICT_KEY = 'test_dict'
UNSAVED_KEY = 'test_unsaved'
SCRATCH_DEFINITIONS: dict[str, dict[str, Any]] = {
    BOOL_KEY: {'type': 'bool', 'default': False},
    INT_KEY: {'type': 'int', 'default': 5, 'range_options': {'min': 1, 'max': 10, 'step': 1}},
    FLOAT_KEY: {'type': 'float', 'default': 0.5, 'range_options': {'min': 0.0, 'max': 1.0, 'step': 0.1}},
    STR_KEY: {'type': 'string', 'default': 'text'},
    OPTION_KEY: {'type': 'string', 'default': 'first', 'options': ['first', 'second']},
    SIZE_KEY: {'type': 'Size', 'default': '64x32'},
    LIST_KEY: {'type': 'list', 'default': ['a']},
    DICT_KEY: {'type': 'dict', 'default': {'inner': 1}},
    UNSAVED_KEY: {'type': 'string', 'default': 'not saved', 'saved': False},
}
DEFAULT_VALUES: dict[str, Any] = {
    BOOL_KEY: False,
    INT_KEY: 5,
    FLOAT_KEY: 0.5,
    STR_KEY: 'text',
    OPTION_KEY: 'first',
    SIZE_KEY: QSize(64, 32),
    LIST_KEY: ['a'],
    DICT_KEY: {'inner': 1},
    UNSAVED_KEY: 'not saved',
}
# A valid non-default value for each key:
CHANGED_VALUES: dict[str, Any] = {
    BOOL_KEY: True,
    INT_KEY: 10,
    FLOAT_KEY: 0.25,
    STR_KEY: 'changed',
    OPTION_KEY: 'second',
    SIZE_KEY: QSize(16, 8),
    LIST_KEY: ['b', 'c'],
    DICT_KEY: {'inner': 2, 'other': 'x'},
    UNSAVED_KEY: 'changed',
}
# A value of the wrong type for each key:
WRONG_TYPE_VALUES: dict[str, Any] = {
    BOOL_KEY: 1,
    INT_KEY: 2.0,
    FLOAT_KEY: 1,
    STR_KEY: 3,
    OPTION_KEY: 3,
    SIZE_KEY: '16x8',
    LIST_KEY: 'a',
    DICT_KEY: ['inner'],
    UNSAVED_KEY: None,
}

CONFIG_DEFINITION_DIR = os.path.join(PROJECT_ROOT, 'resources', 'config')
DEFINITION_FILE_CLASSES: dict[str, type[Config]] = {
    'application_config_definitions.json': AppConfig,
    'cache_value_definitions.json': Cache,
    'key_config_definitions.json': KeyConfig,
    'a1111_setting_definitions.json': A1111Config,
}


class _ScratchConfig(Config):
    """A `Config` that isn't one of the shared singletons, backed by files in a temporary directory."""

    def __init__(self, definition_path: str, json_path: str) -> None:
        super().__init__(definition_path, json_path, _ScratchConfig)


class ConfigTest(IntraPaintTestCase):
    """Tests for `Config`."""

    def setUp(self) -> None:
        super().setUp()
        self.temp_dir = tempfile.mkdtemp(prefix='intrapaint-config-test-')
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)
        self.definition_path = os.path.join(self.temp_dir, 'scratch_definitions.json')
        self.json_path = os.path.join(self.temp_dir, 'scratch.json')
        definitions = {key: {'label': key, 'category': 'Test', 'description': key, 'saved': True, **definition}
                       for key, definition in SCRATCH_DEFINITIONS.items()}
        with open(self.definition_path, 'w', encoding='utf-8') as file:
            json.dump(definitions, file)

    def _config(self) -> _ScratchConfig:
        """Creates a scratch config from the definition file, loading the saved JSON file if it exists.

        Its save timer stops at cleanup. Otherwise a save scheduled by `set` would fire in a later test, after the
        temporary directory is gone.
        """
        config = _ScratchConfig(self.definition_path, self.json_path)
        self.addCleanup(config._save_timer.stop)  # pylint: disable=protected-access
        return config

    def _write_saved_values(self, values: dict[str, Any]) -> None:
        with open(self.json_path, 'w', encoding='utf-8') as file:
            json.dump(values, file)

    def _read_saved_values(self) -> dict[str, Any]:
        with open(self.json_path, encoding='utf-8') as file:
            return json.load(file)

    def test_get_returns_defaults(self) -> None:
        """A new config with no saved file returns each definition's default, converted to its type."""
        config = self._config()
        for key, expected in DEFAULT_VALUES.items():
            with self.subTest(key=key):
                self.assertEqual(config.get(key), expected)
                self.assertIs(type(config.get(key)), type(expected))

    def test_get_returns_copies(self) -> None:
        """Changing a list, dict or QSize returned by `get` leaves the stored value unchanged."""
        config = self._config()
        config.get(LIST_KEY).append('changed')
        config.get(DICT_KEY)['inner'] = 'changed'
        config.get(SIZE_KEY).setWidth(1)
        self.assertEqual(config.get(LIST_KEY), DEFAULT_VALUES[LIST_KEY])
        self.assertEqual(config.get(DICT_KEY), DEFAULT_VALUES[DICT_KEY])
        self.assertEqual(config.get(SIZE_KEY), DEFAULT_VALUES[SIZE_KEY])

    def test_set_and_connect(self) -> None:
        """`set` changes each value type and calls its connected callbacks with the new value."""
        config = self._config()
        for key, new_value in CHANGED_VALUES.items():
            with self.subTest(key=key):
                no_arg_calls: list[None] = []
                one_arg_calls: list[Any] = []
                two_arg_calls: list[tuple[Any, Any]] = []
                config.connect('no_arg', key, lambda: no_arg_calls.append(None))
                config.connect('one_arg', key, one_arg_calls.append)
                config.connect('two_arg', key, lambda value, inner_key: two_arg_calls.append((value, inner_key)))
                config.set(key, new_value, save_change=False)
                self.assertEqual(config.get(key), new_value)
                self.assertEqual(no_arg_calls, [None])
                self.assertEqual(one_arg_calls, [new_value])
                self.assertEqual(two_arg_calls, [(new_value, None)])

    def test_set_unchanged_value_skips_callbacks(self) -> None:
        """Setting the value a key already holds doesn't call its callbacks."""
        config = self._config()
        calls: list[Any] = []
        config.connect(self, STR_KEY, calls.append)
        config.set(STR_KEY, DEFAULT_VALUES[STR_KEY], save_change=False)
        self.assertEqual(calls, [])

    def test_disconnect_stops_callbacks(self) -> None:
        """After `disconnect`, and after `disconnect_all`, a callback no longer runs."""
        config = self._config()
        calls: list[Any] = []
        config.connect(self, STR_KEY, calls.append)
        config.connect(self, INT_KEY, calls.append)
        config.disconnect(self, STR_KEY)
        config.set(STR_KEY, 'changed', save_change=False)
        self.assertEqual(calls, [])
        config.disconnect_all(self)
        config.set(INT_KEY, 2, save_change=False)
        self.assertEqual(calls, [])

    def test_connect_replaces_callback_for_same_object(self) -> None:
        """A second `connect` with the same object and key replaces the first callback."""
        config = self._config()
        first_calls: list[Any] = []
        second_calls: list[Any] = []
        config.connect(self, STR_KEY, first_calls.append)
        config.connect(self, STR_KEY, second_calls.append)
        config.set(STR_KEY, 'changed', save_change=False)
        self.assertEqual(first_calls, [])
        self.assertEqual(second_calls, ['changed'])

    def test_set_wrong_type_raises_type_error(self) -> None:
        """Setting a value of another type raises TypeError and keeps the old value."""
        config = self._config()
        for key, wrong_value in WRONG_TYPE_VALUES.items():
            with self.subTest(key=key):
                with self.assertRaises(TypeError):
                    config.set(key, wrong_value, save_change=False)
                self.assertEqual(config.get(key), DEFAULT_VALUES[key])

    def test_range_limits(self) -> None:
        """Numeric keys accept their range limits, reject values outside them, and report them through `get`."""
        config = self._config()
        for key, minimum, maximum, step, below, above in ((INT_KEY, 1, 10, 1, 0, 11),
                                                          (FLOAT_KEY, 0.0, 1.0, 0.1, -0.01, 1.01)):
            with self.subTest(key=key):
                self.assertEqual(config.get(key, RangeKey.MIN), minimum)
                self.assertEqual(config.get(key, RangeKey.MAX), maximum)
                self.assertEqual(config.get(key, RangeKey.STEP), step)
                for valid_value in (minimum, maximum):
                    config.set(key, valid_value, save_change=False)
                    self.assertEqual(config.get(key), valid_value)
                for invalid_value in (below, above):
                    with self.assertRaises(ValueError):
                        config.set(key, invalid_value, save_change=False)
                    self.assertEqual(config.get(key), maximum)

    def test_options(self) -> None:
        """A key with an options list rejects other values, unless `add_missing_options` adds them to the list."""
        config = self._config()
        self.assertEqual(config.get_options(OPTION_KEY), ['first', 'second'])
        with self.assertRaises(ValueError):
            config.set(OPTION_KEY, 'third', save_change=False)
        self.assertEqual(config.get(OPTION_KEY), 'first')
        config.set(OPTION_KEY, 'third', save_change=False, add_missing_options=True)
        self.assertEqual(config.get(OPTION_KEY), 'third')
        self.assertEqual(config.get_options(OPTION_KEY), ['first', 'second', 'third'])
        self.assertEqual(config.get_option_index(OPTION_KEY), 2)
        with self.assertRaises(RuntimeError):
            config.get_options(STR_KEY)

    def test_update_options_replaces_invalid_value(self) -> None:
        """Replacing the options list notifies option listeners, and moves a value no longer listed to the first
        new option."""
        config = self._config()
        option_lists: list[list[Any]] = []
        values: list[Any] = []
        config.connect_to_option_changes(self, OPTION_KEY, option_lists.append)
        config.connect(self, OPTION_KEY, values.append)
        config.update_options(OPTION_KEY, ['x', 'y'])
        self.assertEqual(option_lists, [['x', 'y']])
        self.assertEqual(config.get(OPTION_KEY), 'x')
        self.assertEqual(values, ['x'])

    def test_inner_key(self) -> None:
        """`set` with an inner key changes one entry of a dict value, and only callbacks for that entry run."""
        config = self._config()
        inner_calls: list[Any] = []
        other_calls: list[Any] = []
        config.connect('inner', DICT_KEY, inner_calls.append, inner_key='inner')
        config.connect('other', DICT_KEY, other_calls.append, inner_key='other')
        config.set(DICT_KEY, 7, save_change=False, inner_key='inner')
        self.assertEqual(config.get(DICT_KEY, 'inner'), 7)
        self.assertIsNone(config.get(DICT_KEY, 'missing'))
        self.assertEqual(inner_calls, [7])
        self.assertEqual(other_calls, [])
        with self.assertRaises(TypeError):
            config.set(STR_KEY, 'x', save_change=False, inner_key='inner')

    def test_missing_key_raises_key_error(self) -> None:
        """Every method that takes a key raises KeyError for a key the config doesn't define."""
        config = self._config()
        for name, call in (('get', lambda: config.get('missing')),
                           ('set', lambda: config.set('missing', 1, save_change=False)),
                           ('connect', lambda: config.connect(self, 'missing', lambda: None)),
                           ('disconnect', lambda: config.disconnect(self, 'missing')),
                           ('get_label', lambda: config.get_label('missing')),
                           ('get_data_type', lambda: config.get_data_type('missing')),
                           ('get_options', lambda: config.get_options('missing'))):
            with self.subTest(method=name):
                with self.assertRaises(KeyError):
                    call()

    def test_missing_key_raises_key_error_on_shared_configs(self) -> None:
        """The shared configs raise KeyError for an unknown key, and so does looking up its owner."""
        for config in (AppConfig(), Cache(), KeyConfig()):
            with self.subTest(config=type(config).__name__):
                with self.assertRaises(KeyError):
                    config.get('not_a_config_key')
        with self.assertRaises(KeyError):
            get_config_from_key('not_a_config_key')

    def test_new_config_writes_defaults(self) -> None:
        """A config with no saved file creates one holding every saved default, in the saved file format."""
        self._config()
        self.assertEqual(self._read_saved_values(), {
            BOOL_KEY: False,
            INT_KEY: {'min': 1, 'max': 10, 'step': 1, 'value': 5},
            FLOAT_KEY: {'min': 0.0, 'max': 1.0, 'step': 0.1, 'value': 0.5},
            STR_KEY: 'text',
            OPTION_KEY: 'first',
            SIZE_KEY: '64x32',
            LIST_KEY: ['a'],
            DICT_KEY: {'inner': 1},
        })

    def test_save_and_reload(self) -> None:
        """Saved changes to every value type load back into a new config from the same file. Keys defined with
        `"saved": false` go back to their defaults."""
        config = self._config()
        for key, new_value in CHANGED_VALUES.items():
            config.set(key, new_value, save_change=False)
        # On the main thread `set` saves on a timer, and tests don't run the event loop:
        config._write_to_json()  # pylint: disable=protected-access
        reloaded = self._config()
        for key, expected in CHANGED_VALUES.items():
            with self.subTest(key=key):
                self.assertEqual(reloaded.get(key), DEFAULT_VALUES[key] if key == UNSAVED_KEY else expected)

    def test_load_with_unknown_and_missing_keys(self) -> None:
        """Loading a file ignores keys the definitions don't have, and uses defaults for keys the file lacks. The next
        save drops the unknown keys and adds the missing ones."""
        self._write_saved_values({STR_KEY: 'saved', 'removed_key': 'stale'})
        config = self._config()
        self.assertEqual(config.get(STR_KEY), 'saved')
        self.assertEqual(config.get(INT_KEY), DEFAULT_VALUES[INT_KEY])
        with self.assertRaises(KeyError):
            config.get('removed_key')
        config._write_to_json()  # pylint: disable=protected-access
        saved = self._read_saved_values()
        self.assertNotIn('removed_key', saved)
        self.assertEqual(saved[STR_KEY], 'saved')
        self.assertEqual(saved[INT_KEY]['value'], DEFAULT_VALUES[INT_KEY])

    def test_load_skips_invalid_saved_values(self) -> None:
        """A saved value with the wrong type, outside its range, or not in its options keeps the default."""
        self._write_saved_values({BOOL_KEY: 'yes', INT_KEY: {'value': 50}, OPTION_KEY: 'unknown', STR_KEY: 7})
        config = self._config()
        for key in (BOOL_KEY, INT_KEY, OPTION_KEY, STR_KEY):
            with self.subTest(key=key):
                self.assertEqual(config.get(key), DEFAULT_VALUES[key])

    def test_load_reads_saved_range(self) -> None:
        """Range limits in the saved file replace the definition's limits."""
        self._write_saved_values({INT_KEY: {'min': 2, 'max': 20, 'step': 2, 'value': 15}})
        config = self._config()
        self.assertEqual(config.get(INT_KEY), 15)
        self.assertEqual(config.get(INT_KEY, RangeKey.MIN), 2)
        self.assertEqual(config.get(INT_KEY, RangeKey.MAX), 20)
        self.assertEqual(config.get(INT_KEY, RangeKey.STEP), 2)

    def test_load_invalid_json_restores_defaults(self) -> None:
        """A saved file that isn't valid JSON loads as defaults, and is replaced with the defaults."""
        with open(self.json_path, 'w', encoding='utf-8') as file:
            file.write('{"test_str": "trunc')
        config = self._config()
        self.assertEqual(config.get(STR_KEY), DEFAULT_VALUES[STR_KEY])
        self.assertEqual(self._read_saved_values()[STR_KEY], DEFAULT_VALUES[STR_KEY])

    def test_failed_write_keeps_previous_file(self) -> None:
        """A save that fails partway through leaves the previous file intact and no temporary file behind."""
        config = self._config()
        with open(self.json_path, encoding='utf-8') as file:
            saved_text = file.read()
        config.set(STR_KEY, 'changed', save_change=False)

        def _fail_partway(data: Any, file: Any, **_kwargs: Any) -> None:
            file.write(json.dumps(data)[:10])
            raise OSError('disk full')

        with patch('src.config.config.json.dump', _fail_partway):
            with self.assertRaises(OSError):
                config._write_to_json()  # pylint: disable=protected-access
        with open(self.json_path, encoding='utf-8') as file:
            self.assertEqual(file.read(), saved_text)
        self.assertEqual(sorted(os.listdir(self.temp_dir)), sorted([os.path.basename(self.definition_path),
                                                                    os.path.basename(self.json_path)]))

    def test_set_with_save_from_worker_thread_does_not_deadlock(self) -> None:
        """`Config.set` with `save_change=True` off the main thread finishes and writes the change to the JSON file.

        This uses a private `Config` instead of `AppConfig`: a deadlocked `set` keeps its lock forever, and
        `IntraPaintTestCase.tearDown` resets the shared singletons, which would block on that lock and hang the suite
        instead of failing this test.
        """
        config = self._config()
        errors: list[BaseException] = []

        def set_value() -> None:
            try:
                config.set(TEST_KEY, True, save_change=True)
            except BaseException as err:  # pylint: disable=broad-exception-caught
                errors.append(err)

        # Daemon, so a deadlocked worker can't keep the process alive after the test fails.
        worker = threading.Thread(target=set_value, daemon=True)
        worker.start()
        worker.join(THREAD_JOIN_TIMEOUT_SECONDS)
        self.assertFalse(worker.is_alive(), 'Config.set deadlocked when saving from a worker thread')
        self.assertEqual([], errors)
        self.assertTrue(config.get(TEST_KEY))
        self.assertTrue(self._read_saved_values()[TEST_KEY])

    @pytest.mark.xfail(strict=True, reason='https://github.com/centuryglass/IntraPaint/issues/28')
    def test_set_from_worker_thread_does_not_run_callbacks_there(self) -> None:
        """A `set` call on a worker thread doesn't run connected callbacks on that thread, where they could change
        widgets."""
        config = self._config()
        callback_threads: list[threading.Thread] = []
        config.connect(self, STR_KEY, lambda: callback_threads.append(threading.current_thread()))

        def set_value() -> None:
            try:
                config.set(STR_KEY, 'changed', save_change=False)
            except AssertionError:  # The main-thread assertion #28 proposes is an acceptable fix.
                pass

        worker = threading.Thread(target=set_value, daemon=True)
        worker.start()
        worker.join(THREAD_JOIN_TIMEOUT_SECONDS)
        self.assertFalse(worker.is_alive())
        self.assertNotIn(worker, callback_threads)


class AppConfigDataDirTest(IntraPaintTestCase):
    """Tests `AppConfig._adjust_defaults`, which fills empty user data directory settings."""

    def test_adjust_defaults_with_existing_directories(self) -> None:
        """Filling empty directory settings works when the directories already exist, as when another instance
        created them first, and the settings point at those directories."""
        data_dir = tempfile.mkdtemp(prefix='intrapaint-data-dir-test-')
        self.addCleanup(shutil.rmtree, data_dir, ignore_errors=True)
        keys_and_names = ((AppConfig.LIBMYPAINT_LIBRARY_DIR, 'libmypaint-lib-files'),
                          (AppConfig.ADDED_FONT_DIR, 'fonts'),
                          (AppConfig.ADDED_MYPAINT_BRUSH_DIR, 'mypaint-brushes'))
        for _, dir_name in keys_and_names:
            os.mkdir(os.path.join(data_dir, dir_name))
        config = AppConfig()
        for key, _ in keys_and_names:
            config.set(key, '', save_change=False)
        with patch.object(application_config, 'DATA_DIR', data_dir):
            config._adjust_defaults()  # pylint: disable=protected-access
        for key, dir_name in keys_and_names:
            with self.subTest(key=key):
                self.assertEqual(config.get(key), os.path.join(data_dir, dir_name))


class ConfigKeyOwnershipTest(IntraPaintTestCase):
    """Checks the real definition files in `resources/config/` against the config classes and `get_config_from_key`."""

    def setUp(self) -> None:
        super().setUp()
        # A1111Config normally exists only once the WebUI generator connects (see reset_singletons). Create it for
        # this test and discard it afterward, unless an earlier test already created it.
        # pylint: disable=protected-access
        if A1111Config not in Singleton._instances:
            self.addCleanup(Singleton._instances.pop, A1111Config, None)
        A1111Config()

    def _definition_keys(self) -> dict[str, list[str]]:
        """Returns each definition file's keys, by file name."""
        keys: dict[str, list[str]] = {}
        for file_name in DEFINITION_FILE_CLASSES:
            with open(os.path.join(CONFIG_DEFINITION_DIR, file_name), encoding='utf-8') as file:
                keys[file_name] = list(json.load(file).keys())
        return keys

    def test_definition_files_match_config_classes(self) -> None:
        """Every definition file in `resources/config/` belongs to a config class, which defines exactly its keys."""
        self.assertEqual(sorted(name for name in os.listdir(CONFIG_DEFINITION_DIR) if name.endswith('.json')),
                         sorted(DEFINITION_FILE_CLASSES))
        for file_name, keys in self._definition_keys().items():
            config_class = DEFINITION_FILE_CLASSES[file_name]
            with self.subTest(config=config_class.__name__):
                self.assertEqual(sorted(config_class().get_keys()), sorted(keys))

    def test_keys_are_unique_across_definition_files(self) -> None:
        """No key is defined in more than one definition file, so `get_config_from_key` can't shadow one."""
        owners: dict[str, list[str]] = {}
        for file_name, keys in self._definition_keys().items():
            for key in keys:
                owners.setdefault(key, []).append(file_name)
        self.assertEqual({key: files for key, files in owners.items() if len(files) > 1}, {})

    def test_every_key_resolves_to_its_config(self) -> None:
        """`get_config_from_key` returns the config whose definition file defines the key."""
        for file_name, keys in self._definition_keys().items():
            config_class = DEFINITION_FILE_CLASSES[file_name]
            with self.subTest(config=config_class.__name__):
                wrong_owners = {key: type(get_config_from_key(key)).__name__ for key in keys
                                if get_config_from_key(key) is not config_class()}
                self.assertEqual(wrong_owners, {})
