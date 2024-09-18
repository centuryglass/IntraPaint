"""Implements drawing controls using a minimal QPainter-based canvas."""
from typing import Optional

from PySide6.QtGui import QIcon, QKeySequence
from PySide6.QtWidgets import QWidget, QApplication

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.tools.base_tool import BaseTool
from src.tools.canvas_tool import CanvasTool
from src.tools.qt_paint_canvas_tool import QtPaintCanvasTool
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.brush_selection_panel import TOOL_MODE_ERASE
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


class DrawTool(QtPaintCanvasTool):
    """Implements brush controls using a minimal QPainter-based brush engine."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        super().__init__(image_stack, image_viewer, size_key=Cache.DRAW_TOOL_BRUSH_SIZE,
                         pressure_size_key=Cache.DRAW_TOOL_PRESSURE_SIZE, opacity_key=Cache.DRAW_TOOL_OPACITY,
                         pressure_opacity_key=Cache.DRAW_TOOL_PRESSURE_OPACITY,
                         hardness_key=Cache.DRAW_TOOL_HARDNESS, pressure_hardness_key=Cache.DRAW_TOOL_PRESSURE_HARDNESS,
                         color_key=Cache.LAST_BRUSH_COLOR, pattern_key=Cache.DRAW_TOOL_BRUSH_PATTERN)
        self._control_panel: Optional[DrawToolPanel] = None
        self._icon = QIcon(ICON_DRAW_TOOL)

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
