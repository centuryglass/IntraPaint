"""Selection panel for the ShapeSelectionTool class."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout

from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.layers.selection_layer import SelectionLayer
from src.ui.graphics_items.click_and_drag_selection import SELECTION_MODE_RECT, SELECTION_MODE_ELLIPSE
from src.ui.input_fields.dual_toggle import DualToggle
from src.ui.layout.divider import Divider
from src.ui.panel.tool_control_panels.selection_panel import SelectionPanel
from src.ui.widget.key_hint_label import KeyHintLabel


class ShapeSelectionPanel(SelectionPanel):
    """Selection panel for the SelectionFillTool class."""

    tool_mode_changed = Signal(str)

    def __init__(self, selection_layer: SelectionLayer) -> None:
        super().__init__(selection_layer)

        toggle_row = QHBoxLayout()
        toggle_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._mode_toggle = DualToggle(self, [SELECTION_MODE_RECT, SELECTION_MODE_ELLIPSE],
                                       Qt.Orientation.Horizontal)
        # TODO: shape icons
        self._mode_toggle.setValue(SELECTION_MODE_RECT)
        self._mode_toggle.valueChanged.connect(self.tool_mode_changed)
        toggle_row.addWidget(self._mode_toggle)

        toggle_hint = KeyHintLabel(config_key=KeyConfig.TOOL_ACTION_HOTKEY)
        toggle_row.addWidget(toggle_hint)
        self.insert_into_layout(toggle_row)

        def _try_toggle() -> bool:
            if not self.isVisible():
                return False
            self._mode_toggle.toggle()
            return True
        HotkeyFilter.instance().register_config_keybinding(_try_toggle, KeyConfig.TOOL_ACTION_HOTKEY)

        # TODO: fixed aspect ratio checkbox
        self.insert_into_layout(Divider(Qt.Orientation.Horizontal))