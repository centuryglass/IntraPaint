"""Control panel for the basic eraser tool."""

from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.ui.panel.tool_control_panels.brush_tool_panel import BrushToolPanel

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.eraser_tool_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


SELECTION_ONLY_LABEL = _tr('Erase in selection only')


class EraserToolPanel(BrushToolPanel):
    """Control panel for the eraser tool."""
    def __init__(self):
        super().__init__(size_key=Cache.ERASER_TOOL_SIZE,
                         pressure_size_key=Cache.ERASER_TOOL_PRESSURE_SIZE,
                         opacity_key=Cache.ERASER_TOOL_OPACITY,
                         pressure_opacity_key=Cache.ERASER_TOOL_PRESSURE_OPACITY,
                         hardness_key=Cache.ERASER_TOOL_HARDNESS,
                         pressure_hardness_key=Cache.ERASER_TOOL_PRESSURE_HARDNESS,
                         selection_only_label=SELECTION_ONLY_LABEL)
