"""Selection panel for the SelectionBrushTool class."""
from typing import cast, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.selection_layer import SelectionLayer
from src.tools.base_tool import BaseTool
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox
from src.ui.panel.tool_control_panels.selection_panel import SelectionPanel
from src.ui.widget.key_hint_label import KeyHintLabel
from src.util.visual.selection_mode import SelectionModifiers

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.brush_selection_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


SELECTION_SIZE_SHORT_LABEL = _tr('Size:')
# Also used by the draw tool's mode toggle:
TOOL_MODE_SELECT = _tr('Select')
TOOL_MODE_DESELECT = _tr('Deselect')


class BrushSelectionPanel(SelectionPanel):
    """Selection panel for the SelectionBrushTool class."""

    def __init__(self, selection_layer: SelectionLayer, selection_tool: BaseTool) -> None:
        super().__init__(selection_layer, selection_tool, toggle_hotkey=True,
                         modifiers=SelectionModifiers.BRUSH)

        # Brush size:
        size_row = QHBoxLayout()
        size_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        size_label = QLabel(SELECTION_SIZE_SHORT_LABEL)
        size_row.addWidget(size_label)
        size_down_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_SIZE_DECREASE, parent=self)
        size_row.addWidget(size_down_hint)
        brush_size_slider = cast(IntSliderSpinbox, Cache().get_control_widget(Cache.SELECTION_BRUSH_SIZE))
        size_row.addWidget(brush_size_slider)
        size_up_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_SIZE_INCREASE, parent=self)
        size_row.addWidget(size_up_hint)
        self.insert_into_layout(size_row)
