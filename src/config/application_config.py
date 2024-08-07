"""Provides access to the user-editable application config."""
from argparse import Namespace
from typing import Optional

from PyQt6.QtWidgets import QStyleFactory

from src.config.config import Config
from src.util.optional_import import optional_import
from src.util.shared_constants import PIL_SCALING_MODES, PROJECT_DIR, DATA_DIR
from src.util.singleton import Singleton

# Optional theme modules:
qdarktheme = optional_import('qdarktheme')
qt_material = optional_import('qt_material')

DEFAULT_CONFIG_PATH = f'{DATA_DIR}/config.json'
CONFIG_DEFINITIONS = f'{PROJECT_DIR}/resources/config/application_config_definitions.json'


# System-based theme/style init constants
DEFAULT_THEME_OPTIONS = ['None']
DARK_THEME_OPTIONS = ['qdarktheme_dark', 'qdarktheme_light', 'qdarktheme_auto']


class AppConfig(Config, metaclass=Singleton):
    """Provides access to the user-editable application config."""

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

        scaling_options = PIL_SCALING_MODES.keys()
        self.update_options(AppConfig.UPSCALE_MODE, scaling_options)
        self.update_options(AppConfig.DOWNSCALE_MODE, scaling_options)

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
    AUTO_MOVE_TABS: str
    BATCH_COUNT: str
    BATCH_SIZE: str
    BRUSH_FAVORITES: str
    CONTROLNET_ARGS_0: str
    CONTROLNET_ARGS_1: str
    CONTROLNET_ARGS_2: str
    CONTROLNET_DOWNSAMPLE_RATE: str
    CONTROLNET_TILE_MODEL: str
    CONTROLNET_UPSCALING: str
    CUTN: str
    DEFAULT_IMAGE_SIZE: str
    DENOISING_STRENGTH: str
    DOWNSCALE_MODE: str
    EDIT_MODE: str
    EDIT_SIZE: str
    FONT_POINT_SIZE: str
    GENERATION_SIZE: str
    GENERATION_TAB_BAR: str
    GUIDANCE_SCALE: str
    INPAINT_FULL_RES: str
    INPAINT_FULL_RES_PADDING: str
    INTERROGATE_MODEL: str
    MASKED_CONTENT: str
    MASK_BLUR: str
    MAX_EDIT_SIZE: str
    MAX_GENERATION_SIZE: str
    MAX_UNDO: str
    MIN_EDIT_SIZE: str
    MIN_GENERATION_SIZE: str
    MYPAINT_BRUSH: str
    NEGATIVE_PROMPT: str
    OPENGL_ACCELERATION: str
    PROMPT: str
    RESTORE_FACES: str
    SAMPLING_METHOD: str
    SAMPLING_STEPS: str
    SEED: str
    SELECTION_BRUSH_SIZE: str
    SELECTION_COLOR: str
    SELECTION_SCREEN_ZOOMS_TO_CHANGED: str
    SHOW_OPTIONS_FULL_RESOLUTION: str
    SHOW_SELECTIONS_IN_GENERATION_OPTIONS: str
    SKETCH_BRUSH_SIZE: str
    SKIP_STEPS: str
    SPEED_MODIFIER_MULTIPLIER: str
    STYLE: str
    THEME: str
    TILING: str
    TOOL_TAB_BAR: str
    UNDO_MERGE_INTERVAL: str
    UPSCALE_METHOD: str
    UPSCALE_MODE: str
    USE_ERROR_HANDLER: str
    WARN_BEFORE_LAYERLESS_SAVE: str
    WARN_ON_KEY_ERROR: str
