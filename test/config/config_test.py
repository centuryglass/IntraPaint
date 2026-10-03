"""Tests for `Config` behavior that doesn't depend on a particular config file's contents."""
import json
import os
import shutil
import tempfile
import threading

from src.config.config import Config
from test.base_test_case import IntraPaintTestCase

# Upper bound for a worker thread that should finish immediately. Only a deadlock reaches it.
THREAD_JOIN_TIMEOUT_SECONDS = 10.0

TEST_KEY = 'test_flag'


class _ScratchConfig(Config):
    """A `Config` that isn't one of the shared singletons, backed by files in a temporary directory."""

    def __init__(self, definition_path: str, json_path: str) -> None:
        super().__init__(definition_path, json_path, _ScratchConfig)


class ConfigTest(IntraPaintTestCase):
    """Tests for `Config`."""

    def test_set_with_save_from_worker_thread_does_not_deadlock(self) -> None:
        """`Config.set` with `save_change=True` off the main thread finishes and writes the change to the JSON file.

        This uses a private `Config` instead of `AppConfig`: a deadlocked `set` keeps its lock forever, and
        `IntraPaintTestCase.tearDown` resets the shared singletons, which would block on that lock and hang the suite
        instead of failing this test.
        """
        temp_dir = tempfile.mkdtemp(prefix='intrapaint-config-test-')
        self.addCleanup(shutil.rmtree, temp_dir, ignore_errors=True)
        definition_path = os.path.join(temp_dir, 'scratch_definitions.json')
        json_path = os.path.join(temp_dir, 'scratch.json')
        with open(definition_path, 'w', encoding='utf-8') as file:
            json.dump({TEST_KEY: {'label': 'Test flag', 'category': 'Test', 'description': 'Test flag', 'type': 'bool',
                                  'default': False, 'saved': True}}, file)
        config = _ScratchConfig(definition_path, json_path)
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
        with open(json_path, encoding='utf-8') as file:
            self.assertTrue(json.load(file)[TEST_KEY])
