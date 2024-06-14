"""Provides access to the user-editable application config."""
from argparse import Namespace
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QStyleFactory, QMessageBox, QStyle, QApplication

from src.util.image_utils import get_standard_qt_icon

KEY_CONFIG_ERROR_TITLE = 'Warning'

KEY_CONFIG_ERROR_MESSAGE = 'Errors found in configurable key bindings:\n'

# Optional theme modules:
try:
    import qdarktheme
except ImportError:
    qdarktheme = None
try:
    import qt_material
except ImportError:
    qt_material = None
from src.config.config import Config

DEFAULT_CONFIG_PATH = 'config.json'
CONFIG_DEFINITIONS = 'resources/application_config_definitions.json'

# System-based theme/style init constants
DEFAULT_THEME_OPTIONS = ['None']
DARK_THEME_OPTIONS = ['qdarktheme_dark', 'qdarktheme_light', 'qdarktheme_auto']


class AppConfig(Config):
    _instance: Optional['AppConfig'] = None

    @staticmethod
    def instance() -> 'AppConfig':
        """Returns the shared config object instance."""
        if AppConfig._instance is None:
            AppConfig._instance = AppConfig()
        return AppConfig._instance

    def __init__(self, json_path: Optional[str] = DEFAULT_CONFIG_PATH) -> None:
        """Load existing config, or initialize from defaults.

        Parameters
        ----------
        json_path: str
            Path where config values will be saved and read. If the file does not exist, it will be created with
            default values. Any expected keys not found in the file will be added with default values. Any unexpected
            keys will be discarded.
        """
        super().__init__(CONFIG_DEFINITIONS, json_path, AppConfig)
        if AppConfig._instance is not None:
            raise RuntimeError('Do not call the AppConfig constructor, access it with AppConfig.instance()')
        self.validate_keybindings()

    def validate_keybindings(self) -> None:
        """Checks all keybindings for conflicts, and shows a warning message if any are found."""
        key_binding_options = self.get_category_keys("Keybindings")
        duplicate_map = {}
        errors = []
        valid_modifiers = ('Ctrl', 'Alt', 'Shift')
        speed_modifier_strings = ('zoom_in', 'zoom_out', 'pan', 'move', 'brush_size')
        speed_modifier = self.get(AppConfig.SPEED_MODIFIER)
        if speed_modifier != '' and speed_modifier not in valid_modifiers:
            errors.append(f'Invalid key for speed_modifier option: found {speed_modifier}, expected {valid_modifiers}')
        for key_str in key_binding_options:
            key_values = self.get(key_str).split(',')
            for key_value in key_values:
                if len(key_value) == 1:
                    key_value = key_value.upper()
                if key_value != '' and key_value not in valid_modifiers and QKeySequence(key_value)[0] == Qt.Key_unknown:
                    errors.append(f'"{key_str}" value "{key_value}" is not a recognized key')
                elif any(mod_str in key_str for mod_str in speed_modifier_strings) and speed_modifier \
                        in valid_modifiers:
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

    def _adjust_defaults(self):
        """Dynamically initialize application style and theme options based on available modules."""
        theme_options = DEFAULT_THEME_OPTIONS
        if qdarktheme is not None:
            theme_options += DARK_THEME_OPTIONS
        if qt_material is not None and hasattr(qt_material, 'list_themes'):
            theme_options += [f'qt_material_{theme}' for theme in qt_material.list_themes()]
        self.update_options(AppConfig.THEME, theme_options)
        self.update_options(AppConfig.STYLE, list(QStyleFactory.keys()))

    def apply_args(self, args: Namespace) -> None:
        """Loads expected parameters from command line arguments"""
        expected = {
            args.text: AppConfig.PROMPT,
            args.negative: AppConfig.NEGATIVE_PROMPT,
            args.num_batches: AppConfig.BATCH_COUNT,
            args.batch_size: AppConfig.BATCH_SIZE,
            args.cutn: AppConfig.CUTN
        }
        for arg_value, key in expected.items():
            if arg_value:
                self.set(key, arg_value)

    # DYNAMIC PROPERTIES:
    # Generate with `python /home/anthony/Workspace/ML/IntraPaint/scripts/dynamic_import_typing.py src/config/application_config.py`

    ANIMATE_OUTLINES: str
    BRUSH_FAVORITES: str
    BRUSH_SIZE_DECREASE: str
    BRUSH_SIZE_INCREASE: str
    BRUSH_TOOL_KEY: str
    CLEAR_SELECTION_SHORTCUT: str
    CONTROLNET_ARGS_0: str
    CONTROLNET_ARGS_1: str
    CONTROLNET_ARGS_2: str
    CONTROLNET_CONTROL_TYPES: str
    CONTROLNET_DOWNSAMPLE_RATE: str
    CONTROLNET_MODELS: str
    CONTROLNET_MODULES: str
    CONTROLNET_TILE_MODEL: str
    CONTROLNET_UPSCALING: str
    CONTROLNET_VERSION: str
    COPY_LAYER_SHORTCUT: str
    COPY_SHORTCUT: str
    CROP_TO_CONTENT_SHORTCUT: str
    CUT_SHORTCUT: str
    DEFAULT_IMAGE_SIZE: str
    DELETE_LAYER_SHORTCUT: str
    DENOISING_STRENGTH: str
    DOWNSCALE_MODE: str
    EDIT_MODE: str
    EDIT_SIZE: str
    EYEDROPPER_TOOL_KEY: str
    FONT_POINT_SIZE: str
    GENERATE_SHORTCUT: str
    GENERATION_AREA_TOOL_KEY: str
    GENERATION_SIZE: str
    GUIDANCE_SCALE: str
    INPAINT_FULL_RES: str
    INPAINT_FULL_RES_PADDING: str
    INTERROGATE_MODEL: str
    LAST_ACTIVE_TOOL: str
    LAST_BRUSH_COLOR: str
    LAST_FILE_PATH: str
    LAST_SEED: str
    LAYER_TO_IMAGE_SIZE_SHORTCUT: str
    LCM_MODE_SHORTCUT: str
    LOAD_SHORTCUT: str
    LORA_MODELS: str
    MASKED_CONTENT: str
    MASK_BLUR: str
    SELECTION_BRUSH_SIZE: str
    SELECTION_TOOL_KEY: str
    MAX_EDIT_SIZE: str
    MAX_GENERATION_SIZE: str
    MAX_UNDO: str
    MERGE_LAYER_DOWN_SHORTCUT: str
    MIN_EDIT_SIZE: str
    MIN_GENERATION_SIZE: str
    MOVE_DOWN: str
    MOVE_LAYER_DOWN_SHORTCUT: str
    MOVE_LAYER_UP_SHORTCUT: str
    MOVE_LEFT: str
    MOVE_RIGHT: str
    MOVE_UP: str
    MYPAINT_BRUSH: str
    NEW_IMAGE_SHORTCUT: str
    NEW_LAYER_SHORTCUT: str
    PAN_DOWN: str
    PAN_LEFT: str
    PAN_RIGHT: str
    PAN_UP: str
    PASTE_SHORTCUT: str
    PRESSURE_OPACITY: str
    PRESSURE_SIZE: str
    QUIT_SHORTCUT: str
    REDO_SHORTCUT: str
    RELOAD_SHORTCUT: str
    RESIZE_CANVAS_SHORTCUT: str
    RESTORE_FACES: str
    ROTATE_CCW_KEY: str
    ROTATE_CW_KEY: str
    SAMPLING_METHOD: str
    SAMPLING_STEPS: str
    SAVE_SHORTCUT: str
    SCALE_IMAGE_SHORTCUT: str
    SEED: str
    SELECT_NEXT_LAYER_SHORTCUT: str
    SELECT_PREVIOUS_LAYER_SHORTCUT: str
    SETTINGS_SHORTCUT: str
    SHOW_LAYER_MENU_SHORTCUT: str
    SHOW_ORIGINAL_IN_OPTIONS: str
    SKETCH_BRUSH_SIZE: str
    SKIP_STEPS: str
    SPEED_MODIFIER_MULTIPLIER: str
    STYLES: str
    TILING: str
    TRANSFORM_TOOL_KEY: str
    UNDO_SHORTCUT: str
    UPDATE_METADATA_SHORTCUT: str
    UPSCALE_METHOD: str
    UPSCALE_MODE: str
    ZOOM_IN: str
    ZOOM_OUT: str
    ZOOM_TOGGLE: str
