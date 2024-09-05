"""Control panel for the basic drawing tool."""
from typing import cast

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.ui.input_fields.dual_toggle import DualToggle
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox
from src.ui.panel.tool_control_panels.canvas_selection_panel import (TOOL_MODE_DRAW, TOOL_MODE_ERASE,
                                                                     RESOURCES_PEN_PNG, RESOURCES_ERASER_PNG)
from src.ui.widget.color_button import ColorButton
from src.ui.widget.key_hint_label import KeyHintLabel

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.draw_tool_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


SELECTION_ONLY_LABEL = _tr('Draw in selection only')


class DrawToolPanel(QWidget):
    """Control panel for the basic drawing tool."""

    tool_mode_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        config = AppConfig()

        # Size slider:
        self._brush_size_label = QLabel(config.get_label(AppConfig.SKETCH_BRUSH_SIZE))
        self._brush_size_down_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_SIZE_DECREASE)
        self._brush_size_slider = cast(IntSliderSpinbox, config.get_control_widget(AppConfig.SKETCH_BRUSH_SIZE))
        self._brush_size_up_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_SIZE_INCREASE)

        # Color button:
        self._color_picker_button = ColorButton()

        # Selection only box:
        self._selection_only_checkbox = Cache().get_control_widget(Cache.PAINT_SELECTION_ONLY)
        self._selection_only_checkbox.setText(SELECTION_ONLY_LABEL)

        # Draw/erase toggle:

        self._tool_toggle = DualToggle(self, [TOOL_MODE_DRAW, TOOL_MODE_ERASE])
        self._tool_toggle.set_icons(RESOURCES_PEN_PNG, RESOURCES_ERASER_PNG)
        self._tool_toggle.setValue(TOOL_MODE_DRAW)
        self._tool_toggle.valueChanged.connect(self.tool_mode_changed)

        self._toggle_hint = KeyHintLabel(config_key=KeyConfig.TOOL_ACTION_HOTKEY)

        def _try_toggle() -> bool:
            if not self._tool_toggle.isVisible():
                return False
            self._tool_toggle.toggle()
            return True
        HotkeyFilter.instance().register_config_keybinding(_try_toggle, KeyConfig.TOOL_ACTION_HOTKEY)
        self._build_layout()

    def _build_layout(self) -> None:
        size_row = QHBoxLayout()
        size_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        for size_widget in (self._brush_size_label, self._brush_size_down_hint, self._brush_size_slider,
                            self._brush_size_up_hint):
            size_row.addWidget(size_widget)
        self._layout.addLayout(size_row)

        second_row = QHBoxLayout()
        second_row.addWidget(self._color_picker_button)
        second_row.addWidget(self._selection_only_checkbox)
        self._layout.addLayout(second_row)

        third_row = QHBoxLayout()
        third_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        third_row.addWidget(self._tool_toggle)
        third_row.addWidget(self._toggle_hint)
        self._layout.addLayout(third_row)
