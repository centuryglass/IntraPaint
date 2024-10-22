"""Control panel for brush tools that apply size/opacity/hardness cache value changes."""
from typing import Optional, List, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QLayout

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.ui.input_fields.fill_style_combo_box import FillStyleComboBox
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox, FloatSliderSpinbox
from src.ui.widget.color_button import ColorButton
from src.ui.widget.key_hint_label import KeyHintLabel
from src.ui.widget.pen_pressure_panel import PenPressurePanel
from src.util.layout import extract_layout_item, synchronize_row_widths


class BrushToolPanel(QWidget):
    """Control panel for brush tools that apply size/opacity/hardness cache value changes."""

    def __init__(self, size_key: Optional[str] = None,
                 pressure_size_key: Optional[str] = None,
                 opacity_key: Optional[str] = None,
                 pressure_opacity_key: Optional[str] = None,
                 hardness_key: Optional[str] = None,
                 pressure_hardness_key: Optional[str] = None,
                 color_key: Optional[str] = None,
                 pattern_key: Optional[str] = None,
                 antialias_key: Optional[str] = None,
                 selection_only_label: Optional[str] = None,
                 added_rows: Optional[List[QWidget | QLayout]] = None) -> None:
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        cache = Cache()

        if added_rows is not None:
            for row in added_rows:
                if isinstance(row, QWidget):
                    self._layout.addWidget(row)
                else:
                    assert isinstance(row, QLayout)
                    self._layout.addLayout(row)

        if size_key is not None:
            size_label = QLabel(cache.get_label(size_key))
            size_down_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_SIZE_DECREASE, parent=self)
            size_slider = cast(IntSliderSpinbox, cache.get_control_widget(size_key))
            size_up_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_SIZE_INCREASE, parent=self)
            size_row = QHBoxLayout()
            size_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
            for size_widget in (size_label, size_down_hint, size_slider, size_up_hint):
                size_row.addWidget(size_widget)
            self._layout.addLayout(size_row)

        if opacity_key is not None:
            opacity_label = QLabel(cache.get_label(opacity_key))
            opacity_down_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_OPACITY_DECREASE, parent=self)
            opacity_slider = cast(FloatSliderSpinbox, cache.get_control_widget(opacity_key))
            opacity_up_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_OPACITY_INCREASE, parent=self)
            opacity_row = QHBoxLayout()
            opacity_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
            for opacity_widget in (opacity_label, opacity_down_hint, opacity_slider, opacity_up_hint):
                opacity_row.addWidget(opacity_widget)
            self._layout.addLayout(opacity_row)

        if hardness_key is not None:
            hardness_label = QLabel(cache.get_label(hardness_key))
            hardness_down_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_HARDNESS_DECREASE, parent=self)
            hardness_slider = cast(FloatSliderSpinbox, cache.get_control_widget(hardness_key))
            hardness_up_hint = KeyHintLabel(config_key=KeyConfig.BRUSH_HARDNESS_INCREASE, parent=self)
            hardness_row = QHBoxLayout()
            hardness_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
            for hardness_widget in (hardness_label, hardness_down_hint, hardness_slider, hardness_up_hint):
                hardness_row.addWidget(hardness_widget)
            self._layout.addLayout(hardness_row)

        self._align_rows()
        color_row = QHBoxLayout()
        if color_key is not None:
            color_button = ColorButton(config_key=color_key, parent=self)
            color_row.addWidget(color_button)
        if pattern_key is not None:
            pattern_label = QLabel(cache.get_label(pattern_key))
            pattern_dropdown = FillStyleComboBox(pattern_key)
            color_row.addWidget(pattern_label)
            color_row.addWidget(pattern_dropdown)
            if color_key is not None:
                def _pattern_color_update(color_str: str) -> None:
                    if QColor.isValidColor(color_str):
                        color = QColor(color_str)
                        pattern_dropdown.set_icon_colors(color)
                cache.connect(self, color_key, _pattern_color_update)
                pattern_dropdown.set_icon_colors(cache.get_color(color_key, Qt.GlobalColor.black))
        self._layout.addLayout(color_row)

        if any(key is not None for key in [pressure_size_key, pressure_opacity_key, pressure_hardness_key]):
            self._pressure_panel: Optional[PenPressurePanel] = PenPressurePanel(pressure_size_key, pressure_opacity_key,
                                                                                pressure_hardness_key,  self)
            self._pressure_panel.setVisible(Cache().get(Cache.EXPECT_TABLET_INPUT))
            self._layout.addWidget(self._pressure_panel)
        else:
            self._pressure_panel = None

        checkbox_row = QHBoxLayout()
        checkbox_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        if antialias_key is not None:
            antialias_checkbox = cache.get_control_widget(antialias_key)
            antialias_checkbox.setText(cache.get_label(antialias_key))
            checkbox_row.addWidget(antialias_checkbox)
        selection_only_checkbox = cache.get_control_widget(Cache.PAINT_SELECTION_ONLY)
        if selection_only_label is not None:
            selection_only_checkbox.setText(selection_only_label)
        checkbox_row.addWidget(selection_only_checkbox)
        self._layout.addLayout(checkbox_row)

    def _align_rows(self) -> None:
        rows = []
        expected_count = 4
        for i in range(self._layout.count()):
            row = []
            row_item = self._layout.itemAt(i)
            if row_item is None:
                continue
            row_layout = row_item.layout()
            if row_layout is None or row_layout.count() != expected_count:
                continue
            for i2 in range(row_layout.count()):
                column = extract_layout_item(row_layout.itemAt(i2))
                assert isinstance(column, QWidget)
                row.append(column)
            rows.append(row)
        if len(rows) > 0:
            synchronize_row_widths(rows)

    def show_pressure_checkboxes(self) -> None:
        """After receiving a tablet event, call this to reveal the pressure control checkboxes."""
        if self._pressure_panel is not None:
            self._pressure_panel.setVisible(True)
            Cache().set(Cache.EXPECT_TABLET_INPUT, True)
