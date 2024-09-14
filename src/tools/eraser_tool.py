"""Draw tool variant meant for erasing only."""
from typing import Optional

from PySide6.QtCore import QPoint
from PySide6.QtGui import QIcon, QKeySequence
from PySide6.QtWidgets import QApplication, QWidget

from src.config.cache import Cache
from src.config.config_entry import RangeKey
from src.config.key_config import KeyConfig
from src.image.canvas.qt_paint_canvas import QtPaintCanvas
from src.image.layers.image_stack import ImageStack
from src.tools.canvas_tool import CanvasTool
from src.tools.draw_tool import DrawTool
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.eraser_tool_panel import EraserToolPanel
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.eraser_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


ICON_ERASER_TOOL = f'{PROJECT_DIR}/resources/icons/tools/eraser_icon.svg'
LABEL_TEXT_ERASER_TOOL = _tr('Erase')
TOOLTIP_ERASER_TOOL = _tr('Erase image layer content')
CONTROL_HINT_DRAW_TOOL = _tr('{left_mouse_icon}: erase - {right_mouse_icon}: 1px erase')


class EraserTool(DrawTool):
    """Draw tool variant meant for erasing only."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        super().__init__(image_stack, image_viewer, size_key=Cache.ERASER_TOOL_SIZE,
                         pressure_size_key=Cache.ERASER_TOOL_PRESSURE_SIZE, opacity_key=Cache.ERASER_TOOL_OPACITY,
                         pressure_opacity_key=Cache.DRAW_TOOL_PRESSURE_OPACITY,
                         hardness_key=Cache.ERASER_TOOL_HARDNESS,
                         pressure_hardness_key=Cache.ERASER_TOOL_PRESSURE_HARDNESS)
        self.canvas.eraser = True

        cache = Cache()
        cache.disconnect(self, Cache.LAST_BRUSH_COLOR)
        self._icon = QIcon(ICON_ERASER_TOOL)
        self._control_panel: Optional[EraserToolPanel] = None

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns the brush control panel."""
        if self._control_panel is None:
            self._control_panel = EraserToolPanel()
        return self._control_panel

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return KeyConfig().get_keycodes(KeyConfig.ERASER_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return LABEL_TEXT_ERASER_TOOL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return TOOLTIP_ERASER_TOOL

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        control_hint_draw_tool = CONTROL_HINT_DRAW_TOOL.format(left_mouse_icon=left_button_hint_text(),
                                                               right_mouse_icon=right_button_hint_text(),
                                                               modifier_or_modifiers='{modifier_or_modifiers}')
        return (f'{control_hint_draw_tool}<br/>{CanvasTool.canvas_control_hints()}'
                f'<br/>{CanvasTool.get_input_hint(self)}')

    def set_brush_size(self, new_size: int) -> None:
        """Update the eraser size."""
        new_size = min(new_size, Cache().get(Cache.ERASER_TOOL_SIZE, RangeKey.MAX))
        super().set_brush_size(new_size)
        Cache().set(Cache.ERASER_TOOL_SIZE, max(1, new_size))

    def _stroke_to(self, image_coordinates: QPoint):
        cache = Cache()
        opacity = cache.get(Cache.ERASER_TOOL_OPACITY)
        hardness = cache.get(Cache.ERASER_TOOL_HARDNESS)
        canvas = self.canvas
        assert isinstance(canvas, QtPaintCanvas)
        canvas.opacity = opacity
        canvas.hardness = hardness
        super()._stroke_to(image_coordinates)
