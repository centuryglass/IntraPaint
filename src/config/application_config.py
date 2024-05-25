"""Provides access to the user-editable application config."""
from argparse import Namespace
from typing import Optional

from PyQt5.QtWidgets import QStyleFactory

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
