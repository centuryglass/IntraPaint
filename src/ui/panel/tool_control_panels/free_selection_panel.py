"""Selection panel for the FreeSelectionTool class."""
from src.image.layers.selection_layer import SelectionLayer
from src.tools.base_tool import BaseTool
from src.ui.panel.tool_control_panels.selection_panel import SelectionPanel


class FreeSelectionPanel(SelectionPanel):
    """Selection panel for the FreeSelectionTool class."""

    def __init__(self, selection_layer: SelectionLayer, selection_tool: BaseTool) -> None:
        super().__init__(selection_layer, selection_tool, toggle_hotkey=True)
