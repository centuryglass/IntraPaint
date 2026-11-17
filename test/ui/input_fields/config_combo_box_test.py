"""Tests that a config-bound `ComboBox` keeps showing the config's value when the key's option list changes."""
from PySide6.QtCore import QObject

from src.config.cache import Cache
from src.ui.input_fields.combo_box import ComboBox
from src.ui.input_fields.field_factory import create_control_widget
from test.base_test_case import IntraPaintTestCase

MODELS = ['alpha.safetensors', 'beta.safetensors', 'gamma.safetensors']


class ConfigComboBoxTest(IntraPaintTestCase):
    """Tests `create_control_widget`'s combo box across option list changes, using `Cache.SD_MODEL`, whose options
    start empty and are filled by a generator on connect."""

    def setUp(self) -> None:
        super().setUp()
        cache = Cache()
        cache.update_options(Cache.SD_MODEL, MODELS)
        cache.set(Cache.SD_MODEL, MODELS[1])
        widget = create_control_widget(cache, Cache.SD_MODEL)
        assert isinstance(widget, ComboBox)
        self.combo = widget
        self.saved_values: list[str] = []
        # `Config.connect` keeps one connection per owner and key, so the combo box can't own this one.
        self.spy_owner = QObject()
        cache.connect(self.spy_owner, Cache.SD_MODEL, self.saved_values.append)

    def tearDown(self) -> None:
        Cache().disconnect(self.spy_owner, Cache.SD_MODEL)
        Cache().restore_default_options(Cache.SD_MODEL)
        super().tearDown()

    def _assert_selected(self, value: str) -> None:
        self.assertEqual(Cache().get(Cache.SD_MODEL), value)
        self.assertEqual(self.combo.value(), value)

    def test_value_survives_options_emptied_and_refilled(self) -> None:
        """Clearing then refilling the options, as a generator disconnect and reconnect does, keeps the value."""
        cache = Cache()
        cache.restore_default_options(Cache.SD_MODEL)
        self.assertEqual(self.combo.count(), 0)
        self.assertEqual(cache.get(Cache.SD_MODEL), MODELS[1])
        cache.update_options(Cache.SD_MODEL, MODELS)
        self._assert_selected(MODELS[1])
        self.assertEqual(self.saved_values, [])

    def test_user_selection_survives_refresh(self) -> None:
        """A value chosen in the combo box stays selected when the options are reloaded in a new order."""
        self.combo.setValue(MODELS[2])
        self._assert_selected(MODELS[2])
        Cache().update_options(Cache.SD_MODEL, list(reversed(MODELS)))
        self._assert_selected(MODELS[2])
        self.assertEqual(self.saved_values, [MODELS[2]])

    def test_missing_value_falls_back_to_first_option(self) -> None:
        """When the new options lack the value, the config and the combo box both switch to the first option."""
        new_models = ['delta.safetensors', 'epsilon.safetensors']
        Cache().update_options(Cache.SD_MODEL, new_models)
        self._assert_selected(new_models[0])
        self.assertEqual(self.saved_values, [new_models[0]])

    def test_missing_value_after_empty_options_falls_back_to_first_option(self) -> None:
        """A value missing from options refilled after being emptied falls back to the first option."""
        cache = Cache()
        cache.restore_default_options(Cache.SD_MODEL)
        new_models = ['delta.safetensors', 'epsilon.safetensors']
        cache.update_options(Cache.SD_MODEL, new_models)
        self._assert_selected(new_models[0])

    def test_value_set_while_options_empty_is_kept(self) -> None:
        """A value added to the empty options with `add_missing_options` is selected once the options refill."""
        cache = Cache()
        cache.restore_default_options(Cache.SD_MODEL)
        cache.set(Cache.SD_MODEL, MODELS[2], add_missing_options=True)
        self._assert_selected(MODELS[2])
        cache.update_options(Cache.SD_MODEL, MODELS)
        self._assert_selected(MODELS[2])

    def test_added_option_keeps_selection(self) -> None:
        """`Config.add_option` adds the item without changing the selection."""
        Cache().add_option(Cache.SD_MODEL, 'delta.safetensors')
        self._assert_selected(MODELS[1])
        self.assertEqual(self.combo.count(), len(MODELS) + 1)
        self.assertEqual(self.saved_values, [])
