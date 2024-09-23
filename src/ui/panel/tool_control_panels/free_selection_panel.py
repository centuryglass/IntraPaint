"""Selection panel for the FreeSelectionTool class."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout

from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.layers.selection_layer import SelectionLayer
from src.ui.input_fields.dual_toggle import DualToggle
from src.ui.layout.divider import Divider
from src.ui.panel.tool_control_panels.brush_selection_panel import TOOL_MODE_SELECT, TOOL_MODE_DESELECT
from src.ui.panel.tool_control_panels.selection_panel import SelectionPanel
from src.ui.widget.key_hint_label import KeyHintLabel
from src.util.shared_constants import PROJECT_DIR


ICON_PATH_SELECT = f'{PROJECT_DIR}/resources/icons/tool_modes/select.svg'
ICON_PATH_DESELECT = f'{PROJECT_DIR}/resources/icons/tool_modes/clear.svg'


class FreeSelectionPanel(SelectionPanel):
    """Selection panel for the FreeSelectionTool class."""

    tool_mode_changed = Signal(str)

    def __init__(self, selection_layer: SelectionLayer) -> None:
        super().__init__(selection_layer)

        # Draw/erase toggle:

        toggle_row = QHBoxLayout()
        toggle_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        tool_toggle = DualToggle(self, [TOOL_MODE_SELECT, TOOL_MODE_DESELECT])
        tool_toggle.set_icons(ICON_PATH_SELECT, ICON_PATH_DESELECT)
        tool_toggle.setValue(TOOL_MODE_SELECT)
        tool_toggle.valueChanged.connect(self.tool_mode_changed)
        toggle_row.addWidget(tool_toggle)

        toggle_hint = KeyHintLabel(config_key=KeyConfig.TOOL_ACTION_HOTKEY, parent=self)
        toggle_row.addWidget(toggle_hint)
        self.insert_into_layout(toggle_row)
        self.insert_into_layout(Divider(Qt.Orientation.Horizontal))

        def _try_toggle() -> bool:
            if not tool_toggle.isVisible():
                return False
            tool_toggle.toggle()
            return True
        binding_id = f'FreeSelectionPanel_{id(self)}_try_toggle'
        HotkeyFilter.instance().register_config_keybinding(binding_id, _try_toggle, KeyConfig.TOOL_ACTION_HOTKEY)
