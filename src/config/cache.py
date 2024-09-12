"""Use the Config module's data sharing capabilities to cache temporary values."""
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QWidget

from src.config.config import Config
from src.util.shared_constants import PROJECT_DIR, DATA_DIR
from src.util.singleton import Singleton

CONFIG_DEFINITIONS = f'{PROJECT_DIR}/resources/config/cache_value_definitions.json'
DEFAULT_FILE_PATH = f'{DATA_DIR}/.cache.json'


class Cache(Config, metaclass=Singleton):
    """Use the Config module's data sharing capabilities to cache temporary values."""

    def __init__(self, json_path: str = DEFAULT_FILE_PATH) -> None:
        """Initialize the cache, registering expected value types."""
        super().__init__(CONFIG_DEFINITIONS, json_path, Cache)

    def save_bounds(self, key: str, widget: QWidget) -> None:
        """Save a widget's geometry to the cache."""
        cache_str = f'{widget.x()},{widget.y()},{widget.width()},{widget.height()}'
        self.set(key, cache_str)

    def load_bounds(self, key: str, widget: QWidget) -> bool:
        """Load widget bounds from the cache, returning whether loading succeeded."""
        try:
            bounds = QRect(*(int(param) for param in self.get(key).split(',')))
            widget.setGeometry(bounds)
            return bounds == widget.geometry()
        except (ValueError, TypeError):
            return False

    # DYNAMIC PROPERTIES:
    # Generate with `python /home/anthony/Workspace/ML/IntraPaint/scripts/dynamic_import_typing.py src/config/cache.py`

    CONTROLNET_CONTROL_TYPES: str
    CONTROLNET_MODELS: str
    CONTROLNET_MODULES: str
    CONTROLNET_VERSION: str
    DRAW_TOOL_FILL_TYPE: str
    DRAW_TOOL_HARDNESS: str
    DRAW_TOOL_OPACITY: str
    DRAW_TOOL_PRESSURE_HARDNESS: str
    DRAW_TOOL_PRESSURE_OPACITY: str
    DRAW_TOOL_PRESSURE_SIZE: str
    FILL_THRESHOLD: str
    LAST_ACTIVE_TOOL: str
    LAST_BRUSH_COLOR: str
    LAST_FILE_PATH: str
    LAST_NAV_PANEL_TOOL: str
    LAST_SEED: str
    LORA_MODELS: str
    NEW_IMAGE_BACKGROUND_COLOR: str
    PAINT_SELECTION_ONLY: str
    SAMPLE_MERGED: str
    SAVED_MAIN_WINDOW_POS: str
    STYLES: str
    TEXT_BACKGROUND_COLOR: str
    TEXT_TOOL_PARAMS: str
