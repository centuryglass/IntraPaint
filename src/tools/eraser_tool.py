"""Draw tool variant meant for erasing only."""
from typing import Optional

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.tools.brush_tool import BrushTool
from src.tools.qt_paint_brush_tool import QtPaintBrushTool
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.eraser_tool_panel import EraserToolPanel
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.eraser_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


ICON_PATH_ERASER_TOOL = f'{PROJECT_DIR}/resources/icons/tools/eraser_icon.svg'
CURSOR_PATH_ERASER_TOOL = f'{PROJECT_DIR}/resources/cursors/eraser_cursor.svg'
LABEL_TEXT_ERASER_TOOL = _tr('Erase')
TOOLTIP_ERASER_TOOL = _tr('Erase image layer content')
CONTROL_HINT_DRAW_TOOL = _tr('{left_mouse_icon}: erase - {right_mouse_icon}: 1px erase')


class EraserTool(QtPaintBrushTool):
    """Draw tool variant meant for erasing only."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        super().__init__(KeyConfig.ERASER_TOOL_KEY, LABEL_TEXT_ERASER_TOOL, TOOLTIP_ERASER_TOOL,
                         QIcon(ICON_PATH_ERASER_TOOL), image_stack, image_viewer, size_key=Cache.ERASER_TOOL_SIZE,
                         pressure_size_key=Cache.ERASER_TOOL_PRESSURE_SIZE, opacity_key=Cache.ERASER_TOOL_OPACITY,
                         pressure_opacity_key=Cache.ERASER_TOOL_PRESSURE_OPACITY,
                         hardness_key=Cache.ERASER_TOOL_HARDNESS, antialias_key=Cache.ERASER_TOOL_ANTIALIAS,
                         pressure_hardness_key=Cache.ERASER_TOOL_PRESSURE_HARDNESS)
        self.brush.eraser = True

        cache = Cache()
        cache.disconnect(self, Cache.LAST_BRUSH_COLOR)
        self._control_panel: Optional[EraserToolPanel] = None
        self.set_scaling_icon_cursor(QIcon(CURSOR_PATH_ERASER_TOOL))

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns the brush control panel."""
        if self._control_panel is None:
            self._control_panel = EraserToolPanel()
        return self._control_panel

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        control_hint_draw_tool = CONTROL_HINT_DRAW_TOOL.format(left_mouse_icon=left_button_hint_text(),
                                                               right_mouse_icon=right_button_hint_text(),
                                                               modifier_or_modifiers='{modifier_or_modifiers}')
        return (f'{control_hint_draw_tool}<br/>{BrushTool.brush_control_hints()}'
                f'<br/>{BrushTool.get_input_hint(self)}')
