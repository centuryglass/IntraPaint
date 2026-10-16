"""Control panel for the basic drawing tool."""
from src.config.cache import Cache
from src.ui.panel.tool_control_panels.stroke_block import StrokeBlock, StrokeToolPanel


class DrawToolPanel(StrokeToolPanel):
    """Control panel for the basic drawing tool: the stroke block with the color pair and Pattern."""

    def __init__(self):
        super().__init__(StrokeBlock(size_key=Cache.DRAW_TOOL_BRUSH_SIZE,
                                     pressure_size_key=Cache.DRAW_TOOL_PRESSURE_SIZE,
                                     opacity_key=Cache.DRAW_TOOL_OPACITY,
                                     pressure_opacity_key=Cache.DRAW_TOOL_PRESSURE_OPACITY,
                                     hardness_key=Cache.DRAW_TOOL_HARDNESS,
                                     pressure_hardness_key=Cache.DRAW_TOOL_PRESSURE_HARDNESS,
                                     color_key=Cache.LAST_BRUSH_COLOR,
                                     pattern_key=Cache.DRAW_TOOL_BRUSH_PATTERN,
                                     antialias_key=Cache.DRAW_TOOL_ANTIALIAS,
                                     show_preview=True))
