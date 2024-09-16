"""Control panel for the basic drawing tool."""
from typing import List, Tuple

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QBrush
from PySide6.QtWidgets import QApplication, QHBoxLayout

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.ui.input_fields.dual_toggle import DualToggle
from src.ui.panel.tool_control_panels.canvas_selection_panel import (TOOL_MODE_DRAW, TOOL_MODE_ERASE,
                                                                     RESOURCES_PEN_PNG, RESOURCES_ERASER_PNG)
from src.ui.panel.tool_control_panels.canvas_tool_panel import CanvasToolPanel
from src.ui.widget.key_hint_label import KeyHintLabel

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.draw_tool_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


SELECTION_ONLY_LABEL = _tr('Draw in selection only')

class DrawToolPanel(CanvasToolPanel):
    """Control panel for the basic drawing tool."""

    tool_mode_changed = Signal(str)

    def __init__(self):
        # Set up toggle row before initializing standard canvas tool panel:
        tool_toggle = DualToggle(None, [TOOL_MODE_DRAW, TOOL_MODE_ERASE])
        tool_toggle.set_icons(RESOURCES_PEN_PNG, RESOURCES_ERASER_PNG)
        tool_toggle.setValue(TOOL_MODE_DRAW)
        toggle_hint = KeyHintLabel(config_key=KeyConfig.TOOL_ACTION_HOTKEY)
        def _try_toggle() -> bool:
            if not tool_toggle.isVisible():
                return False
            tool_toggle.toggle()
            return True
        HotkeyFilter.instance().register_config_keybinding(_try_toggle, KeyConfig.TOOL_ACTION_HOTKEY)
        toggle_row = QHBoxLayout()
        toggle_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        toggle_row.addWidget(tool_toggle)
        toggle_row.addWidget(toggle_hint)
        super().__init__(size_key=Cache.DRAW_TOOL_BRUSH_SIZE,
                         pressure_size_key=Cache.DRAW_TOOL_PRESSURE_SIZE,
                         opacity_key=Cache.DRAW_TOOL_OPACITY,
                         pressure_opacity_key=Cache.DRAW_TOOL_PRESSURE_OPACITY,
                         hardness_key=Cache.DRAW_TOOL_HARDNESS,
                         pressure_hardness_key=Cache.DRAW_TOOL_PRESSURE_HARDNESS,
                         color_key=Cache.LAST_BRUSH_COLOR,
                         pattern_key=Cache.DRAW_TOOL_BRUSH_PATTERN,
                         selection_only_label=SELECTION_ONLY_LABEL,
                         added_rows=[toggle_row])
        tool_toggle.valueChanged.connect(self.tool_mode_changed)
