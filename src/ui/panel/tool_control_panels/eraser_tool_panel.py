"""Control panel for the basic eraser tool."""
from typing import Optional

from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.ui.panel.tool_control_panels.stroke_block import StrokeBlock, StrokeToolPanel

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.eraser_tool_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


# Matches the Size field in every other stroke block, so it stays put when switching tools:
_SIZE_LABEL = _tr('Size')


class EraserToolPanel(StrokeToolPanel):
    """Control panel for the eraser tool: the stroke block without a color row, and a preview of erasing."""

    def __init__(self):
        super().__init__(StrokeBlock(size_key=Cache.ERASER_TOOL_SIZE,
                                     size_label=_SIZE_LABEL,
                                     pressure_size_key=Cache.ERASER_TOOL_PRESSURE_SIZE,
                                     opacity_key=Cache.ERASER_TOOL_OPACITY,
                                     pressure_opacity_key=Cache.ERASER_TOOL_PRESSURE_OPACITY,
                                     hardness_key=Cache.ERASER_TOOL_HARDNESS,
                                     pressure_hardness_key=Cache.ERASER_TOOL_PRESSURE_HARDNESS,
                                     antialias_key=Cache.ERASER_TOOL_ANTIALIAS,
                                     show_preview=True,
                                     erase_preview=True))
