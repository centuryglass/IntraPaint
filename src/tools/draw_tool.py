"""Implements drawing controls using a minimal QPainter-based canvas."""
from typing import Optional

from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QIcon, QKeySequence, Qt, QTabletEvent
from PySide6.QtWidgets import QWidget, QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.config_entry import RangeKey
from src.config.key_config import KeyConfig
from src.image.canvas.qt_paint_canvas import QtPaintCanvas
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.tools.base_tool import BaseTool
from src.tools.canvas_tool import CanvasTool
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.canvas_selection_panel import TOOL_MODE_ERASE
from src.ui.panel.tool_control_panels.draw_tool_panel import DrawToolPanel
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text
from src.util.shared_constants import PROJECT_DIR, COLOR_PICK_HINT

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

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        super().__init__(image_stack, image_viewer, QtPaintCanvas())
        self._last_click = None
        self._control_panel: Optional[DrawToolPanel] = None
        self._active = False
        self._drawing = False
        self._cached_size = None
        self._icon = QIcon(ICON_DRAW_TOOL)

        # Load brush and size from config
        config = AppConfig()
        cache = Cache()
        self.brush_size = config.get(AppConfig.SKETCH_BRUSH_SIZE)
        self.brush_color = cache.get_color(Cache.LAST_BRUSH_COLOR, Qt.GlobalColor.black)

        def apply_brush_size(size: int) -> None:
            """Update brush size for the canvas and cursor when it changes in config."""
            self.canvas.brush_size = size
            self.update_brush_cursor()
        config.connect(self, AppConfig.SKETCH_BRUSH_SIZE, apply_brush_size)

        def set_brush_color(color_str: str) -> None:
            """Update the brush color within the canvas when it changes in config."""
            color = QColor(color_str)
            self.brush_color = color
        cache.connect(self, Cache.LAST_BRUSH_COLOR, set_brush_color)

        image_stack.active_layer_changed.connect(self._active_layer_change_slot)
        self.layer = image_stack.active_layer

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

    def _stroke_to(self, image_coordinates: QPoint):
        cache = Cache()
        opacity = cache.get(Cache.DRAW_TOOL_OPACITY)
        hardness = cache.get(Cache.DRAW_TOOL_HARDNESS)
        canvas = self.canvas
        assert isinstance(canvas, QtPaintCanvas)
        canvas.opacity = opacity
        canvas.hardness = hardness
        super()._stroke_to(image_coordinates)

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns the brush control panel."""
        if self._control_panel is None:
            self._control_panel = DrawToolPanel()

            def _set_eraser(tool_mode: str) -> None:
                self.canvas.eraser = tool_mode == TOOL_MODE_ERASE
            self._control_panel.tool_mode_changed.connect(_set_eraser)
        return self._control_panel

    def tablet_event(self, event: Optional[QTabletEvent], image_coordinates: QPoint) -> bool:
        """Show pressure toggles and cache tablet data when received."""
        self._control_panel.show_pressure_checkboxes()
        return super().tablet_event(event, image_coordinates)

    def set_brush_size(self, new_size: int) -> None:
        """Update the brush size."""
        new_size = min(new_size, AppConfig().get(AppConfig.SKETCH_BRUSH_SIZE, RangeKey.MAX))
        super().set_brush_size(new_size)
        AppConfig().set(AppConfig.SKETCH_BRUSH_SIZE, max(1, new_size))

    def _active_layer_change_slot(self, active_layer: Layer) -> None:
        if isinstance(active_layer, ImageLayer):
            self.layer = active_layer
        else:
            self.layer = None
