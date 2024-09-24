"""Base implementation for BrushTool classes that use a QtPaintBrush."""
import logging
from typing import Optional

from PySide6.QtGui import QColor, Qt, QIcon, QBrush

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.brush.qt_paint_brush import QtPaintBrush
from src.image.layers.image_stack import ImageStack
from src.tools.brush_tool import BrushTool
from src.ui.image_viewer import ImageViewer
from src.ui.input_fields.fill_style_combo_box import FillStyleComboBox, BRUSH_PATTERN_SOLID
from src.ui.panel.tool_control_panels.brush_tool_panel import BrushToolPanel
from src.ui.panel.tool_control_panels.draw_tool_panel import DrawToolPanel
from src.util.math_utils import clamp

logger = logging.getLogger(__name__)


class QtPaintBrushTool(BrushTool):
    """Base implementation for BrushTool classes that use a QtPaintBrush."""

    def __init__(self, activation_config_key: str, label_text: str, tooltip_text: str, icon: QIcon,
                 image_stack: ImageStack, image_viewer: ImageViewer,
                 size_key: Optional[str] = None, pressure_size_key: Optional[str] = None,
                 opacity_key: Optional[str] = None, pressure_opacity_key: Optional[str] = None,
                 hardness_key: Optional[str] = None, pressure_hardness_key: Optional[str] = None,
                 color_key: Optional[str] = None, pattern_key: Optional[str] = None,
                 brush: Optional[QtPaintBrush] = None) -> None:
        if brush is None:
            brush = QtPaintBrush()
        else:
            assert isinstance(brush, QtPaintBrush)
        super().__init__(activation_config_key, label_text, tooltip_text, icon, image_stack, image_viewer, brush)
        self._last_click = None
        self._control_panel: Optional[DrawToolPanel] = None
        self._drawing = False
        self._cached_size = None
        self._size_key = size_key
        self._opacity_key = opacity_key
        self._hardness_key = hardness_key

        # Connect and load all provided cache keys:
        cache = Cache()

        if size_key is not None:
            def _update_size(size: int) -> None:
                self.brush_size = size
            cache.connect(self, size_key, _update_size)
            self.brush_size = cache.get(size_key)

        if pressure_size_key is not None:
            def _update_pressure_size(pressure: bool) -> None:
                brush.pressure_size = pressure
            cache.connect(self, pressure_size_key, _update_pressure_size)
            brush.pressure_size = cache.get(pressure_size_key)

        if opacity_key is not None:
            def _update_opacity(opacity: float) -> None:
                brush.opacity = opacity
            cache.connect(self, opacity_key, _update_opacity)
            brush.opacity = cache.get(opacity_key)

            # Register slider hotkeys:
            down_id = f'QtPaintCanvasTool_{id(self)}_opacity_down'
            up_id = f'QtPaintCanvasTool_{id(self)}_opacity_up'
            key_filter = HotkeyFilter.instance()

            def _update_opacity_offset(offset: float) -> bool:
                offset *= 0.02  # offsets are int-based, scale to float range
                tool_control_panel = self.get_control_panel()
                if not self.is_active or tool_control_panel is None or not tool_control_panel.isEnabled():
                    return False
                self.opacity = float(clamp(self.opacity + offset, 0.0, 1.0))
                return True
            key_filter.register_speed_modified_keybinding(down_id,
                                                          lambda offset: _update_opacity_offset(-offset),
                                                          KeyConfig.BRUSH_OPACITY_DECREASE)
            key_filter.register_speed_modified_keybinding(up_id, _update_opacity_offset,
                                                          KeyConfig.BRUSH_OPACITY_INCREASE)

        if pressure_opacity_key is not None:
            def _update_pressure_opacity(pressure: bool) -> None:
                brush.pressure_opacity = pressure
            cache.connect(self, pressure_opacity_key, _update_pressure_opacity)
            brush.pressure_opacity = cache.get(pressure_opacity_key)

        if hardness_key is not None:
            def _update_hardness(hardness: float) -> None:
                brush.hardness = hardness
            cache.connect(self, hardness_key, _update_hardness)
            brush.hardness = cache.get(hardness_key)

            # Register slider hotkeys:
            down_id = f'QtPaintCanvasTool_{id(self)}_hardness_down'
            up_id = f'QtPaintCanvasTool_{id(self)}_hardness_up'
            key_filter = HotkeyFilter.instance()

            def _update_hardness_offset(offset: float) -> bool:
                offset *= 0.02  # offsets are int-based, scale to float range
                tool_control_panel = self.get_control_panel()
                if not self.is_active or tool_control_panel is None or not tool_control_panel.isEnabled():
                    return False
                self.hardness = float(clamp(self.hardness + offset, 0.0, 1.0))
                return True
            key_filter.register_speed_modified_keybinding(down_id,
                                                          lambda offset: _update_hardness_offset(-offset),
                                                          KeyConfig.BRUSH_HARDNESS_DECREASE)
            key_filter.register_speed_modified_keybinding(up_id, _update_hardness_offset,
                                                          KeyConfig.BRUSH_HARDNESS_INCREASE)

        if pressure_hardness_key is not None:
            def _update_pressure_hardness(pressure: bool) -> None:
                brush.pressure_hardness = pressure
            cache.connect(self, pressure_hardness_key, _update_pressure_hardness)
            brush.pressure_hardness = cache.get(pressure_hardness_key)

        if color_key is not None:
            def _update_color(color_str: str) -> None:
                if not QColor.isValidColor(color_str):
                    logger.error(f'Got invalid color string {color_str}')
                    return
                self.brush_color = QColor(color_str)
            cache.connect(self, color_key, _update_color)
            _update_color(cache.get(color_key))

        if pattern_key is not None:
            def _update_pattern(pattern_str: str) -> None:
                try:
                    fill_style = FillStyleComboBox.get_style(pattern_str)
                    if fill_style != Qt.BrushStyle.SolidPattern:
                        brush.set_pattern_brush(QBrush(fill_style))
                    else:
                        brush.set_pattern_brush(None)
                except KeyError:
                    logger.error(f'Got invalid pattern name {pattern_str}')
                    cache.set(pattern_key, BRUSH_PATTERN_SOLID)
            cache.connect(self, pattern_key, _update_pattern)
            _update_pattern(cache.get(pattern_key))
        self.update_brush_cursor()

        if cache.get(Cache.EXPECT_TABLET_INPUT):
            control_panel = self.get_control_panel()
            if isinstance(control_panel, BrushToolPanel):
                control_panel.show_pressure_checkboxes()

    @property
    def opacity(self) -> float:
        """Accesses brush opacity"""
        brush = self.brush
        assert isinstance(brush, QtPaintBrush)
        return brush.opacity

    @opacity.setter
    def opacity(self, opacity: float) -> None:
        opacity = float(clamp(opacity, 0.0, 1.0))
        if self._opacity_key is not None:
            Cache().set(self._opacity_key, opacity)
        else:
            brush = self.brush
            assert isinstance(brush, QtPaintBrush)
            brush.opacity = opacity

    @property
    def hardness(self) -> float:
        """Accesses brush hardness"""
        brush = self.brush
        assert isinstance(brush, QtPaintBrush)
        return brush.hardness

    @hardness.setter
    def hardness(self, hardness: float) -> None:
        hardness = float(clamp(hardness, 0.0, 1.0))
        if self._hardness_key is not None:
            Cache().set(self._hardness_key, hardness)
        else:
            brush = self.brush
            assert isinstance(brush, QtPaintBrush)
            brush.hardness = hardness

    def set_brush_size(self, new_size: int) -> None:
        """Ensure brush size also propagates to the appropriate config key."""
        if self._size_key is not None:
            Cache().set(self._size_key, new_size)
        super().set_brush_size(new_size)
