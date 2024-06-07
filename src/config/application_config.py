"""Provides access to the user-editable application config."""
from argparse import Namespace
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QStyleFactory, QMessageBox, QStyle

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
            key_value = self.get(key_str)
            if key_value != '' and QKeySequence(key_value)[0] == Qt.Key_unknown:
                errors.append(f'"{key_str}" value "{key_value}" is not a recognized key')
            elif any(mod_str in key_str for mod_str in speed_modifier_strings) and speed_modifier in valid_modifiers:
                if speed_modifier in key_value:
                    errors.append(f'"{key_str}" is set to {key_value}, but {speed_modifier} is the speed modifier key.'
                                  f' This will cause {key_str} to always operate at 10x speed.')
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
        if len(errors) > 0:
            # Error messages can be fairly long, apply HTML to make them a bit more readable.
            lines = ['<li>' + err + '</li>\n' for err in errors]
            error_message = '<b>' + KEY_CONFIG_ERROR_MESSAGE + '</b><br><ul>' + ''.join(lines) + '</ul>'
            message_box = QMessageBox()
            message_box.setTextFormat(Qt.TextFormat.RichText)
            message_box.setWindowTitle(KEY_CONFIG_ERROR_TITLE)
            message_box.setText(error_message)
            message_box.setWindowIcon(message_box.style().standardIcon(QStyle.SP_MessageBoxWarning))
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
