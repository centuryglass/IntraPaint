"""Control panel for the basic drawing tool."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.ui.panel.tool_control_panels.brush_tool_panel import BrushToolPanel

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.draw_tool_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


SELECTION_ONLY_LABEL = _tr('Draw in selection only')


class DrawToolPanel(BrushToolPanel):
    """Control panel for the basic drawing tool."""

    tool_mode_changed = Signal(str)

    def __init__(self):
        super().__init__(size_key=Cache.DRAW_TOOL_BRUSH_SIZE,
                         pressure_size_key=Cache.DRAW_TOOL_PRESSURE_SIZE,
                         opacity_key=Cache.DRAW_TOOL_OPACITY,
                         pressure_opacity_key=Cache.DRAW_TOOL_PRESSURE_OPACITY,
                         hardness_key=Cache.DRAW_TOOL_HARDNESS,
                         pressure_hardness_key=Cache.DRAW_TOOL_PRESSURE_HARDNESS,
                         color_key=Cache.LAST_BRUSH_COLOR,
                         pattern_key=Cache.DRAW_TOOL_BRUSH_PATTERN,
                         selection_only_label=SELECTION_ONLY_LABEL)
