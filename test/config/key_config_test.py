"""Tests KeyConfig keybinding validation and the migration of saved key bindings."""
import json
import os
import shutil
import tempfile
from typing import Any, Callable
from unittest.mock import patch

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent

from src.config.config import Config
from src.config.key_config import CONFIG_DEFINITIONS, KeyConfig
from src.tools.base_tool import FIXED_ASPECT_HINT, BaseTool
from src.util.key_code_utils import get_key_with_modifiers
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

    def test_empty_bindings_valid(self) -> None:
        """A tool key, a menu shortcut and a modifier left empty produce no warnings, and don't conflict."""
        for config_key in (KeyConfig.DRAW_TOOL_KEY, KeyConfig.TEXT_TOOL_KEY, KeyConfig.SAVE_SHORTCUT,
                           KeyConfig.UNDO_SHORTCUT, KeyConfig.LINE_MODIFIER, KeyConfig.EYEDROPPER_OVERRIDE_MODIFIER):
            KeyConfig().set(config_key, '' if config_key.endswith('_modifier') else [])
        self.assertEqual([], _validation_errors())

    def test_duplicate_binding_reported(self) -> None:
        """Two bindings sharing a key still produce a warning."""
        KeyConfig().set(KeyConfig.TEXT_TOOL_KEY, KeyConfig().get(KeyConfig.DRAW_TOOL_KEY))
        errors = _validation_errors()
        self.assertEqual(1, len(errors))
        self.assertIn(KeyConfig().get_label(KeyConfig.DRAW_TOOL_KEY).rstrip(':'), errors[0])

    def test_binding_problems_checks_unsaved_values(self) -> None:
        """`binding_problems` checks values that aren't saved, and lists a clash under every key it involves."""
        config = KeyConfig()
        bindings = config.current_bindings()
        self.assertEqual({}, config.binding_problems(bindings))
        bindings[KeyConfig.TEXT_TOOL_KEY] = bindings[KeyConfig.DRAW_TOOL_KEY]
        problems = config.binding_problems(bindings)
        self.assertEqual({KeyConfig.TEXT_TOOL_KEY, KeyConfig.DRAW_TOOL_KEY}, set(problems))
        self.assertIn(f'"{bindings[KeyConfig.DRAW_TOOL_KEY][0]}"', problems[KeyConfig.TEXT_TOOL_KEY][0])
        self.assertIn(config.get_label(KeyConfig.DRAW_TOOL_KEY).rstrip(':'), problems[KeyConfig.TEXT_TOOL_KEY][0])
        self.assertNotIn(config.get_label(KeyConfig.TEXT_TOOL_KEY).rstrip(':'), problems[KeyConfig.TEXT_TOOL_KEY][0])
        bindings[KeyConfig.TEXT_TOOL_KEY] = ['NotAKey']
        self.assertEqual([KeyConfig.TEXT_TOOL_KEY], list(config.binding_problems(bindings)))
        bindings[KeyConfig.TEXT_TOOL_KEY] = []
        bindings[KeyConfig.LINE_MODIFIER] = 'J'
        self.assertEqual([KeyConfig.LINE_MODIFIER], list(config.binding_problems(bindings)))

    def test_repeated_key_within_one_option_is_not_a_conflict(self) -> None:
        """A key listed twice in one option's value isn't reported as clashing with itself."""
        config = KeyConfig()
        bindings = config.current_bindings()
        key = bindings[KeyConfig.DRAW_TOOL_KEY][0]
        bindings[KeyConfig.DRAW_TOOL_KEY] = [key, key.lower(), key]
        self.assertEqual({}, config.binding_problems(bindings))
        config.set(KeyConfig.DRAW_TOOL_KEY, bindings[KeyConfig.DRAW_TOOL_KEY])
        self.assertEqual([], _validation_errors(), 'Startup validation skips the repeat too')

    def test_empty_modifier_never_held(self) -> None:
        """An empty modifier binding reads as not held, whatever modifiers are down."""
        KeyConfig().set(KeyConfig.EYEDROPPER_OVERRIDE_MODIFIER, '')
        for held in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ControlModifier,
                     Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier):
            with self.subTest(held=held):
                self.assertFalse(KeyConfig.modifier_held(KeyConfig.EYEDROPPER_OVERRIDE_MODIFIER, held_modifiers=held))
                self.assertFalse(KeyConfig.modifier_held(KeyConfig.EYEDROPPER_OVERRIDE_MODIFIER, exclusive=True,
                                                         held_modifiers=held))


class _ScratchKeyConfig(Config):
    """A key config that no AppContext owns, with `KeyConfig`'s definitions and previous defaults."""
    PREVIOUS_DEFAULTS = KeyConfig.PREVIOUS_DEFAULTS

    def __init__(self, json_path: str) -> None:
        super().__init__(CONFIG_DEFINITIONS, json_path)

    def _migrations(self) -> list[Callable[[dict[str, Any]], None]]:
        return super()._migrations() + [lambda json_data: KeyConfig._migrate_binding_lists(self, json_data)]


class KeyConfigMigrationTest(IntraPaintTestCase):
    """Saved key bindings from before a default changed follow the new default, unless the user changed them."""

    def _load(self, saved: dict[str, Any]) -> _ScratchKeyConfig:
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
        self.assertEqual(['F2'], KeyConfig().get(KeyConfig.RENAME_LAYER_SHORTCUT))
        self.assertEqual(['Ctrl+Alt+C', 'Shift+F2'], KeyConfig().get(KeyConfig.RESIZE_CANVAS_SHORTCUT))

    def test_saved_old_resize_default_moves(self) -> None:
        """An unversioned file that holds the old F2 for Resize canvas loads the new default."""
        config = self._load({'resize_canvas_shortcut': 'F2'})
        self.assertEqual(['Ctrl+Alt+C', 'Shift+F2'], config.get('resize_canvas_shortcut'))
        self.assertEqual(['F2'], config.get('rename_layer_shortcut'))

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
        self.assertEqual(['Ctrl+Alt+Z'], config.get('resize_canvas_shortcut'))


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
                parsed = [get_key_with_modifiers(binding) for binding in KeyConfig().get(config_key)]
                self.assertEqual(expected, parsed)

    def test_layer_selection_shortcuts(self) -> None:
        """Layer selection follows the editor conventions: Ctrl+J duplicates, Alt+[ and Alt+] step through layers,
        Shift+Alt+[ and Shift+Alt+] extend the selection, and Ctrl+Alt+A selects every layer."""
        expectations = {
            KeyConfig.COPY_LAYER_SHORTCUT: [(Qt.Key.Key_J, Qt.KeyboardModifier.ControlModifier)],
            KeyConfig.SELECT_NEXT_LAYER_SHORTCUT: [(Qt.Key.Key_BracketLeft, Qt.KeyboardModifier.AltModifier),
                                                   (Qt.Key.Key_PageDown, Qt.KeyboardModifier.ControlModifier)],
            KeyConfig.SELECT_PREVIOUS_LAYER_SHORTCUT: [(Qt.Key.Key_BracketRight, Qt.KeyboardModifier.AltModifier),
                                                       (Qt.Key.Key_PageUp, Qt.KeyboardModifier.ControlModifier)],
            KeyConfig.EXTEND_LAYER_SELECTION_DOWN_SHORTCUT: [(Qt.Key.Key_BracketLeft, Qt.KeyboardModifier.ShiftModifier
                                                              | Qt.KeyboardModifier.AltModifier)],
            KeyConfig.EXTEND_LAYER_SELECTION_UP_SHORTCUT: [(Qt.Key.Key_BracketRight, Qt.KeyboardModifier.ShiftModifier
                                                            | Qt.KeyboardModifier.AltModifier)],
            KeyConfig.SELECT_ALL_LAYERS_SHORTCUT: [(Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier
                                                    | Qt.KeyboardModifier.AltModifier)],
        }
        for config_key, expected in expectations.items():
            with self.subTest(config_key=config_key):
                parsed = [get_key_with_modifiers(binding) for binding in KeyConfig().get(config_key)]
                self.assertEqual(expected, parsed)

    def test_grow_and_shrink_selection_leave_the_zoom_keys(self) -> None:
        """Ctrl+= and Ctrl+- zoom, so selection resizing uses Ctrl+Alt."""
        self.assertEqual(['Ctrl+Alt+='], KeyConfig().get(KeyConfig.GROW_SELECTION_SHORTCUT))
        self.assertEqual(['Ctrl+Alt+-'], KeyConfig().get(KeyConfig.SHRINK_SELECTION_SHORTCUT))

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
                for binding in KeyConfig().get(config_key):
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


class KeyConfigBindingListTest(IntraPaintTestCase):
    """Bindings are stored as lists, so the comma key can be bound."""

    _load = KeyConfigMigrationTest._load

    def test_string_bindings_migrate_to_lists(self) -> None:
        """Unversioned and version-1 files with comma-separated bindings load as lists of alternatives."""
        for version in (None, 1):
            with self.subTest(version=version):
                saved: dict[str, Any] = {'brush_tool_key': 'Shift+S,K', 'text_tool_key': '', 'zoom_in': 'F5, ,Ctrl+X',
                                         'line_modifier': 'Ctrl+Shift', 'select_tool_tab': '1'}
                if version is not None:
                    saved['config_version'] = version
                config = self._load(saved)
                self.assertEqual(['Shift+S', 'K'], config.get('brush_tool_key'))
                self.assertEqual([], config.get('text_tool_key'))
                self.assertEqual(['F5', 'Ctrl+X'], config.get('zoom_in'))
                self.assertEqual('Ctrl+Shift', config.get('line_modifier'))
                with open(config.json_path, encoding='utf-8') as file:  # type: ignore[arg-type]
                    written = json.load(file)
                self.assertEqual(2, written['config_version'])
                self.assertEqual(['Shift+S', 'K'], written['brush_tool_key'])
                self.assertEqual('Ctrl+Shift', written['line_modifier'])

    def test_stale_previous_default_is_shed(self) -> None:
        """An unversioned file holding a previous default string follows the current default after migration."""
        config = self._load({'resize_canvas_shortcut': 'F2'})
        self.assertEqual(config.get_default('resize_canvas_shortcut'), config.get('resize_canvas_shortcut'))

    def test_list_files_are_not_migrated_again(self) -> None:
        """A version-2 file keeps its list bindings, including a comma."""
        config = self._load({'config_version': 2, 'zoom_in': [',', 'Ctrl+,']})
        self.assertEqual([',', 'Ctrl+,'], config.get('zoom_in'))

    @staticmethod
    def _comma_event(modifiers: Qt.KeyboardModifier) -> QKeyEvent:
        return QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Comma, modifiers)

    def test_event_matches_comma_bindings(self) -> None:
        """A bare comma and Ctrl+comma match key events for the comma key."""
        KeyConfig().set(KeyConfig.ZOOM_IN, [','])
        KeyConfig().set(KeyConfig.ZOOM_OUT, ['Ctrl+,'])
        self.assertTrue(KeyConfig.event_matches(self._comma_event(Qt.KeyboardModifier.NoModifier), KeyConfig.ZOOM_IN))
        self.assertFalse(KeyConfig.event_matches(self._comma_event(Qt.KeyboardModifier.ControlModifier),
                                                 KeyConfig.ZOOM_IN))
        self.assertTrue(KeyConfig.event_matches(self._comma_event(Qt.KeyboardModifier.ControlModifier),
                                                KeyConfig.ZOOM_OUT))

    def test_comma_conflict_reported(self) -> None:
        """Two options bound to the comma key conflict."""
        config = KeyConfig()
        bindings = config.current_bindings()
        bindings[KeyConfig.DRAW_TOOL_KEY] = [',']
        bindings[KeyConfig.TEXT_TOOL_KEY] = [',']
        self.assertEqual({KeyConfig.DRAW_TOOL_KEY, KeyConfig.TEXT_TOOL_KEY}, set(config.binding_problems(bindings)))
        bindings[KeyConfig.TEXT_TOOL_KEY] = ['Ctrl+,']
        self.assertEqual({}, config.binding_problems(bindings))
