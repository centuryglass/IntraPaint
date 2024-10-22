"""Implements image smudge operations."""
from typing import Optional

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.brush.smudge_brush import SmudgeBrush
from src.image.layers.image_stack import ImageStack
from src.tools.brush_tool import BrushTool
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.brush_tool_panel import BrushToolPanel
from src.ui.panel.tool_control_panels.smudge_tool_panel import SmudgeToolPanel
from src.util.math_utils import clamp
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.smudge_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


ICON_PATH_SMUDGE_TOOL = f'{PROJECT_DIR}/resources/icons/tools/smudge_icon.svg'
CURSOR_PATH_SMUDGE_TOOL = f'{PROJECT_DIR}/resources/cursors/smudge_cursor.svg'
SMUDGE_LABEL = _tr('Smudge')
SMUDGE_TOOLTIP = _tr('Smudge image content')
SMUDGE_CONTROL_HINT = _tr('{left_mouse_icon}: smudge - {right_mouse_icon}: 1px smudge')


class SmudgeTool(BrushTool):  # type: ignore
    """Implements image smudge operations."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        brush = SmudgeBrush()
        super().__init__(KeyConfig.SMUDGE_TOOL_KEY, SMUDGE_LABEL, SMUDGE_TOOLTIP, QIcon(ICON_PATH_SMUDGE_TOOL),
                         image_stack, image_viewer, brush)
        self.set_scaling_icon_cursor(QIcon(CURSOR_PATH_SMUDGE_TOOL))
        self._control_panel = SmudgeToolPanel()
        cache = Cache()
        key_filter = HotkeyFilter.instance()

        def _size_update(size: int) -> None:
            self.brush_size = size
        cache.connect(self, Cache.SMUDGE_TOOL_BRUSH_SIZE, _size_update)
        self.brush_size = cache.get(Cache.SMUDGE_TOOL_BRUSH_SIZE)

        def _opacity_update(opacity: float) -> None:
            brush.opacity = opacity
        cache.connect(self, Cache.SMUDGE_TOOL_OPACITY, _opacity_update)
        brush.opacity = cache.get(Cache.SMUDGE_TOOL_OPACITY)

        def _update_opacity_offset(offset: float) -> bool:
            offset *= 0.02  # offsets are int-based, scale to float range
            tool_control_panel = self.get_control_panel()
            if not self.is_active or tool_control_panel is None or not tool_control_panel.isEnabled():
                return False
            self.opacity = float(clamp(self.opacity + offset, 0.0, 1.0))
            return True
        opacity_down_id = f'SmudgeTool_{id(self)}_opacity_down'
        opacity_up_id = f'SmudgeTool_{id(self)}_opacity_up'
        key_filter.register_speed_modified_keybinding(opacity_down_id,
                                                      lambda offset: _update_opacity_offset(-offset),
                                                      KeyConfig.BRUSH_OPACITY_DECREASE)
        key_filter.register_speed_modified_keybinding(opacity_up_id, _update_opacity_offset,
                                                      KeyConfig.BRUSH_OPACITY_INCREASE)

        def _hardness_update(hardness: float) -> None:
            brush.hardness = hardness
        cache.connect(self, Cache.SMUDGE_TOOL_HARDNESS, _hardness_update)
        brush.hardness = cache.get(Cache.SMUDGE_TOOL_HARDNESS)

        def _update_hardness_offset(offset: float) -> bool:
            offset *= 0.02  # offsets are int-based, scale to float range
            tool_control_panel = self.get_control_panel()
            if not self.is_active or tool_control_panel is None or not tool_control_panel.isEnabled():
                return False
            self.hardness = float(clamp(self.hardness + offset, 0.0, 1.0))
            return True
        hardness_down_id = f'SmudgeTool_{id(self)}_hardness_down'
        hardness_up_id = f'SmudgeTool_{id(self)}_hardness_up'
        key_filter.register_speed_modified_keybinding(hardness_down_id,
                                                      lambda offset: _update_hardness_offset(-offset),
                                                      KeyConfig.BRUSH_HARDNESS_DECREASE)
        key_filter.register_speed_modified_keybinding(hardness_up_id, _update_hardness_offset,
                                                      KeyConfig.BRUSH_HARDNESS_INCREASE)

        def _pressure_size_update(use_pressure: bool) -> None:
            brush.pressure_size = use_pressure
        cache.connect(self, Cache.SMUDGE_TOOL_PRESSURE_SIZE, _pressure_size_update)
        brush.pressure_size = cache.get(Cache.SMUDGE_TOOL_PRESSURE_SIZE)

        def _pressure_opacity_update(use_pressure: bool) -> None:
            brush.pressure_opacity = use_pressure
        cache.connect(self, Cache.SMUDGE_TOOL_PRESSURE_OPACITY, _pressure_opacity_update)
        brush.pressure_opacity = cache.get(Cache.SMUDGE_TOOL_PRESSURE_OPACITY)

        def _pressure_hardness_update(use_pressure: bool) -> None:
            brush.pressure_hardness = use_pressure
        cache.connect(self, Cache.SMUDGE_TOOL_PRESSURE_HARDNESS, _pressure_hardness_update)
        brush.pressure_hardness = cache.get(Cache.SMUDGE_TOOL_PRESSURE_HARDNESS)

        def _antialias_update(antialias: bool) -> None:
            brush.antialiasing = antialias
        cache.connect(self, Cache.SMUDGE_TOOL_ANTIALIAS, _antialias_update)
        _antialias_update(cache.get(Cache.SMUDGE_TOOL_ANTIALIAS))

        if cache.get(Cache.EXPECT_TABLET_INPUT):
            control_panel = self.get_control_panel()
            assert isinstance(control_panel, BrushToolPanel)
            control_panel.show_pressure_checkboxes()

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        brush_hint = SMUDGE_CONTROL_HINT.format(left_mouse_icon=left_button_hint_text(),
                                                right_mouse_icon=right_button_hint_text())
        return f'{brush_hint}<br/>{BrushTool.brush_control_hints()}<br/>{BrushTool.get_input_hint(self)}'

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns the blur tool control panel."""
        return self._control_panel

    @property
    def opacity(self) -> float:
        """Accesses brush opacity"""
        brush = self.brush
        assert isinstance(brush, SmudgeBrush)
        return brush.opacity

    @opacity.setter
    def opacity(self, opacity: float) -> None:
        opacity = float(clamp(opacity, 0.0, 1.0))
        Cache().set(Cache.SMUDGE_TOOL_OPACITY, opacity)

    @property
    def hardness(self) -> float:
        """Accesses brush hardness"""
        brush = self.brush
        assert isinstance(brush, SmudgeBrush)
        return brush.hardness

    @hardness.setter
    def hardness(self, hardness: float) -> None:
        hardness = float(clamp(hardness, 0.0, 1.0))
        Cache().set(Cache.SMUDGE_TOOL_HARDNESS, hardness)

    def set_brush_size(self, new_size: int) -> None:
        """Ensure brush size also propagates to the appropriate config key."""
        Cache().set(Cache.SMUDGE_TOOL_BRUSH_SIZE, new_size)
        super().set_brush_size(new_size)
