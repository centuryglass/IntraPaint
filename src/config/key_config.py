"""Provides access to the user-editable application keybinding config."""
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QMessageBox, QStyle, QApplication

from src.util.image_utils import get_standard_qt_icon
from src.config.config import Config
from src.util.key_code_utils import get_modifiers
from src.util.shared_constants import PROJECT_DIR, DATA_DIR
from src.util.singleton import Singleton


# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'config.key_config'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


DEFAULT_CONFIG_PATH = f'{DATA_DIR}/key_config.json'
CONFIG_DEFINITIONS = f'{PROJECT_DIR}/resources/config/key_config_definitions.json'

KEY_CONFIG_ERROR_TITLE = _tr('Warning')
KEY_CONFIG_ERROR_MESSAGE = _tr('Errors found in configurable key bindings:\n')
SPEED_MODIFIER_ERROR = _tr('Invalid key for speed_modifier option: found {speed_modifier}, expected {modifiers}')
NOT_A_MODIFIER_ERROR = _tr('"{key_binding_name}" should be a modifier key (Ctrl, Alt, Shift), found "{key_value}"')
UNEXPECTED_MODIFIER_ERROR = _tr('"{key_binding_name}" assigned unexpected modifier key "{key_value}", this may cause '
                                'problems')
UNKNOWN_KEY_CODE_ERROR = _tr('"{key_binding_name}" value "{key_value}" is not a recognized key')
SPEED_MODIFIER_CONFLICT_ERROR = _tr('"{key_binding_name}" is set to {key_value}, but {speed_modifier} is the speed'
                                    ' modifier'
                                    ' key. This will cause {key_str} to always operate at 10x speed.')
UNSET_KEY_ERROR = _tr('{key_binding_name} is not set')
KEY_CONFLICT_ERROR = _tr('Key "{key_str}" is shared between options {key_names}, some keys may not work.')
SPEED_MODIFIED_KEY_DESCRIPTION = _tr('{key_binding_name} (with speed modifier)')


class KeyConfig(Config, metaclass=Singleton):
    """Provides access to the user-editable application keybinding config."""

    def __init__(self, json_path: Optional[str] = DEFAULT_CONFIG_PATH) -> None:
        """Load existing config, or initialize from defaults.

        Parameters
        ----------
        json_path: str
            Path where config values will be saved and read. If the file does not exist, it will be created with
            default values. Any expected keys not found in the file will be added with default values. Any unexpected
            keys will be discarded.
        """
        super().__init__(CONFIG_DEFINITIONS, json_path, KeyConfig)
        self.validate_keybindings()

    @staticmethod
    def modifier_held(modifier_key: str, exclusive=False) -> bool:
        """Returns whether a KeyConfig modifier is held, or false if modifier key is invalid or unbound."""
        try:
            held_keys = QApplication.keyboardModifiers()
            if held_keys == Qt.KeyboardModifier.NoModifier:
                return False
            keys = KeyConfig().get_modifier(modifier_key)
            if not isinstance(keys, list):
                keys = [keys]
            for modifier in keys:
                if modifier == Qt.KeyboardModifier.NoModifier:
                    continue
                test_value = held_keys if exclusive else (modifier and held_keys)
                if test_value == modifier:
                    return True
            return False
        except (RuntimeError, KeyError, ValueError):
            return False

    def get_modifier(self, key: str) -> Qt.KeyboardModifier | list[Qt.KeyboardModifier]:
        """Returns the modifier or modifier list associated with a config value."""
        str_value = self.get(key)
        try:
            return get_modifiers(str_value)
        except RuntimeError:
            return Qt.KeyboardModifier.NoModifier

    def validate_keybindings(self) -> None:
        """Checks all keybindings for conflicts, and shows a warning message if any are found."""
        key_binding_options = self.get_category_keys('Keybindings')
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

        speed_modifier_strings = ('zoom_in', 'zoom_out', 'pan', 'move', 'brush_size')
        speed_modifier = self.get(KeyConfig.SPEED_MODIFIER)
        if speed_modifier != '' and not _is_modifier(speed_modifier):
            errors.append(SPEED_MODIFIER_ERROR.format(speed_modifier=speed_modifier, modifiers=modifiers))
        for config_key in key_binding_options:
            key_binding_name = self.get_label(config_key)
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
                if key_value != '' and key_value not in modifiers and QKeySequence(key_value)[0] == Qt.Key.Key_unknown:
                    errors.append(UNKNOWN_KEY_CODE_ERROR.format(key_binding_name=key_binding_name,
                                                                key_value=key_value))
                elif any(mod_str in config_key for mod_str in speed_modifier_strings) and speed_modifier \
                        in modifiers:
                    if speed_modifier in key_value:
                        errors.append(SPEED_MODIFIER_CONFLICT_ERROR.format(key_binding_name=key_binding_name,
                                                                           key_value=key_value,
                                                                           speed_modifier=speed_modifier))
                    else:
                        speed_value = _standardize_key_str(f'{speed_modifier}+{standardized_key}')
                        speed_key = SPEED_MODIFIED_KEY_DESCRIPTION.format(key_binding_name=key_binding_name)
                        if speed_value not in duplicate_map:
                            duplicate_map[speed_value] = [speed_key]
                        else:
                            duplicate_map[speed_value].append(speed_key)
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
                                                KeyConfig.PAN_VIEW_MODIFIER,
                                                KeyConfig.FIXED_ANGLE_MODIFIER],
                                               [KeyConfig.LINE_MODIFIER,
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
            lines = ['<li>' + err + '</li>\n' for err in errors]
            error_message = '<b>' + KEY_CONFIG_ERROR_MESSAGE + '</b><br><ul>' + ''.join(lines) + '</ul>'
            message_box = QMessageBox()
            message_box.setTextFormat(Qt.TextFormat.RichText)
            message_box.setWindowTitle(KEY_CONFIG_ERROR_TITLE)
            message_box.setText(error_message)
            message_box.setWindowIcon(get_standard_qt_icon(QStyle.StandardPixmap.SP_MessageBoxWarning, message_box))
            message_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            message_box.exec()

    # DYNAMIC PROPERTIES:
    # Generate with `python /home/anthony/Workspace/ML/IntraPaint/scripts/dynamic_import_typing.py src/config/key_config.py`

    BLUR_SHORTCUT: str
    BRIGHTNESS_CONTRAST_SHORTCUT: str
    BRUSH_SIZE_DECREASE: str
    BRUSH_SIZE_INCREASE: str
    BRUSH_TOOL_KEY: str
    CLEAR_SHORTCUT: str
    COLOR_BALANCE_SHORTCUT: str
    COPY_LAYER_SHORTCUT: str
    COPY_SHORTCUT: str
    CROP_TO_CONTENT_SHORTCUT: str
    CUT_SHORTCUT: str
    DELETE_LAYER_SHORTCUT: str
    EYEDROPPER_OVERRIDE_MODIFIER: str
    EYEDROPPER_TOOL_KEY: str
    FILL_TOOL_KEY: str
    FIXED_ANGLE_MODIFIER: str
    FIXED_ASPECT_MODIFIER: str
    GENERATE_SHORTCUT: str
    GENERATION_AREA_TOOL_KEY: str
    GENERATOR_SELECT_SHORTCUT: str
    GROW_SELECTION_SHORTCUT: str
    IMAGE_TO_LAYERS_SHORTCUT: str
    IMAGE_WINDOW_SHORTCUT: str
    INVERT_SELECTION_SHORTCUT: str
    LAYER_MIRROR_HORIZONTAL_SHORTCUT: str
    LAYER_MIRROR_VERTICAL_SHORTCUT: str
    LAYER_ROTATE_CCW_SHORTCUT: str
    LAYER_ROTATE_CW_SHORTCUT: str
    LAYER_TO_IMAGE_SIZE_SHORTCUT: str
    LCM_MODE_SHORTCUT: str
    LINE_MODIFIER: str
    LOAD_LAYERS_SHORTCUT: str
    LOAD_SHORTCUT: str
    LORA_SHORTCUT: str
    MERGE_LAYER_DOWN_SHORTCUT: str
    MOVE_DOWN: str
    MOVE_LAYER_DOWN_SHORTCUT: str
    MOVE_LAYER_TO_TOP_SHORTCUT: str
    MOVE_LAYER_UP_SHORTCUT: str
    MOVE_LEFT: str
    MOVE_RIGHT: str
    MOVE_UP: str
    NEW_IMAGE_SHORTCUT: str
    NEW_LAYER_GROUP_SHORTCUT: str
    NEW_LAYER_SHORTCUT: str
    PAN_DOWN: str
    PAN_LEFT: str
    PAN_RIGHT: str
    PAN_UP: str
    PAN_VIEW_MODIFIER: str
    PASTE_SHORTCUT: str
    POSTERIZE_SHORTCUT: str
    PROMPT_STYLE_SHORTCUT: str
    QUIT_SHORTCUT: str
    REDO_SHORTCUT: str
    RELOAD_SHORTCUT: str
    RESIZE_CANVAS_SHORTCUT: str
    ROTATE_CCW_KEY: str
    ROTATE_CW_KEY: str
    SAVE_AS_SHORTCUT: str
    SAVE_SHORTCUT: str
    SCALE_IMAGE_SHORTCUT: str
    SELECTION_FILL_TOOL_KEY: str
    SELECTION_TOOL_KEY: str
    SELECT_ALL_SHORTCUT: str
    SELECT_LAYER_CONTENT_SHORTCUT: str
    SELECT_NEXT_LAYER_SHORTCUT: str
    SELECT_NONE_SHORTCUT: str
    SELECT_PREVIOUS_LAYER_SHORTCUT: str
    SETTINGS_SHORTCUT: str
    SHAPE_SELECTION_TOOL_KEY: str
    SHARPEN_SHORTCUT: str
    SHOW_LAYER_MENU_SHORTCUT: str
    SHRINK_SELECTION_SHORTCUT: str
    SPEED_MODIFIER: str
    TRANSFORM_TOOL_KEY: str
    UNDO_SHORTCUT: str
    UPDATE_METADATA_SHORTCUT: str
    ZOOM_IN: str
    ZOOM_OUT: str
    ZOOM_TOGGLE: str
    