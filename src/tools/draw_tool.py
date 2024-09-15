"""Implements drawing controls using a minimal QPainter-based canvas."""
from typing import Optional

from PySide6.QtGui import QColor, QIcon, QKeySequence, Qt
from PySide6.QtWidgets import QWidget, QApplication

from src.config.cache import Cache
from src.config.config_entry import RangeKey
from src.config.key_config import KeyConfig
from src.image.canvas.qt_paint_canvas import QtPaintCanvas
from src.image.layers.image_stack import ImageStack
from src.tools.base_tool import BaseTool
from src.tools.canvas_tool import CanvasTool
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.canvas_selection_panel import TOOL_MODE_ERASE
from src.ui.panel.tool_control_panels.draw_tool_panel import DrawToolPanel
from src.util.shared_constants import PROJECT_DIR, COLOR_PICK_HINT
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.draw_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


ICON_DRAW_TOOL = f'{PROJECT_DIR}/resources/icons/tools/pen_icon.svg'
LABEL_TEXT_DRAW_TOOL = _tr('Draw')
TOOLTIP_DRAW_TOOL = _tr('Draw into the image')
CONTROL_HINT_DRAW_TOOL = _tr('{left_mouse_icon}: draw - {right_mouse_icon}: 1px draw')


class DrawTool(CanvasTool):
    """Implements brush controls using a minimal QPainter-based brush engine."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer,
                 size_key: Optional[str] = None, pressure_size_key: Optional[str] = None,
                 opacity_key: Optional[str] = None, pressure_opacity_key: Optional[str] = None,
                 hardness_key: Optional[str] = None, pressure_hardness_key: Optional[str] = None) -> None:
        super().__init__(image_stack, image_viewer, QtPaintCanvas())
        self._size_key = Cache.DRAW_TOOL_BRUSH_SIZE if size_key is None else size_key
        self._pressure_size_key = Cache.DRAW_TOOL_PRESSURE_SIZE if pressure_size_key is None else pressure_size_key
        self._opacity_key = Cache.DRAW_TOOL_OPACITY if opacity_key is None else opacity_key
        self._pressure_opacity_key = Cache.DRAW_TOOL_PRESSURE_OPACITY if pressure_opacity_key is None \
            else pressure_opacity_key
        self._hardness_key = Cache.DRAW_TOOL_HARDNESS if hardness_key is None \
            else hardness_key
        self._pressure_hardness_key = Cache.DRAW_TOOL_PRESSURE_HARDNESS if pressure_hardness_key is None \
            else pressure_hardness_key
        self._last_click = None
        self._control_panel: Optional[DrawToolPanel] = None
        self._active = False
        self._drawing = False
        self._cached_size = None
        self._icon = QIcon(ICON_DRAW_TOOL)

        # Load color and size from cache
        cache = Cache()
        self.brush_size = cache.get(self._size_key)
        self.brush_color = cache.get_color(Cache.LAST_BRUSH_COLOR, Qt.GlobalColor.black)

        canvas = self.canvas
        assert isinstance(canvas, QtPaintCanvas)
        canvas.brush_size = cache.get(self._size_key)
        canvas.opacity = cache.get(self._opacity_key)
        canvas.hardness = cache.get(self._hardness_key)
        canvas.pressure_size = cache.get(self._pressure_size_key)
        canvas.pressure_opacity = cache.get(self._pressure_opacity_key)
        canvas.pressure_hardness = cache.get(self._pressure_hardness_key)

        def _update_size(size: int) -> None:
            canvas.brush_size = size
            self.update_brush_cursor()
        cache.connect(self, self._size_key, _update_size)

        def _update_pressure_size(pressure: bool) -> None:
            canvas.pressure_size = pressure
        cache.connect(self, self._pressure_size_key, _update_pressure_size)

        def _update_opacity(opacity: float) -> None:
            canvas.opacity = opacity
        cache.connect(self, self._opacity_key, _update_opacity)

        def _update_pressure_opacity(pressure: bool) -> None:
            canvas.pressure_opacity = pressure
        cache.connect(self, self._pressure_opacity_key, _update_pressure_opacity)

        def _update_hardness(hardness: float) -> None:
            canvas.hardness = hardness
        cache.connect(self, self._hardness_key, _update_hardness)

        def _update_pressure_hardness(pressure: bool) -> None:
            canvas.pressure_hardness = pressure
        cache.connect(self, self._pressure_hardness_key, _update_pressure_hardness)

        def _update_brush_color(color_str: str) -> None:
            color = QColor(color_str)
            self.brush_color = color
        cache.connect(self, Cache.LAST_BRUSH_COLOR, _update_brush_color)
        self.update_brush_cursor()

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return KeyConfig().get_keycodes(KeyConfig.DRAW_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return LABEL_TEXT_DRAW_TOOL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return TOOLTIP_DRAW_TOOL

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        control_hint_draw_tool = CONTROL_HINT_DRAW_TOOL.format(left_mouse_icon=left_button_hint_text(),
                                                               right_mouse_icon=right_button_hint_text(),
                                                               modifier_or_modifiers='{modifier_or_modifiers}')
        eyedropper_hint = BaseTool.modifier_hint(KeyConfig.EYEDROPPER_OVERRIDE_MODIFIER, COLOR_PICK_HINT)
        if len(eyedropper_hint) > 0:
            eyedropper_hint = ' - ' + eyedropper_hint
        return (f'{control_hint_draw_tool}{eyedropper_hint}<br/>{CanvasTool.canvas_control_hints()}'
                f'<br/>{super().get_input_hint()}')

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns the brush control panel."""
        if self._control_panel is None:
            self._control_panel = DrawToolPanel()

            def _set_eraser(tool_mode: str) -> None:
                self.canvas.eraser = tool_mode == TOOL_MODE_ERASE
            self._control_panel.tool_mode_changed.connect(_set_eraser)
        return self._control_panel

    def set_brush_size(self, new_size: int) -> None:
        """Update the brush size."""
        new_size = min(new_size, Cache().get(Cache.DRAW_TOOL_BRUSH_SIZE, RangeKey.MAX))
        super().set_brush_size(new_size)
        Cache().set(Cache.DRAW_TOOL_BRUSH_SIZE, max(1, new_size))
