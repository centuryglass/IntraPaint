"""Control panel for the basic eraser tool."""
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox, FloatSliderSpinbox
from src.ui.widget.key_hint_label import KeyHintLabel

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.eraser_tool_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


SELECTION_ONLY_LABEL = _tr('Erase in selection only')


class EraserToolPanel(QWidget):
    """Control panel for the basic drawing tool."""
    def __init__(self):
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        cache = Cache()

        # Size slider:
        self._brush_size_label = QLabel(cache.get_label(Cache.ERASER_TOOL_SIZE))
        self._brush_size_down_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_SIZE_DECREASE)
        self._brush_size_slider = cast(IntSliderSpinbox, cache.get_control_widget(Cache.ERASER_TOOL_SIZE))
        self._brush_size_up_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_SIZE_INCREASE)
        self._size_pressure_checkbox = cache.get_control_widget(Cache.ERASER_TOOL_PRESSURE_SIZE)

        self._brush_opacity_label = QLabel(cache.get_label(Cache.DRAW_TOOL_OPACITY))
        self._brush_opacity_slider = cast(FloatSliderSpinbox, cache.get_control_widget(Cache.ERASER_TOOL_OPACITY))
        self._opacity_pressure_checkbox = cache.get_control_widget(Cache.ERASER_TOOL_PRESSURE_OPACITY)

        self._brush_hardness_label = QLabel(cache.get_label(Cache.DRAW_TOOL_HARDNESS))
        self._brush_hardness_slider = cast(FloatSliderSpinbox, cache.get_control_widget(Cache.ERASER_TOOL_HARDNESS))
        self._hardness_pressure_checkbox = cache.get_control_widget(Cache.ERASER_TOOL_PRESSURE_HARDNESS)

        # Selection only box:
        self._selection_only_checkbox = Cache().get_control_widget(Cache.PAINT_SELECTION_ONLY)
        self._selection_only_checkbox.setText(SELECTION_ONLY_LABEL)
        self._build_layout()

    def show_pressure_checkboxes(self) -> None:
        """After receiving a tablet event, call this to reveal the pressure control checkboxes."""
        for checkbox in [self._size_pressure_checkbox, self._opacity_pressure_checkbox,
                         self._hardness_pressure_checkbox]:
            checkbox.setVisible(True)

    def _build_layout(self) -> None:
        size_row = QHBoxLayout()
        size_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        for size_widget in (self._brush_size_label, self._brush_size_down_hint, self._brush_size_slider,
                            self._brush_size_up_hint):
            size_row.addWidget(size_widget)
        self._layout.addLayout(size_row)

        opacity_row = QHBoxLayout()
        opacity_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        opacity_row.addWidget(self._brush_opacity_label)
        opacity_row.addWidget(self._brush_opacity_slider)
        self._layout.addLayout(opacity_row)

        hardness_row = QHBoxLayout()
        hardness_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        hardness_row.addWidget(self._brush_hardness_label)
        hardness_row.addWidget(self._brush_hardness_slider)
        self._layout.addLayout(hardness_row)

        checkbox_row = QHBoxLayout()
        checkbox_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        for checkbox in [self._size_pressure_checkbox, self._opacity_pressure_checkbox,
                         self._hardness_pressure_checkbox]:
            checkbox_row.addWidget(checkbox)
            checkbox.setVisible(False)
        self._layout.addLayout(checkbox_row)

