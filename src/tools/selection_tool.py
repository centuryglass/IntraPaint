"""Selects image content for image generation or editing."""
from typing import Optional

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent, QIcon, QKeySequence, QColor
from PySide6.QtWidgets import QWidget, QApplication

from src.config.application_config import AppConfig
from src.config.config_entry import RangeKey
from src.config.key_config import KeyConfig
from src.image.canvas.pixmap_layer_canvas import PixmapLayerCanvas
from src.image.layers.image_stack import ImageStack
from src.tools.canvas_tool import CanvasTool
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.canvas_selection_panel import TOOL_MODE_ERASE, CanvasSelectionPanel
from src.util.shared_constants import PROJECT_DIR

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.selection_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


SELECTION_TOOL_LABEL = _tr('Selection')
SELECTION_TOOL_TOOLTIP = _tr('Select areas for editing or inpainting.')
SELECTION_CONTROL_HINT = _tr('LMB:select - RMB:1px select - ')

SELECTION_CONTROL_LAYOUT_SPACING = 4
RESOURCES_PEN_PNG = f'{PROJECT_DIR}/resources/icons/pen_small.svg'
RESOURCES_ERASER_PNG = f'{PROJECT_DIR}/resources/icons/eraser_small.svg'
RESOURCES_SELECTION_CURSOR = f'{PROJECT_DIR}/resources/cursors/selection_cursor.svg'
RESOURCES_SELECTION_ICON = f'{PROJECT_DIR}/resources/icons/tools/selection_icon.svg'


class SelectionTool(CanvasTool):
    """Selects image content for image generation or editing."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        scene = image_viewer.scene()
        assert scene is not None
        super().__init__(image_stack, image_viewer, PixmapLayerCanvas(scene))
        self._last_click = None
        self._control_panel = CanvasSelectionPanel(image_stack.selection_layer)
        self._control_panel.tool_mode_changed.connect(self._tool_toggle_slot)
        self._active = False
        self._drawing = False
        self._cached_size: Optional[int] = None
        self._icon = QIcon(RESOURCES_SELECTION_ICON)
        self.set_scaling_icon_cursor(QIcon(RESOURCES_SELECTION_CURSOR))

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

        self.brush_size = AppConfig().get(AppConfig.SELECTION_BRUSH_SIZE)
        self.layer = image_stack.selection_layer
        self.update_brush_cursor()

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return KeyConfig().get_keycodes(KeyConfig.SELECTION_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return SELECTION_TOOL_LABEL

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        return f'{SELECTION_CONTROL_HINT}{CanvasTool.canvas_control_hints()}{super().get_input_hint()}'

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return SELECTION_TOOL_TOOLTIP

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns the selection control panel."""
        return self._control_panel

    def _tool_toggle_slot(self, selected_tool_label: str):
        """Switches the mask tool between draw and erase modes."""
        self._canvas.eraser = selected_tool_label == TOOL_MODE_ERASE

    def set_brush_size(self, new_size: int) -> None:
        """Update the brush size."""
        new_size = min(new_size, AppConfig().get(AppConfig.SELECTION_BRUSH_SIZE, RangeKey.MAX))
        super().set_brush_size(new_size)
        AppConfig().set(AppConfig.SELECTION_BRUSH_SIZE, max(1, new_size))

    def _on_activate(self) -> None:
        """Override base canvas tool to keep mask layer visible."""
        super()._on_activate()
        layer = self.layer
        if layer is not None:
            self._image_viewer.resume_rendering_layer(layer)

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Hide the mask layer while actively drawing."""
        assert event is not None
        layer = self.layer
        if layer is not None and (event.buttons() == Qt.MouseButton.LeftButton
                                  or event.buttons() == Qt.MouseButton.RightButton):
            self._image_viewer.stop_rendering_layer(layer)
            self._canvas.z_value = 1
        return super().mouse_click(event, image_coordinates)

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Stop hiding the mask layer when done drawing."""
        assert event is not None
        layer = self.layer
        if layer is not None:
            self._image_viewer.resume_rendering_layer(layer)
        return super().mouse_release(event, image_coordinates)
