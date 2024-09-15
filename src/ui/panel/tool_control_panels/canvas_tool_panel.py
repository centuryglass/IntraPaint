"""Control panel for canvas tools that apply size/opacity/hardness cache value changes."""
from typing import Optional, List, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QLayout

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox, FloatSliderSpinbox
from src.ui.widget.color_button import ColorButton
from src.ui.widget.key_hint_label import KeyHintLabel


class CanvasToolPanel(QWidget):
    """Control panel for canvas tools that apply size/opacity/hardness cache value changes."""

    def __init__(self, size_key: Optional[str] = None,
                 pressure_size_key: Optional[str] = None,
                 opacity_key: Optional[str] = None,
                 pressure_opacity_key: Optional[str] = None,
                 hardness_key: Optional[str] = None,
                 pressure_hardness_key: Optional[str] = None,
                 color_key: Optional[str] = None,
                 selection_only_label: Optional[str] = None,
                 added_rows: Optional[List[QWidget | QLayout]] = None) -> None:
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._pressure_checkboxes = []
        cache = Cache()

        if size_key is not None:
            size_label = QLabel(cache.get_label(size_key))
            size_down_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_SIZE_DECREASE)
            size_slider = cast(IntSliderSpinbox, cache.get_control_widget(size_key))
            size_up_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_SIZE_INCREASE)
            size_row = QHBoxLayout()
            size_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
            for size_widget in (size_label, size_down_hint, size_slider, size_up_hint):
                size_row.addWidget(size_widget)
            self._layout.addLayout(size_row)

        if opacity_key is not None:
            opacity_label = QLabel(cache.get_label(opacity_key))
            opacity_slider = cast(FloatSliderSpinbox, cache.get_control_widget(opacity_key))
            opacity_row = QHBoxLayout()
            opacity_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
            opacity_row.addWidget(opacity_label)
            opacity_row.addWidget(opacity_slider)
            self._layout.addLayout(opacity_row)

        if hardness_key is not None:
            hardness_label = QLabel(cache.get_label(hardness_key))
            hardness_slider = cast(FloatSliderSpinbox, cache.get_control_widget(hardness_key))
            hardness_row = QHBoxLayout()
            hardness_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
            hardness_row.addWidget(hardness_label)
            hardness_row.addWidget(hardness_slider)
            self._layout.addLayout(hardness_row)

        color_row = QHBoxLayout()
        # color_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        if color_key is not None:
            color_button = ColorButton(config_key=color_key)
            color_row.addWidget(color_button)
        selection_only_checkbox = cache.get_control_widget(Cache.PAINT_SELECTION_ONLY)
        if selection_only_label is not None:
            selection_only_checkbox.setText(selection_only_label)
        color_row.addWidget(selection_only_checkbox)
        self._layout.addLayout(color_row)

        if added_rows is not None:
            for row in added_rows:
                if isinstance(row, QWidget):
                    self._layout.addWidget(row)
                else:
                    assert isinstance(row, QLayout)
                    self._layout.addLayout(row)

        for pressure_key in [pressure_size_key, pressure_opacity_key, pressure_hardness_key]:
            if pressure_key is not None:
                self._pressure_checkboxes.append(cache.get_control_widget(pressure_key))
        if len(self._pressure_checkboxes) > 0:
            checkbox_row = QHBoxLayout()
            checkbox_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
            for checkbox in self._pressure_checkboxes:
                checkbox.setVisible(False)
                checkbox_row.addWidget(checkbox)
            self._layout.addLayout(checkbox_row)

    def show_pressure_checkboxes(self) -> None:
        """After receiving a tablet event, call this to reveal the pressure control checkboxes."""
        for checkbox in self._pressure_checkboxes:
            checkbox.setVisible(True)
