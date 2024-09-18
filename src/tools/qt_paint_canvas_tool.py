"""Base implementation for CanvasTool classes that use a QTPaintCanvas."""
import logging
from typing import Optional

from PySide6.QtGui import QColor, Qt

from src.config.cache import Cache
from src.image.canvas.qt_paint_canvas import QtPaintCanvas
from src.image.layers.image_stack import ImageStack
from src.tools.canvas_tool import CanvasTool
from src.ui.image_viewer import ImageViewer
from src.ui.input_fields.pattern_combo_box import PatternComboBox, BRUSH_PATTERN_SOLID
from src.ui.panel.tool_control_panels.canvas_tool_panel import CanvasToolPanel
from src.ui.panel.tool_control_panels.draw_tool_panel import DrawToolPanel

logger = logging.getLogger(__name__)


class QtPaintCanvasTool(CanvasTool):
    """Implements brush controls using a minimal QPainter-based brush engine."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer,
                 size_key: Optional[str] = None, pressure_size_key: Optional[str] = None,
                 opacity_key: Optional[str] = None, pressure_opacity_key: Optional[str] = None,
                 hardness_key: Optional[str] = None, pressure_hardness_key: Optional[str] = None,
                 color_key: Optional[str] = None, pattern_key: Optional[str] = None) -> None:
        canvas = QtPaintCanvas()
        super().__init__(image_stack, image_viewer, canvas)
        self._last_click = None
        self._control_panel: Optional[DrawToolPanel] = None
        self._drawing = False
        self._cached_size = None

        # Connect and load all provided cache keys:
        cache = Cache()

        if size_key is not None:
            def _update_size(size: int) -> None:
                self.brush_size = size
            cache.connect(self, size_key, _update_size)
            self.brush_size = cache.get(size_key)

        if pressure_size_key is not None:
            def _update_pressure_size(pressure: bool) -> None:
                canvas.pressure_size = pressure
            cache.connect(self, pressure_size_key, _update_pressure_size)
            canvas.pressure_size = cache.get(pressure_size_key)

        if opacity_key is not None:
            def _update_opacity(opacity: float) -> None:
                canvas.opacity = opacity
            cache.connect(self, opacity_key, _update_opacity)
            canvas.opacity = cache.get(opacity_key)

        if pressure_opacity_key is not None:
            def _update_pressure_opacity(pressure: bool) -> None:
                canvas.pressure_opacity = pressure
            cache.connect(self, pressure_opacity_key, _update_pressure_opacity)
            canvas.pressure_opacity = cache.get(pressure_opacity_key)

        if hardness_key is not None:
            def _update_hardness(hardness: float) -> None:
                canvas.hardness = hardness
            cache.connect(self, hardness_key, _update_hardness)
            canvas.hardness = cache.get(hardness_key)

        if pressure_hardness_key is not None:
            def _update_pressure_hardness(pressure: bool) -> None:
                canvas.pressure_hardness = pressure
            cache.connect(self, pressure_hardness_key, _update_pressure_hardness)
            canvas.pressure_hardness = cache.get(pressure_hardness_key)

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
                    pattern_brush = PatternComboBox.get_brush(pattern_str)
                    if pattern_brush.style() != Qt.BrushStyle.SolidPattern:
                        canvas.set_pattern_brush(pattern_brush)
                    else:
                        canvas.set_pattern_brush(None)
                except KeyError:
                    logger.error(f'Got invalid pattern name {pattern_str}')
                    cache.set(pattern_key, BRUSH_PATTERN_SOLID)
            cache.connect(self, pattern_key, _update_pattern)
            _update_pattern(cache.get(pattern_key))
        self.update_brush_cursor()

        if cache.get(Cache.EXPECT_TABLET_INPUT):
            control_panel = self.get_control_panel()
            assert isinstance(control_panel, CanvasToolPanel)
            control_panel.show_pressure_checkboxes()
