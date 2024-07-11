"""Provides access to the user-editable application keybinding config."""
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QMessageBox, QStyle, QApplication

from src.util.image_utils import get_standard_qt_icon
from src.config.config import Config
from src.util.singleton import Singleton

DEFAULT_CONFIG_PATH = 'key_config.json'
CONFIG_DEFINITIONS = 'resources/config/key_config_definitions.json'

KEY_CONFIG_ERROR_TITLE = 'Warning'
KEY_CONFIG_ERROR_MESSAGE = 'Errors found in configurable key bindings:\n'


class KeyConfig(Config, metaclass=Singleton):

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

    def validate_keybindings(self) -> None:
        """Checks all keybindings for conflicts, and shows a warning message if any are found."""
        key_binding_options = self.get_category_keys('Keybindings')
        duplicate_map = {}
        errors = []
        modifiers = ('Ctrl', 'Alt', 'Shift')
        speed_modifier_strings = ('zoom_in', 'zoom_out', 'pan', 'move', 'brush_size')
        speed_modifier = self.get(KeyConfig.SPEED_MODIFIER)
        if speed_modifier != '' and speed_modifier not in modifiers:
            errors.append(f'Invalid key for speed_modifier option: found {speed_modifier}, expected {modifiers}')
        for key_str in key_binding_options:
            key_values = self.get(key_str).split(',')
            for key_value in key_values:
                if len(key_value) == 1:
                    key_value = key_value.upper()
                if key_value != '' and key_value not in modifiers and QKeySequence(key_value)[0] == Qt.Key_unknown:
                    errors.append(f'"{key_str}" value "{key_value}" is not a recognized key')
                elif any(mod_str in key_str for mod_str in speed_modifier_strings) and speed_modifier \
                        in modifiers:
                    if speed_modifier in key_value:
                        errors.append(f'"{key_str}" is set to {key_value}, but {speed_modifier} is the speed modifier'
                                      f' key. This will cause {key_str} to always operate at 10x speed.')
                    else:
                        speed_value = f'{speed_modifier}+{key_value}'
                        speed_value = QKeySequence(speed_value).toString()  # Make sure modifiers are consistent
                        speed_key = f'{key_str} (with speed modifier)'
                        if speed_value not in duplicate_map:
                            duplicate_map[speed_value] = [speed_key]
                        else:
                            duplicate_map[speed_value].append(speed_key)
                if '+' in key_value:
                    key_value = QKeySequence(key_value).toString()  # Make sure modifiers are consistent
                if len(key_value) == 0:
                    errors.append(f'{key_str} is not set.')
                elif key_value not in duplicate_map:
                    duplicate_map[key_value] = [key_str]
                else:
                    duplicate_map[key_value].append(key_str)
        for key_binding, config_keys in duplicate_map.items():
            if len(config_keys) > 1:
                errors.append(f'Key "{key_binding}" is shared between options {config_keys}, some keys may not work.')
        if len(errors) > 0 and QApplication.instance() is not None:
            # Error messages can be fairly long, apply HTML to make them a bit more readable.
            lines = ['<li>' + err + '</li>\n' for err in errors]
            error_message = '<b>' + KEY_CONFIG_ERROR_MESSAGE + '</b><br><ul>' + ''.join(lines) + '</ul>'
            message_box = QMessageBox()
            message_box.setTextFormat(Qt.TextFormat.RichText)
            message_box.setWindowTitle(KEY_CONFIG_ERROR_TITLE)
            message_box.setText(error_message)
            message_box.setWindowIcon(get_standard_qt_icon(QStyle.SP_MessageBoxWarning, message_box))
            message_box.setStandardButtons(QMessageBox.Ok)
            message_box.exec()

    # DYNAMIC PROPERTIES:
    # Generate with `python /home/anthony/Workspace/ML/IntraPaint/scripts/dynamic_import_typing.py src/config/key_config.py`

    BLUR_SHORTCUT: str
    BRIGHTNESS_CONTRAST_SHORTCUT: str
    BRUSH_SIZE_DECREASE: str
    BRUSH_SIZE_INCREASE: str
    BRUSH_TOOL_KEY: str
    COLOR_BALANCE_SHORTCUT: str
    COPY_LAYER_SHORTCUT: str
    COPY_SHORTCUT: str
    CROP_TO_CONTENT_SHORTCUT: str
    CUT_SHORTCUT: str
    DELETE_LAYER_SHORTCUT: str
    EYEDROPPER_TOOL_KEY: str
    FILL_TOOL_KEY: str
    GENERATE_SHORTCUT: str
    GENERATION_AREA_TOOL_KEY: str
    GROW_SELECTION_SHORTCUT: str
    IMAGE_TO_LAYERS_SHORTCUT: str
    IMAGE_WINDOW_SHORTCUT: str
    INVERT_SELECTION_SHORTCUT: str
    LAYER_TO_IMAGE_SIZE_SHORTCUT: str
    LCM_MODE_SHORTCUT: str
    LOAD_LAYERS_SHORTCUT: str
    LOAD_SHORTCUT: str
    LORA_SHORTCUT: str
    MERGE_LAYER_DOWN_SHORTCUT: str
    MOVE_DOWN: str
    MOVE_LAYER_DOWN_SHORTCUT: str
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