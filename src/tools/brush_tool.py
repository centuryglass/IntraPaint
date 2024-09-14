"""Implements brush controls using a MyPaint surface."""
import logging
import os
from typing import Optional

from PySide6.QtGui import QColor, QIcon, QKeySequence, Qt
from PySide6.QtWidgets import QWidget, QApplication

from src.config.cache import Cache
from src.config.config_entry import RangeKey
from src.config.key_config import KeyConfig
from src.image.canvas.mypaint_canvas import MyPaintLayerCanvas
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.tools.base_tool import BaseTool
from src.tools.canvas_tool import CanvasTool
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.brush_control_panel import BrushControlPanel
from src.util.shared_constants import PROJECT_DIR, COLOR_PICK_HINT
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.brush_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


RESOURCES_BRUSH_ICON = f'{PROJECT_DIR}/resources/icons/tools/brush_icon.svg'
BRUSH_LABEL = _tr('Brush')
BRUSH_TOOLTIP = _tr('Paint into the image')
BRUSH_CONTROL_HINT = _tr('{left_mouse_icon}: draw - {right_mouse_icon}: 1px draw')


class BrushTool(CanvasTool):
    """Implements brush controls using a MyPaint surface."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        super().__init__(image_stack, image_viewer, MyPaintLayerCanvas())
        self._last_click = None
        self._control_panel: Optional[BrushControlPanel] = None
        self._active = False
        self._drawing = False
        self._cached_size = None
        self._icon = QIcon(RESOURCES_BRUSH_ICON)

        # Load brush and size from cache
        cache = Cache()
        self.brush_path = cache.get(Cache.MYPAINT_BRUSH)
        self.brush_size = cache.get(Cache.PAINT_TOOL_BRUSH_SIZE)
        self.brush_color = cache.get_color(Cache.LAST_BRUSH_COLOR, Qt.GlobalColor.black)

        def apply_brush_size(size: int) -> None:
            """Update brush size for the canvas and cursor when it changes in config."""
            self._canvas.brush_size = size
            self.update_brush_cursor()
        cache.connect(self, Cache.PAINT_TOOL_BRUSH_SIZE, apply_brush_size)

        def set_brush_color(color_str: str) -> None:
            """Update the brush color within the canvas when it changes in config."""
            color = QColor(color_str)
            self.brush_color = color
        cache.connect(self, Cache.LAST_BRUSH_COLOR, set_brush_color)

        def set_active_brush(brush_path: str) -> None:
            """Update the active MyPaint brush when it changes in config."""
            self.brush_path = brush_path
        cache.connect(self, Cache.MYPAINT_BRUSH, set_active_brush)

        image_stack.active_layer_changed.connect(self._active_layer_change_slot)
        self.layer = image_stack.active_layer

        self.update_brush_cursor()

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return KeyConfig().get_keycodes(KeyConfig.BRUSH_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return BRUSH_LABEL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return BRUSH_TOOLTIP

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        brush_hint = BRUSH_CONTROL_HINT.format(left_mouse_icon=left_button_hint_text(),
                                               right_mouse_icon=right_button_hint_text())
        eyedropper_hint = BaseTool.modifier_hint(KeyConfig.EYEDROPPER_OVERRIDE_MODIFIER, COLOR_PICK_HINT)
        if len(eyedropper_hint) > 0:
            eyedropper_hint = ' - ' + eyedropper_hint
        return f'{brush_hint}{eyedropper_hint}<br/>{CanvasTool.canvas_control_hints()}<br/>{super().get_input_hint()}'

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns the brush control panel."""
        if self._control_panel is None:
            self._control_panel = BrushControlPanel()
        return self._control_panel

    @property
    def brush_path(self) -> Optional[str]:
        """Gets the active brush file path, if any."""
        canvas = self.canvas
        assert isinstance(canvas, MyPaintLayerCanvas)
        return canvas.brush_path

    @brush_path.setter
    def brush_path(self, new_path: str) -> None:
        """Updates the active brush size."""
        canvas = self.canvas
        assert isinstance(canvas, MyPaintLayerCanvas)
        try:
            if not os.path.isfile(new_path):
                resource_path = f'{PROJECT_DIR}/new_path'
                if os.path.isfile(resource_path):
                    new_path = resource_path
                else:
                    raise RuntimeError('Brush file does not exist')
            canvas.brush_path = new_path
        except (OSError, RuntimeError) as err:
            logger.error(f'loading brush {new_path} failed', err)

    def set_brush_size(self, new_size: int) -> None:
        """Update the brush size."""
        new_size = min(new_size, Cache().get(Cache.PAINT_TOOL_BRUSH_SIZE, RangeKey.MAX))
        super().set_brush_size(new_size)
        Cache().set(Cache.PAINT_TOOL_BRUSH_SIZE, max(1, new_size))

    def _active_layer_change_slot(self, active_layer: Layer) -> None:
        if isinstance(active_layer, ImageLayer):
            self.layer = active_layer
        else:
            self.layer = None
