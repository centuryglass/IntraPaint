"""Tests KeyConfig keybinding validation and the migration of saved key bindings."""
import json
import os
import shutil
import tempfile
from unittest.mock import patch

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent

from src.config.config import Config
from src.config.key_config import CONFIG_DEFINITIONS, KeyConfig
from src.tools.base_tool import FIXED_ASPECT_HINT, BaseTool
from src.util.key_code_utils import get_key_with_modifiers, key_alternatives
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
        """Rename layer takes F2, and Resize canvas keeps Shift+F2 as its second binding."""
        self.assertEqual('F2', KeyConfig().get(KeyConfig.RENAME_LAYER_SHORTCUT))
        self.assertEqual('Ctrl+Alt+C,Shift+F2', KeyConfig().get(KeyConfig.RESIZE_CANVAS_SHORTCUT))

    def test_saved_old_resize_default_moves(self) -> None:
        """An unversioned file that holds the old F2 for Resize canvas loads the new default."""
        config = self._load({'resize_canvas_shortcut': 'F2'})
        self.assertEqual('Ctrl+Alt+C,Shift+F2', config.get('resize_canvas_shortcut'))
        self.assertEqual('F2', config.get('rename_layer_shortcut'))

    def test_every_previous_default_moves_to_the_current_one(self) -> None:
        """An unversioned file holding the old default of any changed binding loads the current default."""
        current = {key: KeyConfig().get_default(key) for key in KeyConfig.PREVIOUS_DEFAULTS}
        for key, old_values in KeyConfig.PREVIOUS_DEFAULTS.items():
            for old_value in old_values:
                with self.subTest(key=key, old_value=old_value):
                    config = self._load({key: old_value})
                    self.assertEqual(current[key], config.get(key))

    def test_custom_resize_binding_kept(self) -> None:
        """An unversioned file keeps a Resize canvas binding the user chose."""
        config = self._load({'resize_canvas_shortcut': 'Ctrl+Alt+Z'})
        self.assertEqual('Ctrl+Alt+Z', config.get('resize_canvas_shortcut'))


class KeyConfigDefaultsTest(IntraPaintTestCase):
    """The default bindings follow the editor conventions in #139."""

    def test_default_key_strings_parse_to_expected_sequences(self) -> None:
        """Conventional chords parse to the keys and modifiers they name, including the bare plus key."""
        expectations = {
            KeyConfig.SAVE_AS_SHORTCUT: [(Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier
                                          | Qt.KeyboardModifier.ShiftModifier),
                                         (Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier
                                          | Qt.KeyboardModifier.AltModifier)],
            KeyConfig.ZOOM_IN: [(Qt.Key.Key_Plus, Qt.KeyboardModifier.ShiftModifier),
                                (Qt.Key.Key_Equal, Qt.KeyboardModifier.NoModifier)],
            KeyConfig.ZOOM_OUT: [(Qt.Key.Key_Minus, Qt.KeyboardModifier.NoModifier)],
            KeyConfig.ZOOM_IN_SHORTCUT: [(Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier),
                                         (Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier
                                          | Qt.KeyboardModifier.ShiftModifier)],
            KeyConfig.PAN_VIEW_KEY: [(Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)],
            KeyConfig.RESET_VIEW_SHORTCUT: [(Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)],
            KeyConfig.ZOOM_ACTUAL_SIZE_SHORTCUT: [(Qt.Key.Key_1, Qt.KeyboardModifier.ControlModifier),
                                                  (Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier
                                                   | Qt.KeyboardModifier.AltModifier)],
            KeyConfig.MOVE_LEFT_MORE: [(Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)],
            KeyConfig.SWAP_COLORS_SHORTCUT: [(Qt.Key.Key_X, Qt.KeyboardModifier.NoModifier)],
        }
        for config_key, expected in expectations.items():
            with self.subTest(config_key=config_key):
                parsed = [get_key_with_modifiers(binding) for binding in key_alternatives(KeyConfig().get(config_key))]
                self.assertEqual(expected, parsed)

    def test_grow_and_shrink_selection_leave_the_zoom_keys(self) -> None:
        """Ctrl+= and Ctrl+- zoom, so selection resizing uses Ctrl+Alt."""
        self.assertEqual('Ctrl+Alt+=', KeyConfig().get(KeyConfig.GROW_SELECTION_SHORTCUT))
        self.assertEqual('Ctrl+Alt+-', KeyConfig().get(KeyConfig.SHRINK_SELECTION_SHORTCUT))

    def test_pan_and_speed_modifiers_are_gone(self) -> None:
        """Ctrl-drag panning and the key speed modifier no longer exist."""
        for removed in ('pan_view_modifier', 'speed_modifier'):
            with self.subTest(removed=removed):
                with self.assertRaises(KeyError):
                    KeyConfig().get(removed)

    def test_tool_keys_leave_color_keys_free(self) -> None:
        """No tool takes X or D, which swap and reset colors."""
        tool_keys = [key for key in KeyConfig().get_category_keys('Keybindings') if key.endswith('_tool_key')]
        for config_key in tool_keys:
            with self.subTest(config_key=config_key):
                for binding in key_alternatives(KeyConfig().get(config_key)):
                    self.assertNotIn(binding.upper(), ('X', 'D'))

    def test_event_matches_requires_exact_modifiers(self) -> None:
        """A key event matches a binding with the same key and modifiers, and any alternative of it counts."""
        def _event(key: Qt.Key, modifiers: Qt.KeyboardModifier) -> QKeyEvent:
            return QKeyEvent(QEvent.Type.KeyPress, key, modifiers)
        self.assertTrue(KeyConfig.event_matches(_event(Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier),
                                                KeyConfig.MOVE_LEFT_MORE))
        self.assertFalse(KeyConfig.event_matches(_event(Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier),
                                                 KeyConfig.MOVE_LEFT_MORE))
        self.assertTrue(KeyConfig.event_matches(_event(Qt.Key.Key_Equal, Qt.KeyboardModifier.NoModifier),
                                                KeyConfig.ZOOM_IN))
        self.assertTrue(KeyConfig.event_matches(_event(Qt.Key.Key_Plus, Qt.KeyboardModifier.ShiftModifier),
                                                KeyConfig.ZOOM_IN))


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
