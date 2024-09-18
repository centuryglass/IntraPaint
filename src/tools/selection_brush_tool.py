"""Selects image content for image generation or editing."""
from typing import Optional

from PySide6.QtGui import QIcon, QKeySequence, QColor
from PySide6.QtWidgets import QWidget, QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.config_entry import RangeKey
from src.config.key_config import KeyConfig
from src.image.canvas.qt_paint_canvas import QtPaintCanvas
from src.image.layers.image_stack import ImageStack
from src.tools.canvas_tool import CanvasTool
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.brush_selection_panel import TOOL_MODE_ERASE, BrushSelectionPanel
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text
from src.util.shared_constants import PROJECT_DIR

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.selection_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


LABEL_TEXT_SELECTION_TOOL = _tr('Selection Brush')
TOOLTIP_SELECTION_TOOL = _tr('Draw to select areas for editing or inpainting.')
CONTROL_HINT_SELECTION_TOOL = _tr('{left_mouse_icon}: select - {right_mouse_icon}:1px select')

CURSOR_SELECTION_TOOL = f'{PROJECT_DIR}/resources/cursors/selection_cursor.svg'
ICON_SELECTION_TOOL = f'{PROJECT_DIR}/resources/icons/tools/selection_icon.svg'


class SelectionBrushTool(CanvasTool):
    """Selects image content for image generation or editing."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        canvas = QtPaintCanvas(None)
        super().__init__(image_stack, image_viewer, canvas, False, False)
        self._last_click = None
        self._control_panel = BrushSelectionPanel(image_stack.selection_layer)
        self._control_panel.tool_mode_changed.connect(self._tool_toggle_slot)
        self._active = False
        self._drawing = False
        self._cached_size: Optional[int] = None
        self._icon = QIcon(ICON_SELECTION_TOOL)
        self.set_scaling_icon_cursor(QIcon(CURSOR_SELECTION_TOOL))

        # Setup brush, load size from config
        self.brush_color = QColor()

        def _update_color(color_str: str) -> None:
            if color_str == self.brush_color.name():
                return
            color = QColor(color_str)
            color.setAlphaF(1.0)
            self.brush_color = color
        _update_color(AppConfig().get(AppConfig.SELECTION_COLOR))
        AppConfig().connect(self, AppConfig.SELECTION_COLOR, _update_color)

        self.brush_size = Cache().get(Cache.SELECTION_BRUSH_SIZE)
        self.layer = image_stack.selection_layer
        self.update_brush_cursor()

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return KeyConfig().get_keycodes(KeyConfig.SELECTION_BRUSH_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return LABEL_TEXT_SELECTION_TOOL

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        select_hint = CONTROL_HINT_SELECTION_TOOL.format(left_mouse_icon=left_button_hint_text(),
                                                         right_mouse_icon=right_button_hint_text())
        return f'{select_hint}<br/>{CanvasTool.canvas_control_hints()}<br/>{super().get_input_hint()}'

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return TOOLTIP_SELECTION_TOOL

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns the selection control panel."""
        return self._control_panel

    def _tool_toggle_slot(self, selected_tool_label: str):
        """Switches the mask tool between draw and erase modes."""
        self._canvas.eraser = selected_tool_label == TOOL_MODE_ERASE

    def set_brush_size(self, new_size: int) -> None:
        """Update the brush size."""
        new_size = min(new_size, Cache().get(Cache.SELECTION_BRUSH_SIZE, RangeKey.MAX))
        super().set_brush_size(new_size)
        Cache().set(Cache.SELECTION_BRUSH_SIZE, max(1, new_size))
