"""Control panel widget for the smudge tool."""

from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.ui.panel.tool_control_panels.canvas_tool_panel import CanvasToolPanel

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.smudge_tool_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


SELECTION_ONLY_LABEL = _tr('Edit selection only')


class SmudgeToolPanel(CanvasToolPanel):
    """Control panel widget for the blur tool."""

    def __init__(self):
        super().__init__(size_key=Cache.SMUDGE_TOOL_BRUSH_SIZE,
                         pressure_size_key=Cache.SMUDGE_TOOL_PRESSURE_SIZE,
                         opacity_key=Cache.SMUDGE_TOOL_OPACITY,
                         pressure_opacity_key=Cache.SMUDGE_TOOL_PRESSURE_OPACITY,
                         hardness_key=Cache.SMUDGE_TOOL_HARDNESS,
                         pressure_hardness_key=Cache.SMUDGE_TOOL_PRESSURE_HARDNESS,
                         selection_only_label=SELECTION_ONLY_LABEL)
