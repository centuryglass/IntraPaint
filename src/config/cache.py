"""Use the Config module's data sharing capabilities to cache temporary values."""
from typing import Dict

from PySide6.QtCore import QRect, QTimer
from PySide6.QtWidgets import QWidget

from src.config.config import Config
from src.util.shared_constants import PROJECT_DIR, DATA_DIR
from src.util.singleton import Singleton

CONFIG_DEFINITIONS = f'{PROJECT_DIR}/resources/config/cache_value_definitions.json'
DEFAULT_FILE_PATH = f'{DATA_DIR}/.cache.json'
GEOMETRY_CHECK_INTERVAL = 100


class Cache(Config, metaclass=Singleton):
    """Use the Config module's data sharing capabilities to cache temporary values."""

    def __init__(self, json_path: str = DEFAULT_FILE_PATH) -> None:
        """Initialize the cache, registering expected value types."""
        super().__init__(CONFIG_DEFINITIONS, json_path, Cache)
        self._geometry_timer = QTimer()
        self._geometry_timer.setInterval(GEOMETRY_CHECK_INTERVAL)
        self._geometry_timer.timeout.connect(self._check_bounds)
        self._final_bounds: Dict[QWidget, QRect] = {}
        self._last_bounds: Dict[QWidget, QRect] = {}

    def save_bounds(self, key: str, widget: QWidget) -> None:
        """Save a widget's geometry to the cache.  If waiting to load bounds for the same widget the new bounds will
           not be saved, since they are about to be replaced anywya."""
        if widget not in self._last_bounds:  # Don't update if waiting to apply previous bounds
            cache_str = f'{widget.x()},{widget.y()},{widget.width()},{widget.height()}'
            self.set(key, cache_str)

    def load_bounds(self, key: str, widget: QWidget) -> bool:
        """Load widget bounds from the cache, returning whether loading succeeded.  Widget bounds will be applied once
           widget geometry has remained stable for 100ms, to avoid cases where bounds are immediately overridden by
           initial placement. """
        try:
            bounds = QRect(*(int(param) for param in self.get(key).split(',')))
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
            if bounds == self._last_bounds[widget]:
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
            return

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
    SAVED_IMAGE_WINDOW_POS: str
    SAVED_LAYER_WINDOW_POS: str
    SAVED_MAIN_WINDOW_POS: str
    STYLES: str
    TEXT_BACKGROUND_COLOR: str
    TEXT_TOOL_PARAMS: str
