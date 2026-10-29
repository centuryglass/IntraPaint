"""Tests KeyConfig keybinding validation and the migration of saved key bindings."""
import json
import os
import shutil
import tempfile
from unittest.mock import patch

from PySide6.QtCore import Qt

from src.config.config import Config
from src.config.key_config import CONFIG_DEFINITIONS, KeyConfig
from src.tools.base_tool import FIXED_ASPECT_HINT, BaseTool
from test.base_test_case import IntraPaintTestCase


def _validation_errors() -> list[str]:
    """Runs keybinding validation and returns the reported messages."""
    with patch('src.config.key_config.show_warning_dialog') as warning:
        KeyConfig().validate_keybindings()
    if not warning.called:
        return []
    return [str(warning.call_args.args[2])]


class KeyConfigValidationTest(IntraPaintTestCase):
    """Validation reports problems instead of raising."""

    def test_defaults_valid(self) -> None:
        """The default bindings produce no warnings."""
        self.assertEqual([], _validation_errors())

    def test_speed_modifier_in_binding(self) -> None:
        """A speed-modified binding that includes the speed modifier is reported."""
        config = KeyConfig()
        config.set(KeyConfig.SPEED_MODIFIER, 'Alt')
        config.set(KeyConfig.PAN_LEFT, 'Alt+Left')
        errors = _validation_errors()
        self.assertEqual(1, len(errors))
        self.assertIn('speed modifier', errors[0])
        self.assertIn('Alt+Left', errors[0])

    def test_speed_modified_variant_collision(self) -> None:
        """A speed-modified variant that collides with another binding names both entries."""
        config = KeyConfig()
        config.set(KeyConfig.SPEED_MODIFIER, 'Alt')
        config.set(KeyConfig.PAN_LEFT, 'Z')
        config.set(KeyConfig.BRUSH_TOOL_KEY, 'Alt+Z')
        errors = _validation_errors()
        self.assertEqual(1, len(errors))
        self.assertIn('with speed modifier', errors[0])
        self.assertIn('Alt+Z', errors[0])


class _ScratchKeyConfig(Config):
    """A key config that isn't the shared singleton, with `KeyConfig`'s definitions and previous defaults."""
    PREVIOUS_DEFAULTS = KeyConfig.PREVIOUS_DEFAULTS

    def __init__(self, json_path: str) -> None:
        super().__init__(CONFIG_DEFINITIONS, json_path, _ScratchKeyConfig)


class KeyConfigMigrationTest(IntraPaintTestCase):
    """Saved key bindings from before a default changed follow the new default, unless the user changed them."""

    def _load(self, saved: dict[str, str]) -> _ScratchKeyConfig:
        temp_dir = tempfile.mkdtemp(prefix='intrapaint-key-config-test-')
        self.addCleanup(shutil.rmtree, temp_dir, ignore_errors=True)
        json_path = os.path.join(temp_dir, 'key_config.json')
        with open(json_path, 'w', encoding='utf-8') as file:
            json.dump(saved, file)
        config = _ScratchKeyConfig(json_path)
        self.addCleanup(config._save_timer.stop)  # pylint: disable=protected-access
        return config

    def test_rename_and_resize_defaults(self) -> None:
        """Rename layer takes F2, and Resize canvas moved to Shift+F2."""
        self.assertEqual('F2', KeyConfig().get(KeyConfig.RENAME_LAYER_SHORTCUT))
        self.assertEqual('Shift+F2', KeyConfig().get(KeyConfig.RESIZE_CANVAS_SHORTCUT))

    def test_saved_old_resize_default_moves(self) -> None:
        """An unversioned file that holds the old F2 for Resize canvas loads the new default."""
        config = self._load({'resize_canvas_shortcut': 'F2'})
        self.assertEqual('Shift+F2', config.get('resize_canvas_shortcut'))
        self.assertEqual('F2', config.get('rename_layer_shortcut'))

    def test_custom_resize_binding_kept(self) -> None:
        """An unversioned file keeps a Resize canvas binding the user chose."""
        config = self._load({'resize_canvas_shortcut': 'Ctrl+Alt+Z'})
        self.assertEqual('Ctrl+Alt+Z', config.get('resize_canvas_shortcut'))


class KeyConfigModifierTest(IntraPaintTestCase):
    """An empty modifier binding means no modifier, not an error."""

    def test_get_modifier_empty_value_means_no_modifier(self) -> None:
        """get_modifier returns NoModifier for an unbound modifier instead of raising."""
        config = KeyConfig()
        config.set(KeyConfig.FIXED_ASPECT_MODIFIER, '')
        self.assertEqual(Qt.KeyboardModifier.NoModifier,
                         config.get_modifier(KeyConfig.FIXED_ASPECT_MODIFIER))

    def test_modifier_hint_omitted_for_empty_binding(self) -> None:
        """modifier_hint returns an empty string for an unbound modifier instead of raising."""
        KeyConfig().set(KeyConfig.FIXED_ASPECT_MODIFIER, '')
        self.assertEqual('', BaseTool.modifier_hint(KeyConfig.FIXED_ASPECT_MODIFIER, FIXED_ASPECT_HINT))
