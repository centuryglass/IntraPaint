"""Control panel widget for the smudge tool."""
from typing import cast, Optional

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QComboBox

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.mypaint.mypaint_brush import MyPaintBrush, BrushSetting
from src.ui.input_fields.combo_box import ComboBox
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox, FloatSliderSpinbox
from src.ui.widget.key_hint_label import KeyHintLabel

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.smudge_tool_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


class SmudgeToolPanel(QWidget):
    """Control panel widget for the blur tool."""

    def __init__(self, smudge_brush: MyPaintBrush) -> None:
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._brush = smudge_brush
        cache = Cache()
        self._brush_size_label = QLabel(cache.get_label(Cache.SMUDGE_TOOL_BRUSH_SIZE))
        self._brush_size_down_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_SIZE_DECREASE)
        self._brush_size_slider = cast(IntSliderSpinbox, cache.get_control_widget(Cache.SMUDGE_TOOL_BRUSH_SIZE))
        self._brush_size_up_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_SIZE_INCREASE)

        self._mypaint_dropdown = QComboBox()
        self._mypaint_dropdown.addItem('None')
        for brush_setting in MyPaintBrush._setting_info:
            self._mypaint_dropdown.addItem(brush_setting.name, userData=brush_setting)
        self._setting_info = QLabel('')
        self._setting_info.setWordWrap(True)
        self._setting_slider = FloatSliderSpinbox()
        self._setting_slider.valueChanged.connect(self._slider_value_change_slot)
        self._mypaint_dropdown.currentIndexChanged.connect(self._brush_box_change_slot)
        self._mypaint_dropdown.setCurrentText('None')

        self._build_layout()

    def _build_layout(self) -> None:
        size_row = QHBoxLayout()
        size_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        for size_widget in (self._brush_size_label, self._brush_size_down_hint, self._brush_size_slider,
                            self._brush_size_up_hint):
            size_row.addWidget(size_widget)
        self._layout.addLayout(size_row)

        self._layout.addWidget(self._mypaint_dropdown)
        self._layout.addWidget(self._setting_info)
        self._layout.addWidget(self._setting_slider)

    def _brush_box_change_slot(self, idx: int) -> None:
        brush_data: Optional[BrushSetting] = self._mypaint_dropdown.itemData(idx)
        if brush_data is None:
            self._setting_slider.setVisible(False)
            self._setting_info.setVisible(False)
            return
        blocker = QSignalBlocker(self._setting_slider)
        self._setting_slider.setVisible(True)
        self._setting_slider.setRange(brush_data.min_value, brush_data.max_value)
        self._setting_slider.setValue(self._brush.get_value(brush_data.id))
        self._setting_info.setText(brush_data.tooltip)
        self._setting_info.setVisible(True)

    def _slider_value_change_slot(self, value: float) -> None:
        brush_data: Optional[BrushSetting] = self._mypaint_dropdown.currentData()
        if brush_data is None:
            return
        self._brush.set_value(brush_data.id, value)