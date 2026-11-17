"""Tests for the recent files list behind File > Open Recent."""
import json
import os

from src.config.cache import Cache
from src.util.recent_files import MAX_RECENT_FILES, add_recent_file, clear_recent_files, recent_files
from test.base_test_case import IntraPaintTestCase


class TestRecentFiles(IntraPaintTestCase):
    """Tests ordering, deduplication, the length cap and persistence."""

    def setUp(self) -> None:
        super().setUp()
        clear_recent_files()

    def test_newest_first(self) -> None:
        add_recent_file('/tmp/a.png')
        add_recent_file('/tmp/b.png')
        self.assertEqual(recent_files(), ['/tmp/b.png', '/tmp/a.png'])

    def test_readding_moves_to_front_without_duplicates(self) -> None:
        for name in ('a', 'b', 'c'):
            add_recent_file(f'/tmp/{name}.png')
        add_recent_file('/tmp/a.png')
        self.assertEqual(recent_files(), ['/tmp/a.png', '/tmp/c.png', '/tmp/b.png'])

    def test_relative_paths_are_stored_absolute(self) -> None:
        add_recent_file('image.png')
        self.assertEqual(recent_files(), [os.path.abspath('image.png')])

    def test_list_is_capped(self) -> None:
        for index in range(MAX_RECENT_FILES + 5):
            add_recent_file(f'/tmp/{index}.png')
        paths = recent_files()
        self.assertEqual(len(paths), MAX_RECENT_FILES)
        self.assertEqual(paths[0], f'/tmp/{MAX_RECENT_FILES + 4}.png')
        self.assertEqual(paths[-1], '/tmp/5.png')

    def test_clear(self) -> None:
        add_recent_file('/tmp/a.png')
        clear_recent_files()
        self.assertEqual(recent_files(), [])

    def test_value_is_saved_between_runs(self) -> None:
        """The config definition keeps the list in the saved cache file, so it survives a restart."""
        with open('resources/config/cache_value_definitions.json', encoding='utf-8') as definitions_file:
            definition = json.load(definitions_file)[Cache.RECENT_FILES]
        self.assertTrue(definition['saved'])
        self.assertEqual(definition['default'], [])
