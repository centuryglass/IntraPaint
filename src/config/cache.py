"""Use the Config module's data sharing capabilities to cache temporary values."""
from argparse import Namespace
from typing import Any, Optional

from PySide6.QtCore import QRect, QTimer
from PySide6.QtWidgets import QWidget, QApplication

from src.config.config import Config
from src.config.generated_keys import CacheKeys
from src.util.shared_constants import PROJECT_DIR, DATA_DIR
from src.util.singleton import Singleton
from src.util.visual.display_size import get_screen_bounds

CONFIG_DEFINITIONS = f'{PROJECT_DIR}/resources/config/cache_value_definitions.json'
DEFAULT_FILE_PATH = f'{DATA_DIR}/.cache.json'
GEOMETRY_CHECK_INTERVAL = 100

# The QCoreApplication.translate context for strings in this file
TR_ID = 'config.cache'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


SCALING_OPTION_NONE = _tr('None')


class Cache(CacheKeys, Config, metaclass=Singleton):
    """Use the Config module's data sharing capabilities to cache temporary values."""

    def __init__(self, json_path: str = DEFAULT_FILE_PATH) -> None:
        """Initialize the cache, registering expected value types."""
        super().__init__(CONFIG_DEFINITIONS, json_path)
        self._geometry_timer = QTimer()
        self._geometry_timer.setInterval(GEOMETRY_CHECK_INTERVAL)
        self._geometry_timer.timeout.connect(self._check_bounds)
        self._final_bounds: dict[QWidget, QRect] = {}
        self._last_bounds: dict[QWidget, QRect] = {}

    def _migrate_legacy_keys(self, json_data: dict[str, Any]) -> None:
        """Converts the saved `color_select_mode` checkbox to `selection_fill_area`."""
        if 'selection_fill_area' not in json_data and json_data.get('color_select_mode') is True:
            json_data['selection_fill_area'] = 'By color'

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
            x, y, w, h = (int(param) for param in self.get(key).split(','))
            bounds = QRect(x, y, w, h)
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

    def tiling_in_effect(self) -> bool:
        """Returns whether generated images tile: the WebUI generator is connected and its tiling option is on."""
        return bool(self.get(Cache.WEBUI_TILING_AVAILABLE) and self.get(Cache.WEBUI_TILING))

    def limited_context_in_effect(self) -> bool:
        """Returns whether inpainting limits context to the selection. Read this, not
        `Cache.INPAINT_FULL_RES` alone, wherever the crop is drawn or applied.

        Tiling turns the crop off and leaves `Cache.INPAINT_FULL_RES` as the user set it. A crop's edges wrap only to
        each other, so a tiling crop never tiles with the image around it.
        """
        return bool(self.get(Cache.INPAINT_FULL_RES)) and not self.tiling_in_effect()

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
