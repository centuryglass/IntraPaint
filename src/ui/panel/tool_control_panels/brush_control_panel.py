"""Control panel widget for the MyPaint Brush tool."""
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QApplication, QHBoxLayout, QLabel

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox
from src.ui.layout.divider import Divider
from src.ui.panel.mypaint_brush_panel import MypaintBrushPanel
from src.ui.widget.brush_color_button import BrushColorButton
from src.ui.widget.key_hint_label import KeyHintLabel

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.brush_control_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


SELECTION_ONLY_LABEL = _tr('Paint selection only')


class BrushControlPanel(QWidget):
    """Control panel widget for the MyPaint Brush tool."""

    def __init__(self) -> None:
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.addWidget(Divider(Qt.Orientation.Horizontal))
        config = AppConfig()

        # Size slider:
        size_row = QHBoxLayout()
        size_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        size_label = QLabel(config.get_label(AppConfig.SKETCH_BRUSH_SIZE))
        size_row.addWidget(size_label)
        size_down_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_SIZE_DECREASE)
        size_row.addWidget(size_down_hint)
        brush_size_slider = cast(IntSliderSpinbox, config.get_control_widget(AppConfig.SKETCH_BRUSH_SIZE))
        size_row.addWidget(brush_size_slider)
        size_up_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_SIZE_INCREASE)
        size_row.addWidget(size_up_hint)
        self._layout.addLayout(size_row)

        second_row = QHBoxLayout()
        self._layout.addLayout(second_row)
        color_picker_button = BrushColorButton()
        second_row.addWidget(color_picker_button)

        selection_only_checkbox = Cache().get_control_widget(Cache.PAINT_SELECTION_ONLY)
        selection_only_checkbox.setText(SELECTION_ONLY_LABEL)
        second_row.addWidget(selection_only_checkbox)
        selection_only_checkbox.setText(SELECTION_ONLY_LABEL)
        second_row.addWidget(selection_only_checkbox)
        brush_panel = MypaintBrushPanel()
        self._layout.addWidget(brush_panel)
