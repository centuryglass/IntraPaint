"""Selection panel for the SelectionBrushTool class."""
from typing import cast

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.layers.selection_layer import SelectionLayer
from src.ui.input_fields.dual_toggle import DualToggle
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox
from src.ui.layout.divider import Divider
from src.ui.panel.tool_control_panels.selection_panel import SelectionPanel
from src.ui.widget.key_hint_label import KeyHintLabel
from src.util.shared_constants import PROJECT_DIR

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.brush_selection_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


SELECTION_SIZE_SHORT_LABEL = _tr('Size:')
TOOL_MODE_DRAW = _tr('Draw')
TOOL_MODE_ERASE = _tr('Erase')
CLEAR_BUTTON_LABEL = _tr('Clear')
FILL_BUTTON_LABEL = _tr('Fill')

RESOURCES_PEN_PNG = f'{PROJECT_DIR}/resources/icons/pen_small.svg'
RESOURCES_ERASER_PNG = f'{PROJECT_DIR}/resources/icons/eraser_small.svg'


class BrushSelectionPanel(SelectionPanel):
    """Selection panel for the SelectionBrushTool class."""

    tool_mode_changed = Signal(str)

    def __init__(self, selection_layer: SelectionLayer) -> None:
        super().__init__(selection_layer)

        # Brush size:
        size_row = QHBoxLayout()
        size_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        size_label = QLabel(SELECTION_SIZE_SHORT_LABEL)
        size_row.addWidget(size_label)
        size_down_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_SIZE_DECREASE)
        size_row.addWidget(size_down_hint)
        brush_size_slider = cast(IntSliderSpinbox, Cache().get_control_widget(Cache.SELECTION_BRUSH_SIZE))
        size_row.addWidget(brush_size_slider)
        size_up_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_SIZE_INCREASE)
        size_row.addWidget(size_up_hint)
        self.insert_into_layout(size_row)

        # Draw/erase toggle:

        toggle_row = QHBoxLayout()
        toggle_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        tool_toggle = DualToggle(self, [TOOL_MODE_DRAW, TOOL_MODE_ERASE])
        tool_toggle.set_icons(RESOURCES_PEN_PNG, RESOURCES_ERASER_PNG)
        tool_toggle.setValue(TOOL_MODE_DRAW)
        tool_toggle.valueChanged.connect(self.tool_mode_changed)
        toggle_row.addWidget(tool_toggle)

        toggle_hint = KeyHintLabel(config_key=KeyConfig.TOOL_ACTION_HOTKEY)
        toggle_row.addWidget(toggle_hint)
        self.insert_into_layout(toggle_row)
        self.insert_into_layout(Divider(Qt.Orientation.Horizontal))

        def _try_toggle() -> bool:
            if not tool_toggle.isVisible():
                return False
            tool_toggle.toggle()
            return True
        binding_id = f'BrushSelectionPanel_{id(self)}_try_toggle'
        HotkeyFilter.instance().register_config_keybinding(binding_id, _try_toggle, KeyConfig.TOOL_ACTION_HOTKEY)
