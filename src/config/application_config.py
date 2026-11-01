"""Provides access to the user-editable application config."""
import os
from typing import Any, Optional

from PySide6.QtWidgets import QStyleFactory

from src.config.config import Config
from src.ui.theme import THEME_INK, THEME_SYSTEM
from src.util.optional_import import optional_import
from src.util.shared_constants import PROJECT_DIR, DATA_DIR, PIL_SCALING_MODES, APP_CONFIG_PATH
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


class AppConfig(Config, metaclass=Singleton):
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
        super().__init__(CONFIG_DEFINITIONS, json_path, AppConfig)

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

    # DYNAMIC PROPERTIES:
    # Generate with `python scripts/dynamic_import_typing.py src/config/application_config.py`

    ADDED_FONT_DIR: str
    ADDED_MYPAINT_BRUSH_DIR: str
    ALWAYS_INIT_METADATA_ON_SAVE: str
    ALWAYS_UPDATE_METADATA_ON_SAVE: str
    ANIMATE_OUTLINES_AND_PREVIEWS: str
    ANIMATE_SELECTION_FILL: str
    ANIMATE_SELECTION_OUTLINE: str
    BERT_MODEL_PATH: str
    BRUSH_FAVORITES: str
    CLEAR_CONTEXT_PINS_AFTER_GENERATING: str
    CLIP_MODEL_NAME: str
    DEFAULT_IMAGE_SIZE: str
    FONT_POINT_SIZE: str
    GENERATION_AREA_FOLLOW_SELECTION: str
    GENERATION_RESOLUTION_MIN_SIDE: str
    GLID_MODEL_PATH: str
    GLID_VAE_MODEL_PATH: str
    INTERROGATE_MODEL: str
    KEY_HINT_FONT_SIZE: str
    LANGUAGE: str
    LIBMYPAINT_LIBRARY_DIR: str
    MASK_BLUR: str
    MAX_EDIT_SIZE: str
    MAX_GENERATION_SIZE: str
    MAX_IMAGE_SIZE: str
    MAX_UNDO: str
    MIN_EDIT_SIZE: str
    MIN_GENERATION_SIZE: str
    OPENGL_ACCELERATION: str
    OVERLAY_SCROLL_BARS: str
    PIL_DOWNSCALE_MODE: str
    PIL_UPSCALE_MODE: str
    ROUNDED_POPUPS: str
    RULER_FONT_SIZE: str
    RULER_GENERATION_AREA_COLOR: str
    SAVED_COLORS: str
    SELECTION_COLOR: str
    SELECTION_SCREEN_ZOOMS_TO_CHANGED: str
    SHOW_OPTIONS_FULL_RESOLUTION: str
    SHOW_RULERS: str
    SHOW_RULER_HIGHLIGHTS: str
    SHOW_SELECTIONS_IN_GENERATION_OPTIONS: str
    SHOW_TOOL_CONTROL_HINTS: str
    SPEED_MODIFIER_MULTIPLIER: str
    STATIC_LOADING_INDICATOR: str
    STYLE: str
    TABLET_PRESSURE_CURVE: str
    TAB_FONT_POINT_SIZE: str
    THEME: str
    TOOLBAR_TOOL_BUTTON_COUNT: str
    USE_ERROR_HANDLER: str
    WARN_BEFORE_COLOR_LOSS: str
    WARN_BEFORE_FIXED_SIZE_SAVE: str
    WARN_BEFORE_LAYERLESS_SAVE: str
    WARN_BEFORE_RGB_SAVE: str
    WARN_BEFORE_SAVE_WITHOUT_METADATA: str
    WARN_BEFORE_WRITE_ONLY_SAVE: str
    WARN_ON_KEY_ERROR: str
    WARN_ON_LIBMYPAINT_ERROR: str
    WARN_WHEN_CROP_DELETES_LAYERS: str
    WARN_WHEN_LOCK_FORCES_LAYER_CREATE: str
