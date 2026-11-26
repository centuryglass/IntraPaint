"""Provides access to the user-editable application keybinding config."""
import logging
from typing import Any, Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QKeyEvent
from PySide6.QtWidgets import QApplication

from src.app_context import AppService
from src.config.application_config import AppConfig
from src.config.config import Config
from src.config.generated_keys import KeyConfigKeys
from src.ui.modal.modal_utils import show_warning_dialog
from src.util.key_code_utils import get_modifiers, get_key_with_modifiers
from src.util.parameter import TYPE_LIST
from src.util.rich_text import escape_rich_text, rich_text_list
from src.util.shared_constants import PROJECT_DIR, DATA_DIR

logger = logging.getLogger(__name__)


# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'config.key_config'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


DEFAULT_CONFIG_PATH = f'{DATA_DIR}/key_config.json'
CONFIG_DEFINITIONS = f'{PROJECT_DIR}/resources/config/key_config_definitions.json'

KEY_CONFIG_ERROR_TITLE = _tr('Warning')
KEY_CONFIG_ERROR_MESSAGE = _tr('Errors found in configurable key bindings:\n')
NOT_A_MODIFIER_ERROR = _tr('"{key_binding_name}" should be a modifier key (Ctrl, Alt, Shift), found "{key_value}"')
UNEXPECTED_MODIFIER_ERROR = _tr('"{key_binding_name}" assigned unexpected modifier key "{key_value}", this may cause '
                                'problems')
UNKNOWN_KEY_CODE_ERROR = _tr('"{key_binding_name}" value "{key_value}" is not a recognized key')
KEY_CONFLICT_ERROR = _tr('Key "{key_str}" is shared between options {key_names}, some keys may not work.')
KEY_ALSO_BOUND_ERROR = _tr('"{key_str}" is also bound to: {key_names}')


# Config keys that set the brush opacity directly, mapped to the opacity each sets:
BRUSH_OPACITY_PRESETS = {f'brush_opacity_{percent}': percent / 100 for percent in range(10, 101, 10)}


class KeyConfig(KeyConfigKeys, Config, metaclass=AppService):
    """Provides access to the user-editable application keybinding config."""

    # Defaults from released versions, so installs that never changed them follow the current default. These are
    # version-0 saved values, so bindings are comma-separated strings: `_migrate_unversioned` runs before
    # `_migrate_binding_lists`.
    PREVIOUS_DEFAULTS = {
        'draw_tool_key': ['D'],
        'generation_area_tool_key': ['G'],
        'previous_generation_frame_key': ['Shift+G'],
        'eyedropper_tool_key': ['C'],
        'clone_stamp_tool_key': ['N'],
        'smudge_tool_key': ['M'],
        'filter_tool_key': ['I'],
        'text_tool_key': ['X'],
        'transform_tool_key': ['T'],
        'selection_brush_tool_key': ['S'],
        'selection_fill_tool_key': ['A'],
        'shape_selection_tool_key': ['R'],
        'shape_tool_key': ['Shift+S'],
        'tool_action_hotkey': ['q'],
        'toggle_selection_shape_hotkey': [''],
        'zoom_in': ['PgUp'],
        'zoom_out': ['PgDown'],
        'select_tool_tab': ['1'],
        'select_generator_tab': ['2'],
        'select_ControlNet_tab': ['3'],
        'load_layers_shortcut': ['Ctrl+Shift+O'],
        'save_as_shortcut': ['Ctrl+Alt+S'],
        'reload_shortcut': ['F5'],
        'swap_colors_shortcut': ['Shift+X'],
        'reset_colors_shortcut': ['Shift+D'],
        'settings_shortcut': ['F9'],
        'zoom_in_shortcut': ['Ctrl+Shift+='],
        'zoom_out_shortcut': ['Ctrl+Shift+-'],
        'reset_view_shortcut': ['Ctrl+Alt+0'],
        'zoom_to_gen_area_shortcut': ['Ctrl+Alt+Z'],
        'toggle_rulers_shortcut': ['Ctrl+Alt+Shift+R'],
        'generator_select_shortcut': ['F11'],
        'resize_canvas_shortcut': ['F2', 'Shift+F2'],
        'scale_image_shortcut': ['F3'],
        'crop_image_shortcut': ['Ctrl+Alt+C'],
        'update_metadata_shortcut': ['Ctrl+Alt+D'],
        'restore_choices_shortcut': ['Ctrl+G'],
        'invert_selection_shortcut': ['Ctrl+I'],
        'grow_selection_shortcut': ['Ctrl+='],
        'shrink_selection_shortcut': ['Ctrl+-'],
        'select_previous_layer_shortcut': ['Ctrl+PgUp'],
        'select_next_layer_shortcut': ['Ctrl+PgDown'],
        'move_layer_up_shortcut': ['Ctrl+Home'],
        'move_layer_down_shortcut': ['Ctrl+End'],
        'move_layer_to_top_shortcut': ['Ctrl+Shift+Home'],
        'copy_layer_shortcut': ['Ctrl+Shift+C', 'Ctrl+J,Ctrl+Shift+C'],
        'delete_layer_shortcut': ['Ctrl+Shift+D'],
        'merge_layer_down_shortcut': ['Ctrl+Shift+M'],
        'merge_all_visible_shortcut': ['Ctrl+Shift+Alt+M'],
        'layer_to_image_size_shortcut': ['Ctrl+Shift+I'],
        'crop_layer_to_selection_shortcut': ['Ctrl+Shift+E'],
        'color_balance_shortcut': ['Ctrl+1'],
        'saturation_shortcut': ['Ctrl+6'],
        'invert_shortcut': ['Ctrl+7'],
    }

    def __init__(self, json_path: Optional[str] = DEFAULT_CONFIG_PATH) -> None:
        """Load existing config, or initialize from defaults.

        Parameters
        ----------
        json_path: str
            Path where config values will be saved and read. If the file does not exist, it will be created with
            default values. Any expected keys not found in the file load with their current default. Any unexpected
            keys will be discarded.
        """
        super().__init__(CONFIG_DEFINITIONS, json_path)
        self.validate_keybindings()

    def _migrations(self) -> list[Callable[[dict[str, Any]], None]]:
        return super()._migrations() + [self._migrate_binding_lists]

    def _migrate_binding_lists(self, json_data: dict[str, Any]) -> None:
        """Migration from version 1 to 2: converts comma-separated binding strings to lists of alternatives.

        Earlier versions couldn't store a literal comma, so every comma in a saved string is a separator.
        """
        for key, entry in self._entries.items():
            if entry.type_name == TYPE_LIST and isinstance(json_data.get(key), str):
                json_data[key] = [alternative.strip() for alternative in json_data[key].split(',')
                                  if alternative.strip() != '']

    @staticmethod
    def modifier_held(modifier_key: str, exclusive=False,
                      held_modifiers: Optional[Qt.KeyboardModifier] = None) -> bool:
        """Returns whether a KeyConfig modifier is held, or False if the modifier binding is invalid or empty."""
        try:
            if held_modifiers is None:
                held_modifiers = QApplication.keyboardModifiers()
            if held_modifiers == Qt.KeyboardModifier.NoModifier:
                return False
            keys = KeyConfig().get_modifier(modifier_key)
            if not isinstance(keys, list):
                keys = [keys]
            for modifier in keys:
                if modifier == Qt.KeyboardModifier.NoModifier:
                    continue
                test_value = held_modifiers if exclusive else (modifier & held_modifiers)
                if test_value == modifier:
                    return True
            return False
        except (RuntimeError, KeyError, ValueError):
            return False

    @staticmethod
    def event_matches(event: QKeyEvent, config_key: str) -> bool:
        """Returns whether a key event is the key and exact modifiers of any alternative bound to a config key."""
        event_modifiers = event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier
        for alternative in KeyConfig().get(config_key):
            try:
                key, modifiers = get_key_with_modifiers(alternative)
            except ValueError:
                continue
            if key is not None and key == event.key() and modifiers == event_modifiers:
                return True
        return False

    def get_modifier(self, key: str) -> Qt.KeyboardModifier | list[Qt.KeyboardModifier]:
        """Returns the modifier or modifier list associated with a config value.

        An empty binding returns `Qt.KeyboardModifier.NoModifier`, which means disabled, never always held. A caller
        that reads this directly instead of using `modifier_held` checks for `NoModifier` itself.
        """
        str_value = self.get(key)
        try:
            return get_modifiers(str_value)
        except RuntimeError as err:
            logger.error(f'get_modifier error: key={key} value={str_value} err={err}')
            return Qt.KeyboardModifier.NoModifier

    def validate_keybindings(self) -> None:
        """Checks all keybindings for conflicts, and shows a warning message if any are found.

        Any binding may be empty, which leaves its action unbound. Empty values are skipped, so they never conflict.
        """
        errors = [message for _keys, message, _shared in self._check_bindings(self.current_bindings())]
        if len(errors) > 0 and QApplication.instance() is not None:
            # Error messages can be fairly long, apply HTML to make them a bit more readable.
            # AppConfig explicit initialization is required if running the dynamic import script, otherwise
            # WARN_ON_KEY_ERROR won't be present and any key errors will cause an unexplained failure.
            AppConfig()
            error_message = (f'<b>{escape_rich_text(KEY_CONFIG_ERROR_MESSAGE.strip())}</b>'
                             + rich_text_list(errors))
            show_warning_dialog(None, KEY_CONFIG_ERROR_TITLE, error_message, AppConfig.WARN_ON_KEY_ERROR)

    def current_bindings(self) -> dict[str, list[str] | str]:
        """Returns the saved value of every keybinding and menu shortcut, by config key."""
        return {key: self.get(key)
                for key in self.get_category_keys('Keybindings') + self.get_category_keys('Menu Shortcuts')}

    def binding_problems(self, bindings: dict[str, list[str] | str]) -> dict[str, list[str]]:
        """Checks a set of keybinding values, and returns the problem messages found for each config key.

        `bindings` maps config keys to values: a list of alternative bindings, or a modifier string. It may hold
        unsaved values from the settings window. A conflict is listed under every key it involves, naming the other
        options that share the key. These are the checks `validate_keybindings` runs at startup.
        """
        problems: dict[str, list[str]] = {}
        for config_keys, message, conflict_key in self._check_bindings(bindings):
            for config_key in config_keys:
                if conflict_key is not None:
                    others = ', '.join(f'"{self._binding_name(key)}"' for key in config_keys if key != config_key)
                    message = KEY_ALSO_BOUND_ERROR.format(key_str=conflict_key, key_names=others)
                problems.setdefault(config_key, []).append(message)
        return problems

    def _binding_name(self, config_key: str) -> str:
        """Returns a keybinding's label without the trailing colon it has as a row label."""
        return self.get_label(config_key).strip().rstrip(':')

    def _check_bindings(self, bindings: dict[str, list[str] | str]) -> list[tuple[list[str], str, Optional[str]]]:
        """Returns (config keys involved, message, shared key or None) for each problem found in keybinding values.

        The shared key is set only for conflicts between options. A key repeated within one option isn't a conflict.
        """
        duplicate_map: dict[str, list[str]] = {}
        errors: list[tuple[list[str], str, Optional[str]]] = []
        modifiers = ('Ctrl', 'Alt', 'Shift')

        def _standardize_key_str(base_key_str: str) -> str:
            if len(base_key_str) == 1:
                return base_key_str.upper()
            if base_key_str.lower() == 'ctrl':
                return 'Ctrl'  # Special case: QKeySequence doesn't work with Ctrl unless combined with another key.
            return QKeySequence(base_key_str).toString()

        def _is_modifier(tested_key_str: str) -> bool:
            tested_key_str = _standardize_key_str(tested_key_str)
            if tested_key_str in modifiers:
                return True
            tested_key_str = QKeySequence(tested_key_str).toString()  # Make sure modifier case is consistent
            if '+' in tested_key_str and tested_key_str != '+':
                key_list = tested_key_str.split('+')
                for key in key_list:
                    if key not in modifiers:
                        return False
                return True
            return False

        for config_key, value in bindings.items():
            key_binding_name = self._binding_name(config_key)
            alternatives = [value] if isinstance(value, str) and value else [] if isinstance(value, str) else value
            for key_value in alternatives:
                if key_value == '':
                    continue
                standardized_key = _standardize_key_str(key_value)
                if config_key.endswith('_modifier'):
                    if not _is_modifier(standardized_key):
                        errors.append(([config_key], NOT_A_MODIFIER_ERROR.format(key_binding_name=key_binding_name,
                                                                                 key_value=key_value), None))
                else:
                    if _is_modifier(standardized_key):
                        errors.append(([config_key], UNEXPECTED_MODIFIER_ERROR.format(
                            key_binding_name=key_binding_name, key_value=key_value), None))
                # noinspection PyUnresolvedReferences
                if key_value not in modifiers and QKeySequence(key_value)[0] == Qt.Key.Key_unknown:
                    errors.append(([config_key], UNKNOWN_KEY_CODE_ERROR.format(key_binding_name=key_binding_name,
                                                                               key_value=key_value), None))
                key_owners = duplicate_map.setdefault(standardized_key, [])
                if config_key not in key_owners:
                    key_owners.append(config_key)
        for key_str, config_keys in duplicate_map.items():
            if len(config_keys) > 1:
                key_names = ', '.join(f'"{self._binding_name(key)}"' for key in config_keys)
                if key_str in modifiers:
                    modifier_conflict_lists = [[KeyConfig.LINE_MODIFIER,
                                                KeyConfig.FIXED_ANGLE_MODIFIER,
                                                KeyConfig.EYEDROPPER_OVERRIDE_MODIFIER]]
                    for conflict_list in modifier_conflict_lists:
                        conflicting = [mod_key for mod_key in config_keys if mod_key in conflict_list]
                        if len(conflicting) > 1:
                            conflict_names = ', '.join(f'"{self._binding_name(key)}"' for key in conflicting)
                            errors.append((conflicting, KEY_CONFLICT_ERROR.format(key_str=key_str,
                                                                                   key_names=conflict_names), key_str))
                else:
                    errors.append((config_keys, KEY_CONFLICT_ERROR.format(key_str=key_str, key_names=key_names),
                                   key_str))
        return errors
