"""Selection panel for the FreeSelectionTool class."""
from typing import Optional

from PySide6.QtWidgets import QApplication, QLabel

from src.image.layers.selection_layer import SelectionLayer
from src.tools.base_tool import BaseTool
from src.ui.panel.tool_control_panels.selection_panel import SelectionPanel
from src.ui.panel.tool_control_panels.stroke_block import tool_section

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.free_selection_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


FREE_SECTION_TITLE = _tr('Free selection')
FREE_SECTION_HINT = _tr('Click adds a point. Enter closes the shape and applies it.')


class FreeSelectionPanel(SelectionPanel):
    """Selection panel for the FreeSelectionTool class: Mode, one line of instructions, then Selection."""

    def __init__(self, selection_layer: SelectionLayer, selection_tool: BaseTool) -> None:
        super().__init__(selection_layer, selection_tool)
        hint = QLabel(FREE_SECTION_HINT)
        hint.setWordWrap(True)
        self.insert_into_layout(tool_section(FREE_SECTION_TITLE, hint))
