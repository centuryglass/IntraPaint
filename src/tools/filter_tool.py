"""Use brush strokes to apply image filters."""
import json
from typing import Optional, List

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.brush.filter_brush import FilterBrush
from src.image.filter.blur import BlurFilter
from src.image.filter.brightness_contrast import BrightnessContrastFilter
from src.image.filter.filter import ImageFilter
from src.image.filter.posterize import PosterizeFilter
from src.image.filter.rgb_color_balance import RGBColorBalanceFilter
from src.image.filter.sharpen import SharpenFilter
from src.image.layers.image_stack import ImageStack
from src.tools.brush_tool import BrushTool
from src.tools.qt_paint_brush_tool import QtPaintBrushTool
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.filter_tool_panel import FilterToolPanel
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.filter_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


RESOURCES_FILTER_ICON = f'{PROJECT_DIR}/resources/icons/tools/filter_icon.svg'
FILTER_LABEL = _tr('Filter')
FILTER_TOOLTIP = _tr('Draw to apply an image filter')
FILTER_CONTROL_HINT = _tr('{left_mouse_icon}: filter - {right_mouse_icon}: 1px filter')


class FilterTool(QtPaintBrushTool):
    """Use brush strokes to apply image filters."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        cache = Cache()
        self._control_panel: Optional[FilterToolPanel] = None
        self._filters: List[ImageFilter] = [
            BlurFilter(image_stack),
            BrightnessContrastFilter(image_stack),
            PosterizeFilter(image_stack),
            RGBColorBalanceFilter(image_stack),
            SharpenFilter(image_stack)
        ]
        try:
            self._filter_params = json.loads(cache.get(Cache.FILTER_TOOL_CACHED_PARAMETERS))
        except json.JSONDecodeError:
            self._filter_params = {}
        added_defaults = False
        for img_filter in self._filters:
            filter_key = img_filter.get_name()
            if filter_key in self._filter_params:
                continue
            self._filter_params[filter_key] = [param.default_value for param in img_filter.get_parameters()]
            added_defaults = True
        if added_defaults:
            Cache().set(Cache.FILTER_TOOL_CACHED_PARAMETERS, json.dumps(self._filter_params))
        try:
            initial_filter = self._filter_from_name(cache.get(Cache.FILTER_TOOL_SELECTED_FILTER))
        except ValueError:
            initial_filter = self._filters[0]
            cache.set(Cache.FILTER_TOOL_SELECTED_FILTER, initial_filter.get_name())
        self._active_filter = initial_filter
        brush = FilterBrush(initial_filter)
        brush.parameter_values = self._filter_params[self._active_filter.get_name()]
        super().__init__(KeyConfig.FILTER_TOOL_KEY, FILTER_LABEL, FILTER_TOOLTIP, QIcon(RESOURCES_FILTER_ICON),
                         image_stack, image_viewer, size_key=Cache.FILTER_TOOL_BRUSH_SIZE,
                         pressure_size_key=Cache.FILTER_TOOL_PRESSURE_SIZE, opacity_key=Cache.FILTER_TOOL_OPACITY,
                         pressure_opacity_key=Cache.FILTER_TOOL_PRESSURE_OPACITY,
                         hardness_key=Cache.FILTER_TOOL_HARDNESS,
                         pressure_hardness_key=Cache.FILTER_TOOL_PRESSURE_HARDNESS, brush=brush)
        cache.connect(self, Cache.FILTER_TOOL_SELECTED_FILTER, self._filter_update_slot)
        cache.connect(self, Cache.FILTER_TOOL_CACHED_PARAMETERS, self._filter_param_update_slot)

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        brush_hint = FILTER_CONTROL_HINT.format(left_mouse_icon=left_button_hint_text(),
                                                right_mouse_icon=right_button_hint_text())
        return f'{brush_hint}<br/>{BrushTool.brush_control_hints()}<br/>{BrushTool.get_input_hint(self)}'

    # noinspection PyMethodMayBeStatic
    def get_control_panel(self) -> Optional[QWidget]:
        """Returns the blur tool control panel."""
        if self._control_panel is None:
            self._control_panel = FilterToolPanel(self._filters)
        return self._control_panel

    def _filter_update_slot(self, filter_name: str) -> None:
        new_filter = self._filter_from_name(filter_name)
        if new_filter == self._active_filter:
            return
        brush = self.brush
        assert isinstance(brush, FilterBrush)
        brush.image_filter = new_filter
        brush.parameter_values = self._filter_params[new_filter.get_name()]
        self._active_filter = new_filter

    def _filter_param_update_slot(self, filter_params: str) -> None:
        self._filter_params = json.loads(filter_params)
        brush = self.brush
        assert isinstance(brush, FilterBrush)
        brush.parameter_values = self._filter_params[self._active_filter.get_name()]

    def _filter_from_name(self, filter_name: str) -> ImageFilter:
        matching = [img_filter for img_filter in self._filters if img_filter.get_name() == filter_name]
        if len(matching) == 0:
            raise ValueError(f'invalid filter name {filter_name}')
        return matching[0]
