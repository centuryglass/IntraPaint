"""Add text to an image."""
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QIcon, QCursor, QMouseEvent, QKeySequence, QColor, QPainter, QTransform
from PySide6.QtWidgets import QWidget, QFormLayout, QApplication

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.tools.base_tool import BaseTool
from src.tools.brush_tool import COLOR_PICK_HINT
from src.ui.panel.tool_control_panels.text_tool_panel import TextToolPanel
from src.ui.widget.brush_color_button import BrushColorButton
from src.util.image_utils import flood_fill, create_transparent_image
from src.util.shared_constants import PROJECT_DIR

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.text_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


RESOURCES_TEXT_ICON = f'{PROJECT_DIR}/resources/icons/tools/text_icon.svg'
CURSOR_SIZE = 50

TEXT_LABEL = _tr('Text')
TEXT_TOOLTIP = _tr('Add text to a text layer')
TEXT_CONTROL_HINT = _tr('TODO: text controls')


class TextTool(BaseTool):
    """Lets the user fill image areas with solid colors."""

    def __init__(self, image_stack: ImageStack) -> None:
        super().__init__()
        self._control_panel = TextToolPanel()
        self._image_stack = image_stack
        self._icon = QIcon(RESOURCES_TEXT_ICON)

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return KeyConfig().get_keycodes(KeyConfig.TEXT_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return TEXT_LABEL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return TEXT_TOOLTIP

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        return (f'{TEXT_CONTROL_HINT}'
                f'{super().get_input_hint()}')

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        return self._control_panel
