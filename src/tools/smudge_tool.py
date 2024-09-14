"""Implements image smudging using a restricted BrushTool."""
from typing import Optional

from PySide6.QtGui import QIcon, QKeySequence, Qt
from PySide6.QtWidgets import QApplication, QWidget

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.tools.canvas_tool import CanvasTool
from src.ui.image_viewer import ImageViewer
from src.util.optional_import import optional_import
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text

BrushTool = optional_import('src.tools.brush_tool', attr_name='BrushTool')
assert BrushTool is not None

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.smudge_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


RESOURCES_SMUDGE_BRUSH = f'{PROJECT_DIR}/resources/brushes/classic/smudge.myb'
RESOURCES_SMUDGE_ICON = f'{PROJECT_DIR}/resources/icons/tools/smudge_icon.svg'
SMUDGE_LABEL = _tr('Smudge')
SMUDGE_TOOLTIP = _tr('Smudge image content')
SMUDGE_CONTROL_HINT = _tr('{left_mouse_icon}: smudge - {right_mouse_icon}: 1px smudge')


class SmudgeTool(BrushTool):  # type: ignore
    """Implements image smudging using a restricted BrushTool."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        super().__init__(image_stack, image_viewer)
        Cache().disconnect(self, Cache.MYPAINT_BRUSH)
        Cache().disconnect(self, Cache.LAST_BRUSH_COLOR)
        self.brush_color = Qt.GlobalColor.black
        self.brush_path = RESOURCES_SMUDGE_BRUSH
        self._icon = QIcon(RESOURCES_SMUDGE_ICON)

    # noinspection PyMethodMayBeStatic
    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return KeyConfig().get_keycodes(KeyConfig.SMUDGE_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    # noinspection PyMethodMayBeStatic
    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return SMUDGE_LABEL

    # noinspection PyMethodMayBeStatic
    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return SMUDGE_TOOLTIP

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        brush_hint = SMUDGE_CONTROL_HINT.format(left_mouse_icon=left_button_hint_text(),
                                                right_mouse_icon=right_button_hint_text())
        return f'{brush_hint}<br/>{CanvasTool.canvas_control_hints()}<br/>{CanvasTool.get_input_hint(self)}'

    # noinspection PyMethodMayBeStatic
    def get_control_panel(self) -> Optional[QWidget]:
        """Returns the blur tool control panel."""
        return None
