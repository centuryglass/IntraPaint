"""Samples colors within the image, setting brush color."""
from typing import Optional

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QIcon, QCursor, QColor, QMouseEvent, QKeySequence
from PySide6.QtWidgets import QWidget, QColorDialog, QApplication

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.tools.base_tool import BaseTool
from src.ui.panel.color_panel import ColorControlPanel
from src.util.visual.text_drawing_utils import left_button_hint_text
from src.util.shared_constants import PROJECT_DIR

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.eyedropper_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


RESOURCES_EYEDROPPER_ICON = f'{PROJECT_DIR}/resources/icons/tools/eyedropper_icon.svg'
RESOURCES_EYEDROPPER_CURSOR = f'{PROJECT_DIR}/resources/cursors/eyedropper_cursor.svg'
CURSOR_SIZE = 50

EYEDROPPER_LABEL = _tr('Color Picker')
EYEDROPPER_TOOLTIP = _tr('Select a brush color')
EYEDROPPER_CONTROL_HINT = _tr('{left_mouse_icon}: pick color')


class EyedropperTool(BaseTool):
    """Lets the user select colors from the scene or pick a color."""

    def __init__(self, image_stack: ImageStack) -> None:
        super().__init__()
        self._image_stack = image_stack
        self._control_panel: Optional[QColorDialog] = None
        self._icon = QIcon(RESOURCES_EYEDROPPER_ICON)
        cursor_icon = QIcon(RESOURCES_EYEDROPPER_CURSOR)
        self.cursor = QCursor(cursor_icon.pixmap(CURSOR_SIZE, CURSOR_SIZE), 0, CURSOR_SIZE)

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return KeyConfig().get_keycodes(KeyConfig.EYEDROPPER_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return EYEDROPPER_LABEL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return EYEDROPPER_TOOLTIP

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
            color = self._image_stack.get_color_at_point(image_coordinates)
            Cache().set(Cache.LAST_BRUSH_COLOR, color.name(QColor.NameFormat.HexArgb))
            return True
        return False
