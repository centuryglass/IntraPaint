"""Use the Config module's data sharing capabilities to cache temporary values."""
from argparse import Namespace

from PySide6.QtCore import QRect, QTimer
from PySide6.QtWidgets import QWidget, QApplication

from src.config.config import Config
from src.util.shared_constants import PROJECT_DIR, DATA_DIR
from src.util.singleton import Singleton
from src.util.visual.display_size import get_screen_bounds

CONFIG_DEFINITIONS = f'{PROJECT_DIR}/resources/config/cache_value_definitions.json'
DEFAULT_FILE_PATH = f'{DATA_DIR}/.cache.json'
GEOMETRY_CHECK_INTERVAL = 100

# The QCoreApplication.translate context for strings in this file
TR_ID = 'config.cache'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


SCALING_OPTION_NONE = _tr('None')


class Cache(Config, metaclass=Singleton):
    """Use the Config module's data sharing capabilities to cache temporary values."""

    def __init__(self, json_path: str = DEFAULT_FILE_PATH) -> None:
        """Initialize the cache, registering expected value types."""
        super().__init__(CONFIG_DEFINITIONS, json_path, Cache)
        self._geometry_timer = QTimer()
        self._geometry_timer.setInterval(GEOMETRY_CHECK_INTERVAL)
        self._geometry_timer.timeout.connect(self._check_bounds)
        self._final_bounds: dict[QWidget, QRect] = {}
        self._last_bounds: dict[QWidget, QRect] = {}

    def apply_args(self, args: Namespace) -> None:
        """Loads expected parameters from command line arguments"""
        expected = {
            args.text: Cache.PROMPT,
            args.negative: Cache.NEGATIVE_PROMPT,
            args.num_batches: Cache.BATCH_COUNT,
            args.batch_size: Cache.BATCH_SIZE,
            args.cutn: Cache.CUTN
        }
        for arg_value, key in expected.items():
            if arg_value:
                self.set(key, arg_value)

    def save_bounds(self, key: str, widget: QWidget) -> None:
        """Save a widget's geometry to the cache.  If waiting to load bounds for the same widget the new bounds will
           not be saved, since they are about to be replaced anyway."""
        if widget not in self._last_bounds:  # Don't update if waiting to apply previous bounds
            bounds = widget.geometry()
            cache_str = f'{bounds.x()},{bounds.y()},{bounds.width()},{bounds.height()}'
            self.set(key, cache_str)

    def load_bounds(self, key: str, widget: QWidget) -> bool:
        """Load widget bounds from the cache, returning whether loading succeeded.  Widget bounds will be applied once
           widget geometry has remained stable for 100ms, to avoid cases where bounds are immediately overridden by
           initial placement. """
        try:
            bounds = QRect(*(int(param) for param in self.get(key).split(',')))
            screen_bounds = get_screen_bounds(default_to_primary=False, alt_test_bounds=bounds)
            if not screen_bounds.isNull():
                bounds = bounds.intersected(screen_bounds)
            if bounds == screen_bounds:
                widget.showMaximized()
            self._final_bounds[widget] = bounds
            self._last_bounds[widget] = QRect(widget.geometry())
            if not self._geometry_timer.isActive():
                self._geometry_timer.start()
            return True
        except (ValueError, TypeError):
            return False

    def _check_bounds(self) -> None:
        to_clear = []
        to_update = []
        for widget, bounds in self._last_bounds.items():
            if widget.geometry() == bounds:
                to_clear.append(widget)
            else:
                to_update.append(widget)
        for widget in to_clear:
            widget.setGeometry(self._final_bounds[widget])
            del self._final_bounds[widget]
            del self._last_bounds[widget]
        for widget in to_update:
            self._last_bounds[widget] = QRect(widget.geometry())
        if len(self._last_bounds) == 0:
            self._geometry_timer.stop()

    # DYNAMIC PROPERTIES:
    # Generate with `python /home/anthony/Workspace/ML/IntraPaint/scripts/dynamic_import_typing.py src/config/cache.py`

    BATCH_COUNT: str
    BATCH_SIZE: str
    CANVAS_RESIZE_CROP_LAYERS: str
    CANVAS_RESIZE_LAYER_MODE: str
    CLIP_SKIP: str
    CLONE_STAMP_TOOL_ANTIALIAS: str
    CLONE_STAMP_TOOL_BRUSH_SIZE: str
    CLONE_STAMP_TOOL_HARDNESS: str
    CLONE_STAMP_TOOL_OPACITY: str
    CLONE_STAMP_TOOL_PRESSURE_HARDNESS: str
    CLONE_STAMP_TOOL_PRESSURE_OPACITY: str
    CLONE_STAMP_TOOL_PRESSURE_SIZE: str
    COLOR_SELECT_MODE: str
    COMFYUI_CACHED_SCALING_MODE: str
    COMFYUI_INPAINTING_MODEL: str
    COMFYUI_MODEL_CONFIG: str
    COMFYUI_TILED_VAE: str
    COMFYUI_TILED_VAE_TILE_SIZE: str
    CONTROLNET_ARGS_0_COMFYUI: str
    CONTROLNET_ARGS_0_WEBUI: str
    CONTROLNET_ARGS_1_COMFYUI: str
    CONTROLNET_ARGS_1_WEBUI: str
    CONTROLNET_ARGS_2_COMFYUI: str
    CONTROLNET_ARGS_2_WEBUI: str
    CONTROLNET_TAB_BAR: str
    CUTN: str
    DENOISING_STRENGTH: str
    DRAW_TOOL_ANTIALIAS: str
    DRAW_TOOL_BRUSH_PATTERN: str
    DRAW_TOOL_BRUSH_SIZE: str
    DRAW_TOOL_HARDNESS: str
    DRAW_TOOL_OPACITY: str
    DRAW_TOOL_PRESSURE_HARDNESS: str
    DRAW_TOOL_PRESSURE_OPACITY: str
    DRAW_TOOL_PRESSURE_SIZE: str
    EDIT_MODE: str
    EDIT_SIZE: str
    ERASER_TOOL_ANTIALIAS: str
    ERASER_TOOL_HARDNESS: str
    ERASER_TOOL_OPACITY: str
    ERASER_TOOL_PRESSURE_HARDNESS: str
    ERASER_TOOL_PRESSURE_OPACITY: str
    ERASER_TOOL_PRESSURE_SIZE: str
    ERASER_TOOL_SIZE: str
    EXPECT_TABLET_INPUT: str
    FILL_THRESHOLD: str
    FILL_TOOL_BRUSH_PATTERN: str
    FILTER_TOOL_ANTIALIAS: str
    FILTER_TOOL_BRUSH_SIZE: str
    FILTER_TOOL_CACHED_PARAMETERS: str
    FILTER_TOOL_HARDNESS: str
    FILTER_TOOL_OPACITY: str
    FILTER_TOOL_PRESSURE_HARDNESS: str
    FILTER_TOOL_PRESSURE_OPACITY: str
    FILTER_TOOL_PRESSURE_SIZE: str
    FILTER_TOOL_SELECTED_FILTER: str
    GENERATION_SIZE: str
    GENERATION_TAB_BAR: str
    GENERATOR_SCALING_MODES: str
    GLID_SERVER_URL: str
    GUIDANCE_SCALE: str
    HYPERNETWORK_MODELS: str
    IMAGE_LAYER_SCALING_BEHAVIOR: str
    INPAINT_FULL_RES: str
    INPAINT_FULL_RES_PADDING: str
    INPAINT_OPTIONS_AVAILABLE: str
    LAST_ACTIVE_TOOL: str
    LAST_BRUSH_COLOR: str
    LAST_FILE_PATH: str
    LAST_NAV_PANEL_TOOL: str
    LAST_SEED: str
    LORA_MODELS: str
    MASKED_CONTENT: str
    MYPAINT_BRUSH: str
    NEGATIVE_PROMPT: str
    NEW_IMAGE_BACKGROUND_COLOR: str
    PAINT_SELECTION_ONLY: str
    PAINT_TOOL_BRUSH_SIZE: str
    PROMPT: str
    RECENT_TOOLS: str
    SAMPLE_MERGED: str
    SAMPLING_METHOD: str
    SAMPLING_STEPS: str
    SAVED_LAYER_WINDOW_POS: str
    SAVED_MAIN_WINDOW_POS: str
    SAVED_NAVIGATION_WINDOW_POS: str
    SCALING_MODE: str
    SCHEDULER: str
    SCRIPTS_IMG2IMG: str
    SCRIPTS_TXT2IMG: str
    SD_COMFYUI_SERVER_URL: str
    SD_MODEL: str
    SD_UPSCALING_AVAILABLE: str
    SD_UPSCALING_CONTROLNET_TILE_MODELS: str
    SD_UPSCALING_CONTROLNET_TILE_PREPROCESSORS: str
    SD_UPSCALING_CONTROLNET_TILE_SETTINGS: str
    SD_UPSCALING_DENOISING_STRENGTH: str
    SD_UPSCALING_STEP_COUNT: str
    SD_WEBUI_SERVER_URL: str
    SEED: str
    SELECTION_BRUSH_SIZE: str
    SHAPE_TOOL_ANTIALIAS: str
    SHAPE_TOOL_DASH_PATTERN: str
    SHAPE_TOOL_FILL_COLOR: str
    SHAPE_TOOL_FILL_PATTERN: str
    SHAPE_TOOL_LINE_COLOR: str
    SHAPE_TOOL_LINE_JOIN_STYLE: str
    SHAPE_TOOL_LINE_STYLE: str
    SHAPE_TOOL_LINE_WIDTH: str
    SHAPE_TOOL_MODE: str
    SHAPE_TOOL_STAR_INNER_POINT_FRACTION: str
    SHAPE_TOOL_VERTEX_COUNT: str
    SKIP_STEPS: str
    SMUDGE_TOOL_ANTIALIAS: str
    SMUDGE_TOOL_BRUSH_SIZE: str
    SMUDGE_TOOL_HARDNESS: str
    SMUDGE_TOOL_OPACITY: str
    SMUDGE_TOOL_PRESSURE_HARDNESS: str
    SMUDGE_TOOL_PRESSURE_OPACITY: str
    SMUDGE_TOOL_PRESSURE_SIZE: str
    STYLES: str
    TEXT_BACKGROUND_COLOR: str
    TEXT_TOOL_PARAMS: str
    TOOL_TAB_BAR: str
    ULTIMATE_UPSCALE_SCRIPT_AVAILABLE: str
    USE_STABLE_DIFFUSION_UPSCALING: str
    USE_ULTIMATE_UPSCALE_SCRIPT: str
    WEBUI_CACHED_SCALING_MODE: str
    WEBUI_LAST_SUBSEED: str
    WEBUI_RESTORE_FACES: str
    WEBUI_SEED_RESIZE: str
    WEBUI_SEED_RESIZE_ENABLED: str
    WEBUI_SUBSEED: str
    WEBUI_SUBSEED_STRENGTH: str
    WEBUI_TILING: str
