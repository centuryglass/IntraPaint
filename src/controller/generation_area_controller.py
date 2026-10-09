"""Keeps the generation resolution, recent frame sizes and generation area position in step with the image.

The generation area size drives the resolution, never the reverse: the resolution rule writes Cache.GENERATION_SIZE
whenever the area size changes, and nothing here sets the area from the resolution. Any GENERATION_SIZE change the rule
didn't write switches the rule to manual, so a typed resolution is never overwritten.

Follow-selection moves the area after selection edits, and only when the selection bounds or context pins changed. Area
moves and padding changes alone never trigger it, so it never undoes a manual move.
"""
from typing import Optional

from PySide6.QtCore import QObject, QRect, QSize, QTimer, Qt, QPoint
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.layers.image_stack import ImageStack
from src.undo_stack import UndoStack
from src.util.application_state import AppStateTracker, APP_STATE_EDITING
from src.util.generation_area_utils import resolution_for_area, previous_frame, updated_recent_sizes, \
    RESOLUTION_RULE_MANUAL, follow_selection_target, follow_selection_position, FOLLOW_SELECTION_OFF
from src.util.shared_constants import EDIT_MODE_INPAINT

PREVIOUS_FRAME_BINDING_ID = 'GenerationAreaController_previous_frame'

# Milliseconds a selection must stay unchanged before the generation area follows it.
FOLLOW_SELECTION_DELAY_MS = 300


def record_generation_area_size(size: QSize) -> None:
    """Records a finished generation area size change in Cache.RECENT_GENERATION_AREA_SIZES."""
    cache = Cache()
    recent = cache.get(Cache.RECENT_GENERATION_AREA_SIZES)
    updated = updated_recent_sizes(recent, size)
    if updated != recent:
        cache.set(Cache.RECENT_GENERATION_AREA_SIZES, updated)


def apply_generation_area_frame(image_stack: ImageStack, size: QSize) -> None:
    """Resizes the generation area, then records the resulting size as a recent frame.

    With follow-selection on and a selection, the new area is placed by the same rule that follows selection edits,
    so it still contains the selection when the selection fits in `size`. Otherwise it resizes around its old center.
    ImageStack clamps the new area to the image and the area size limits, so the recorded size can be smaller than
    `size`.
    """
    area = image_stack.generation_area
    new_area = QRect(0, 0, size.width(), size.height())
    mode = AppConfig().get(AppConfig.GENERATION_AREA_FOLLOW_SELECTION)
    position = None
    if mode != FOLLOW_SELECTION_OFF:
        cache = Cache()
        padding = cache.get(Cache.INPAINT_FULL_RES_PADDING) if cache.get(Cache.INPAINT_FULL_RES) else 0
        selection_layer = image_stack.selection_layer
        target = follow_selection_target(selection_layer.get_selection_bounds(), selection_layer.context_pins,
                                         padding)
        if target is not None:
            position = follow_selection_position(new_area, target, mode, image_stack.bounds)
            new_area.moveTopLeft(position)
    if position is None:
        new_area.moveCenter(area.center())
    image_stack.generation_area = new_area
    record_generation_area_size(image_stack.generation_area.size())


class GenerationAreaController(QObject):
    """Applies the resolution rule on generation area size changes, moves the area to follow selection edits, and
    handles the previous frame hotkey."""

    def __init__(self, image_stack: ImageStack) -> None:
        super().__init__()
        self._image_stack = image_stack
        self._area_size = image_stack.generation_area.size()
        self._writing_resolution = False
        # Whether the generation area is shown. The area only follows the selection while it is.
        self.generation_area_visible = False
        # The selection bounds and pins the area last followed. Padding isn't part of it, so padding changes alone don't
        # move the area.
        self._followed_selection = self._current_selection_state()
        self._follow_skipped_for_history = False
        self._follow_timer = QTimer(self)
        self._follow_timer.setSingleShot(True)
        self._follow_timer.timeout.connect(self.follow_selection)
        image_stack.generation_area_bounds_changed.connect(self._area_bounds_changed)
        selection_layer = image_stack.selection_layer
        selection_layer.content_changed.connect(self._selection_changed)
        selection_layer.context_pins_changed.connect(self._selection_changed)
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

    @property
    def follow_pending(self) -> bool:
        """Returns whether a selection change is waiting for follow_selection."""
        return self._follow_timer.isActive()

    def follow_selection(self) -> None:
        """Moves the generation area to follow the selection, if the selection or its pins changed since the last call.

        Runs once a selection change has settled. A change made by undo or redo only updates the followed state, so
        undo and redo never move the area. While a mouse button is held, this waits for another delay.
        """
        if QApplication.mouseButtons() != Qt.MouseButton.NoButton:
            self._start_follow_timer()
            return
        self._follow_timer.stop()
        selection_state = self._current_selection_state()
        skipped_for_history = self._follow_skipped_for_history
        self._follow_skipped_for_history = False
        if selection_state == self._followed_selection:
            return
        self._followed_selection = selection_state
        mode = AppConfig().get(AppConfig.GENERATION_AREA_FOLLOW_SELECTION)
        cache = Cache()
        if (skipped_for_history or mode == FOLLOW_SELECTION_OFF or not self.generation_area_visible
                or cache.get(Cache.EDIT_MODE) != EDIT_MODE_INPAINT):
            return
        padding = cache.get(Cache.INPAINT_FULL_RES_PADDING) if cache.get(Cache.INPAINT_FULL_RES) else 0
        target = follow_selection_target(*selection_state, padding)
        if target is None:
            return
        area = self._image_stack.generation_area
        position = follow_selection_position(area, target, mode, self._image_stack.bounds)
        if position != area.topLeft():
            self._image_stack.generation_area = QRect(position, area.size())

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

    def _current_selection_state(self) -> tuple[Optional[QRect], list[QPoint]]:
        selection_layer = self._image_stack.selection_layer
        return selection_layer.get_selection_bounds(), selection_layer.context_pins

    def _start_follow_timer(self) -> None:
        # The delay outlasts the undo merge interval, so the follow move doesn't merge into the selection edit's step.
        merge_interval_ms = round(AppConfig().get(AppConfig.UNDO_MERGE_INTERVAL) * 1000)
        self._follow_timer.start(max(FOLLOW_SELECTION_DELAY_MS, merge_interval_ms + 50))

    def _selection_changed(self, *_args) -> None:
        undo_stack = UndoStack()
        if undo_stack.undo_in_progress or undo_stack.redo_in_progress:
            self._follow_skipped_for_history = True
        self._start_follow_timer()

    def _area_bounds_changed(self, bounds: QRect) -> None:
        if bounds.size() == self._area_size:
            return
        self._area_size = bounds.size()
        self.apply_resolution_rule()

    def _resolution_changed(self) -> None:
        if self._writing_resolution:
            return
        Cache().set(Cache.GENERATION_RESOLUTION_RULE, RESOLUTION_RULE_MANUAL)
