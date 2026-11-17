"""Tests SeedValueSpinbox's binding to its Cache keys, for seeds beyond the range of C integers."""
import sys

from PySide6 import QtTest
from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.ui.input_fields.big_int_spinbox import BigIntSpinbox
from src.ui.input_fields.seed_value_spinbox import SeedValueSpinbox
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

# Seeds at and past the limits of 32- and 64-bit integers, up to the largest the seed keys accept:
LARGE_SEEDS = (2 ** 31, 2 ** 63 - 1, 2 ** 63, BigIntSpinbox.MAXIMUM)


class SeedValueSpinboxTest(IntraPaintTestCase):
    """Tests the seed and variation seed fields against `Cache.SEED` and `Cache.WEBUI_SUBSEED`."""

    @staticmethod
    def _key_pairs() -> tuple[tuple[str, str], ...]:
        """Returns each (seed key, last seed key) pair a `SeedValueSpinbox` edits."""
        return (Cache.SEED, Cache.LAST_SEED), (Cache.WEBUI_SUBSEED, Cache.WEBUI_LAST_SUBSEED)

    def test_typed_seed_is_cached_as_int(self) -> None:
        """A typed seed reaches the Cache as an int, including seeds a C integer can't hold."""
        cache = Cache()
        for seed_key, last_seed_key in self._key_pairs():
            line_edit = SeedValueSpinbox(seed_key, last_seed_key).findChild(BigIntSpinbox).lineEdit()
            for seed in (-1, 5, *LARGE_SEEDS):
                with self.subTest(key=seed_key, seed=seed):
                    line_edit.clear()
                    QtTest.QTest.keyClicks(line_edit, str(seed))
                    self.assertEqual(cache.get(seed_key), seed)
                    self.assertIs(type(cache.get(seed_key)), int)

    def test_cached_seed_updates_field(self) -> None:
        """Setting a large seed in the Cache shows it in the field, through Config's change signal."""
        cache = Cache()
        for seed_key, last_seed_key in self._key_pairs():
            field = SeedValueSpinbox(seed_key, last_seed_key)
            emitted: list[str] = []
            field.valueChanged.connect(emitted.append)
            for seed in LARGE_SEEDS:
                with self.subTest(key=seed_key, seed=seed):
                    cache.set(seed_key, seed)
                    self.assertEqual(field.value(), seed)
                    self.assertEqual(emitted[-1], str(seed))
                    self.assertEqual(cache.get(seed_key), seed)

    def test_reuse_last_seed_handles_large_seeds(self) -> None:
        """The reuse button copies a large last seed into the seed key as an int, and randomize sets -1."""
        cache = Cache()
        for seed_key, last_seed_key in self._key_pairs():
            field = SeedValueSpinbox(seed_key, last_seed_key)
            with self.subTest(key=seed_key):
                cache.set(last_seed_key, str(BigIntSpinbox.MAXIMUM))
                field._repeat_button.click()  # pylint: disable=protected-access
                self.assertEqual(cache.get(seed_key), BigIntSpinbox.MAXIMUM)
                self.assertIs(type(cache.get(seed_key)), int)
                self.assertEqual(field.value(), BigIntSpinbox.MAXIMUM)
                field._randomize_button.click()  # pylint: disable=protected-access
                self.assertEqual(cache.get(seed_key), -1)
                self.assertEqual(field.value(), -1)
