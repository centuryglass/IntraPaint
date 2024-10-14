"""Samples colors within the image, setting brush color."""
from typing import Optional

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QIcon, QCursor, QColor, QMouseEvent
from PySide6.QtWidgets import QWidget, QColorDialog, QApplication

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.image.layers.image_stack_utils import image_stack_color_at_point
from src.tools.base_tool import BaseTool
from src.ui.panel.color_panel import ColorControlPanel
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.text_drawing_utils import left_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.eyedropper_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


ICON_PATH_EYEDROPPER_TOOL = f'{PROJECT_DIR}/resources/icons/tools/eyedropper_icon.svg'
CURSOR_PATH_EYEDROPPER_TOOL = f'{PROJECT_DIR}/resources/cursors/eyedropper_cursor.svg'
CURSOR_SIZE = 50

EYEDROPPER_LABEL = _tr('Color Picker')
EYEDROPPER_TOOLTIP = _tr('Select a brush color')
EYEDROPPER_CONTROL_HINT = _tr('{left_mouse_icon}: pick color - ')


class EyedropperTool(BaseTool):
    """Lets the user select colors from the scene or pick a color."""

    def __init__(self, image_stack: ImageStack) -> None:
        super().__init__(KeyConfig.EYEDROPPER_TOOL_KEY, EYEDROPPER_LABEL, EYEDROPPER_TOOLTIP,
                         QIcon(ICON_PATH_EYEDROPPER_TOOL))
        self._image_stack = image_stack
        self._control_panel: Optional[QColorDialog] = None
        cursor_icon = QIcon(CURSOR_PATH_EYEDROPPER_TOOL)
        self.cursor = QCursor(cursor_icon.pixmap(CURSOR_SIZE, CURSOR_SIZE), 0, CURSOR_SIZE)

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        eyedropper_hint = EYEDROPPER_CONTROL_HINT.format(left_mouse_icon=left_button_hint_text())
        return f'{eyedropper_hint}</br>{super().get_input_hint()}'

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        if self._control_panel is not None:
            return self._control_panel
        self._control_panel = ColorControlPanel()
        return self._control_panel

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Copy the color under the mouse on left-click."""
        assert event is not None
        if event.buttons() == Qt.MouseButton.LeftButton:
            color = image_stack_color_at_point(self._image_stack, image_coordinates)
            Cache().set(Cache.LAST_BRUSH_COLOR, color.name(QColor.NameFormat.HexArgb))
            return True
        return False
