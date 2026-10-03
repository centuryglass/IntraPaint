"""Keeps the generation resolution and recent frame sizes in step with the generation area.

The generation area size drives the resolution, never the reverse: the resolution rule writes Cache.GENERATION_SIZE
whenever the area size changes, and nothing here sets the area from the resolution. Any GENERATION_SIZE change the rule
didn't write switches the rule to manual, so a typed resolution is never overwritten.
"""
from PySide6.QtCore import QObject, QRect, QSize

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.layers.image_stack import ImageStack
from src.util.application_state import AppStateTracker, APP_STATE_EDITING
from src.util.generation_area_utils import resolution_for_area, previous_frame, updated_recent_sizes, \
    RESOLUTION_RULE_MANUAL

PREVIOUS_FRAME_BINDING_ID = 'GenerationAreaController_previous_frame'


def record_generation_area_size(size: QSize) -> None:
    """Records a finished generation area size change in Cache.RECENT_GENERATION_AREA_SIZES."""
    cache = Cache()
    recent = cache.get(Cache.RECENT_GENERATION_AREA_SIZES)
    updated = updated_recent_sizes(recent, size)
    if updated != recent:
        cache.set(Cache.RECENT_GENERATION_AREA_SIZES, updated)


def apply_generation_area_frame(image_stack: ImageStack, size: QSize) -> None:
    """Resizes the generation area around its center, then records the resulting size as a recent frame.

    ImageStack clamps the new area to the image and the area size limits, so the recorded size can be smaller than
    `size`.
    """
    area = image_stack.generation_area
    new_area = QRect(0, 0, size.width(), size.height())
    new_area.moveCenter(area.center())
    image_stack.generation_area = new_area
    record_generation_area_size(image_stack.generation_area.size())


class GenerationAreaController(QObject):
    """Applies the resolution rule on generation area size changes, and handles the previous frame hotkey."""

    def __init__(self, image_stack: ImageStack) -> None:
        super().__init__()
        self._image_stack = image_stack
        self._area_size = image_stack.generation_area.size()
        self._writing_resolution = False
        image_stack.generation_area_bounds_changed.connect(self._area_bounds_changed)
        cache = Cache()
        cache.connect(self, Cache.GENERATION_SIZE, self._resolution_changed)
        cache.connect(self, Cache.GENERATION_RESOLUTION_RULE, self.apply_resolution_rule)
        config = AppConfig()
        config.connect(self, AppConfig.GENERATION_RESOLUTION_MIN_SIDE, self.apply_resolution_rule)
        config.connect(self, AppConfig.MAX_GENERATION_SIZE, self.apply_resolution_rule)
        hotkey_filter = HotkeyFilter.instance()
        hotkey_filter.remove_keybinding(PREVIOUS_FRAME_BINDING_ID)
        hotkey_filter.register_config_keybinding(PREVIOUS_FRAME_BINDING_ID, self._previous_frame_hotkey,
                                                 KeyConfig().PREVIOUS_GENERATION_FRAME_KEY)
        self.apply_resolution_rule()

    def apply_resolution_rule(self) -> None:
        """Sets the generation resolution from the generation area size, unless the rule is manual."""
        config = AppConfig()
        resolution = resolution_for_area(self._image_stack.generation_area.size(),
                                         Cache().get(Cache.GENERATION_RESOLUTION_RULE),
                                         config.get(AppConfig.GENERATION_RESOLUTION_MIN_SIDE),
                                         config.get(AppConfig.MAX_GENERATION_SIZE))
        if resolution is None:
            return
        self._writing_resolution = True
        try:
            Cache().set(Cache.GENERATION_SIZE, resolution)
        finally:
            self._writing_resolution = False

    def select_previous_frame(self) -> bool:
        """Switches the generation area to the most recent other size, returning whether there was one."""
        size = previous_frame(Cache().get(Cache.RECENT_GENERATION_AREA_SIZES), self._image_stack.generation_area.size())
        if size is None:
            return False
        apply_generation_area_frame(self._image_stack, size)
        return True

    def _previous_frame_hotkey(self) -> bool:
        if AppStateTracker.app_state() != APP_STATE_EDITING:
            return False
        return self.select_previous_frame()

    def _area_bounds_changed(self, bounds: QRect) -> None:
        if bounds.size() == self._area_size:
            return
        self._area_size = bounds.size()
        self.apply_resolution_rule()

    def _resolution_changed(self) -> None:
        if self._writing_resolution:
            return
        Cache().set(Cache.GENERATION_RESOLUTION_RULE, RESOLUTION_RULE_MANUAL)
