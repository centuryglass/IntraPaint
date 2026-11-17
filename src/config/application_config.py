"""Provides access to the user-editable application config."""
import os
from typing import Any, Optional

from PySide6.QtWidgets import QStyleFactory

from src.config.config import Config
from src.config.generated_keys import AppConfigKeys
from src.ui.theme import THEME_INK, THEME_SYSTEM
from src.util.optional_import import optional_import
from src.util.shared_constants import PROJECT_DIR, DATA_DIR, APP_CONFIG_PATH
from src.util.shared_text import PIL_SCALING_MODES
from src.util.translation import SYSTEM_LANGUAGE, available_languages, language_name
from src.util.singleton import Singleton

# Optional theme modules:
qdarktheme = optional_import('qdarktheme')
qt_material = optional_import('qt_material')

DEFAULT_CONFIG_PATH = APP_CONFIG_PATH
CONFIG_DEFINITIONS = f'{PROJECT_DIR}/resources/config/application_config_definitions.json'


# System-based theme/style init constants
DEFAULT_THEME_OPTIONS = [THEME_INK, THEME_SYSTEM]
DARK_THEME_OPTIONS = ['qdarktheme_dark', 'qdarktheme_light', 'qdarktheme_auto']


class AppConfig(AppConfigKeys, Config, metaclass=Singleton):
    """Provides access to the user-editable application config."""

    # Defaults from released versions, so installs that never changed them follow the current default:
    PREVIOUS_DEFAULTS = {
        'selection_color': ['#55ff0000'],
        'style': ['fusion'],
        'theme': ['None']
    }
    # Every install switches to the Ink theme once, when its unversioned file is migrated:
    RESET_KEYS = ('theme', 'style')

    def __init__(self, json_path: Optional[str] = DEFAULT_CONFIG_PATH) -> None:
        """Load existing config, or initialize from defaults.

        Parameters
        ----------
        json_path: str
            Path where config values will be saved and read. If the file does not exist, it will be created with
            default values. Any expected keys not found in the file load with their current default. Any unexpected
            keys will be discarded.
        """
        # Set by `_adjust_defaults`, which runs during construction:
        self._language_codes: list[str] = []
        super().__init__(CONFIG_DEFINITIONS, json_path)

    def _adjust_defaults(self):
        """Dynamically initialize application style and theme options based on available modules."""
        theme_options = list(DEFAULT_THEME_OPTIONS)
        if qdarktheme is not None:
            theme_options += DARK_THEME_OPTIONS
        if qt_material is not None and hasattr(qt_material, 'list_themes'):
            theme_options += [f'qt_material_{theme}' for theme in qt_material.list_themes()]
        self.update_options(AppConfig.THEME, theme_options)
        self.update_options(AppConfig.STYLE, list(QStyleFactory.keys()))
        self._language_codes = available_languages()
        self.update_options(AppConfig.LANGUAGE, [SYSTEM_LANGUAGE, *self._language_codes])

        # Put default user data directories in the user data dir:
        for config_key, dir_name in ((AppConfig.LIBMYPAINT_LIBRARY_DIR, 'libmypaint-lib-files'),
                                     (AppConfig.ADDED_FONT_DIR, 'fonts'),
                                     (AppConfig.ADDED_MYPAINT_BRUSH_DIR, 'mypaint-brushes')):
            current_path = self.get(config_key)
            if current_path == '':
                dir_path = os.path.join(DATA_DIR, dir_name)
                os.makedirs(dir_path, exist_ok=True)
                if os.path.isdir(dir_path):
                    self.set(config_key, dir_path)

        scaling_options = list(PIL_SCALING_MODES.keys())
        self.update_options(AppConfig.PIL_UPSCALE_MODE, scaling_options)
        self.update_options(AppConfig.PIL_DOWNSCALE_MODE, scaling_options)

    def get_option_display(self, option: Any) -> str:
        """Shows `AppConfig.LANGUAGE`'s language codes by their own names, and every other option as `Config` does."""
        if isinstance(option, str) and option in self._language_codes:
            return language_name(option)
        return super().get_option_display(option)
