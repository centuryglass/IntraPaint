"""Provides access to the user-editable application keybinding config."""
import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QKeyEvent
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.config import Config
from src.config.generated_keys import KeyConfigKeys
from src.ui.modal.modal_utils import show_warning_dialog
from src.util.key_code_utils import get_modifiers, get_key_with_modifiers, key_alternatives
from src.util.shared_constants import PROJECT_DIR, DATA_DIR
from src.util.singleton import Singleton

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
UNSET_KEY_ERROR = _tr('{key_binding_name} is not set')
KEY_CONFLICT_ERROR = _tr('Key "{key_str}" is shared between options {key_names}, some keys may not work.')


# Config keys that set the brush opacity directly, mapped to the opacity each sets:
BRUSH_OPACITY_PRESETS = {f'brush_opacity_{percent}': percent / 100 for percent in range(10, 101, 10)}

# Bindings that may be left empty. Each one with an empty default must be listed, or startup warns that it is unset.
OPTIONAL_KEYS = ('toggle_sample_merged_hotkey', 'toggle_selection_shape_hotkey', 'report_bug_shortcut',
                 'release_notes_shortcut', 'about_shortcut', 'about_qt_shortcut', 'image_flip_horizontal_shortcut',
                 'image_flip_vertical_shortcut', 'image_rotate_cw_shortcut', 'image_rotate_ccw_shortcut',
                 'image_rotate_180_shortcut')


class KeyConfig(KeyConfigKeys, Config, metaclass=Singleton):
    """Provides access to the user-editable application keybinding config."""

    # Defaults from released versions, so installs that never changed them follow the current default:
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
        'copy_layer_shortcut': ['Ctrl+Shift+C'],
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

    @staticmethod
    def modifier_held(modifier_key: str, exclusive=False,
                      held_modifiers: Optional[Qt.KeyboardModifier] = None) -> bool:
        """Returns whether a KeyConfig modifier is held, or false if modifier key is invalid or unbound."""
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
        for alternative in key_alternatives(KeyConfig().get(config_key)):
            try:
                key, modifiers = get_key_with_modifiers(alternative)
            except ValueError:
                continue
            if key is not None and key == event.key() and modifiers == event_modifiers:
                return True
        return False

    def get_modifier(self, key: str) -> Qt.KeyboardModifier | list[Qt.KeyboardModifier]:
        """Returns the modifier or modifier list associated with a config value."""
        str_value = self.get(key)
        try:
            return get_modifiers(str_value)
        except RuntimeError as err:
            logger.error(f'get_modifier error: key={key} value={str_value} err={err}')
            return Qt.KeyboardModifier.NoModifier

    def validate_keybindings(self) -> None:
        """Checks all keybindings for conflicts, and shows a warning message if any are found."""
        key_binding_options = self.get_category_keys('Keybindings') + self.get_category_keys('Menu Shortcuts')
        duplicate_map = {}
        errors = []
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

        for config_key in key_binding_options:
            key_binding_name = self.get_label(config_key)
            if config_key in OPTIONAL_KEYS and self.get(config_key) == '':
                continue
            key_values = self.get(config_key).split(',')
            for key_value in key_values:
                standardized_key = _standardize_key_str(key_value)
                if config_key.endswith('_modifier'):
                    if not _is_modifier(standardized_key):
                        errors.append(NOT_A_MODIFIER_ERROR.format(key_binding_name=key_binding_name,
                                                                  key_value=key_value))
                else:
                    if _is_modifier(standardized_key):
                        errors.append(UNEXPECTED_MODIFIER_ERROR.format(key_binding_name=key_binding_name,
                                                                       key_value=key_value))
                # noinspection PyUnresolvedReferences
                if key_value != '' and key_value not in modifiers and QKeySequence(key_value)[0] == Qt.Key.Key_unknown:
                    errors.append(UNKNOWN_KEY_CODE_ERROR.format(key_binding_name=key_binding_name,
                                                                key_value=key_value))
                if len(key_value) == 0:
                    errors.append(UNSET_KEY_ERROR.format(key_binding_name=key_binding_name))
                elif standardized_key not in duplicate_map:
                    duplicate_map[standardized_key] = [config_key]
                else:
                    duplicate_map[standardized_key].append(config_key)
        for key_str, config_keys in duplicate_map.items():
            if len(config_keys) > 1:
                key_names = [self.get_label(key) for key in config_keys]
                if key_str in modifiers:
                    modifier_conflict_lists = [[KeyConfig.LINE_MODIFIER,
                                                KeyConfig.FIXED_ANGLE_MODIFIER,
                                                KeyConfig.EYEDROPPER_OVERRIDE_MODIFIER]]
                    for conflict_list in modifier_conflict_lists:
                        conflict_key_count = len([mod_key for mod_key in conflict_list if mod_key in config_keys])
                        if conflict_key_count > 1:
                            errors.append(KEY_CONFLICT_ERROR.format(key_str=key_str, key_names=key_names))
                else:
                    errors.append(KEY_CONFLICT_ERROR.format(key_str=key_str, key_names=key_names))
        if len(errors) > 0 and QApplication.instance() is not None:
            # Error messages can be fairly long, apply HTML to make them a bit more readable.
            # AppConfig explicit initialization is required if running the dynamic import script, otherwise
            # WARN_ON_KEY_ERROR won't be present and any key errors will cause an unexplained failure.
            AppConfig()
            lines = ['<li>' + err + '</li>\n' for err in errors]
            error_message = '<b>' + KEY_CONFIG_ERROR_MESSAGE + '</b><br><ul>' + ''.join(lines) + '</ul>'
            show_warning_dialog(None, KEY_CONFIG_ERROR_TITLE, error_message, AppConfig.WARN_ON_KEY_ERROR)
