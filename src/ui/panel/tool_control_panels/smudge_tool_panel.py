"""Control panel widget for the smudge tool."""
from typing import Optional

from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.ui.panel.tool_control_panels.stroke_block import StrokeBlock, StrokeToolPanel

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.smudge_tool_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


STRENGTH_LABEL = _tr('Strength')
STRENGTH_TOOLTIP = _tr('How far the smudge carries color')


class SmudgeToolPanel(StrokeToolPanel):
    """Control panel widget for the smudge tool: the stroke block without a color row, with Opacity read as
    Strength."""

    def __init__(self):
        super().__init__(StrokeBlock(size_key=Cache.SMUDGE_TOOL_BRUSH_SIZE,
                                     pressure_size_key=Cache.SMUDGE_TOOL_PRESSURE_SIZE,
                                     opacity_key=Cache.SMUDGE_TOOL_OPACITY,
                                     opacity_label=STRENGTH_LABEL,
                                     opacity_tooltip=STRENGTH_TOOLTIP,
                                     pressure_opacity_key=Cache.SMUDGE_TOOL_PRESSURE_OPACITY,
                                     hardness_key=Cache.SMUDGE_TOOL_HARDNESS,
                                     pressure_hardness_key=Cache.SMUDGE_TOOL_PRESSURE_HARDNESS,
                                     antialias_key=Cache.SMUDGE_TOOL_ANTIALIAS))
