"""Control panel widget for the filter tool."""
import json
from typing import List, Optional, Callable, Any, Tuple

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QWidget, QApplication, QVBoxLayout, QLabel, QHBoxLayout

from src.config.cache import Cache
from src.image.filter.filter import ImageFilter
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.slider_spinbox import FloatSliderSpinbox, IntSliderSpinbox
from src.ui.layout.divider import Divider
from src.ui.panel.tool_control_panels.canvas_tool_panel import CanvasToolPanel
from src.util.parameter import DynamicFieldWidget, ParamType
from src.util.shared_constants import ICON_SIZE
from src.util.visual.geometry_utils import synchronize_row_widths

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.filter_tool_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


LABEL_TEXT_FILTER_TYPE = _tr('Filter:')
LABEL_TEXT_FILTER_SELECTED_ONLY = _tr('Filter selection only')


class FilterToolPanel(CanvasToolPanel):
    """Control panel widget for the filter tool."""

    def __init__(self, filter_list: List[ImageFilter]) -> None:
        self._filters = filter_list
        self._filter_option_panel = QWidget()
        super().__init__(size_key=Cache.FILTER_TOOL_BRUSH_SIZE, pressure_size_key=Cache.FILTER_TOOL_PRESSURE_SIZE,
                         opacity_key=Cache.FILTER_TOOL_OPACITY, pressure_opacity_key=Cache.FILTER_TOOL_PRESSURE_OPACITY,
                         hardness_key=Cache.FILTER_TOOL_HARDNESS,
                         pressure_hardness_key=Cache.FILTER_TOOL_PRESSURE_HARDNESS,
                         selection_only_label=LABEL_TEXT_FILTER_SELECTED_ONLY,
                         added_rows=[self._filter_option_panel, Divider(Qt.Orientation.Horizontal)])
        self._filter_layout = QVBoxLayout(self._filter_option_panel)
        self._filter_dropdown = Cache().get_control_widget(Cache.FILTER_TOOL_SELECTED_FILTER)
        self._filter_dropdown.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        for i in range(self._filter_dropdown.count()):
            name = self._filter_dropdown.itemText(i)
            img_filter = self._filter_from_name(name)
            self._filter_dropdown.setItemIcon(i, img_filter.get_icon())

        self._filter_dropdown.valueChanged.connect(self._update_filter_option_slot)
        self._filter_row = QWidget()
        self._filter_label = QLabel(LABEL_TEXT_FILTER_TYPE)
        self._filter_label.setBuddy(self._filter_dropdown)
        filter_row_layout = QHBoxLayout(self._filter_row)
        filter_row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        filter_row_layout.addWidget(self._filter_label)
        filter_row_layout.addWidget(self._filter_dropdown)
        self._filter_layout.addWidget(self._filter_row)
        self._current_filter: Optional[ImageFilter] = None
        self._filter_params = json.loads(Cache().get(Cache.FILTER_TOOL_CACHED_PARAMETERS))
        self._filter_widget_connections: List[Tuple[DynamicFieldWidget, Callable[[Any], None]]] = []
        self._update_filter_option_slot(self._filter_dropdown.currentText())
        Cache().connect(self, Cache.FILTER_TOOL_CACHED_PARAMETERS, self._update_filter_param_slot)

    def _filter_from_name(self, filter_name: str) -> ImageFilter:
        matching = [img_filter for img_filter in self._filters if img_filter.get_name() == filter_name]
        if len(matching) == 0:
            raise ValueError(f'invalid filter name {filter_name}')
        return matching[0]

    def _update_filter_param_slot(self, filter_json: str):
        self._filter_params = json.loads(filter_json)
        if self._current_filter is None:
            return
        filter_name = self._current_filter.get_name()
        for i, filter_value in enumerate(self._filter_params[filter_name]):
            filter_input = self._filter_widget_connections[i][0]
            filter_input.setValue(filter_value)

    def _update_filter_option_slot(self, filter_name: str) -> None:
        """Update panel layout with new filter parameters when the filter changes"""
        img_filter = self._filter_from_name(filter_name)
        if img_filter == self._current_filter:
            return

        # Clear old layout:
        while len(self._filter_widget_connections) > 0:
            widget, handler = self._filter_widget_connections.pop(0)
            widget.valueChanged.disconnect(handler)
        while self._filter_layout.count() > 0:
            widget = self._filter_layout.takeAt(0).widget()
            assert widget is not None
            if widget != self._filter_row:
                widget.setVisible(False)
                widget.setParent(None)
        self._filter_layout.addWidget(self._filter_row)

        # Prepare parent class items for alignment:
        expected_row_length = 5
        alignment_rows = [[self._filter_label, None, self._filter_dropdown, None, None]]
        layout = self.layout()
        assert isinstance(layout, QVBoxLayout)
        for i in range(layout.count()):
            item = layout.itemAt(i)
            assert item is not None
            row_layout = item.layout()
            if row_layout is None:
                continue
            row = []
            for i2 in range(row_layout.count()):
                row_item = row_layout.itemAt(i2)
                assert row_item is not None
                row_widget = row_item.widget()
                if row_widget is None:
                    continue
                if isinstance(row_widget, (IntSliderSpinbox, FloatSliderSpinbox)):
                    row.append(row_widget.label)
                    row.append(row_widget.slider)
                    row.append(row_widget.spinbox)
                else:
                    row.append(row_widget)
            if len(row) == expected_row_length:
                alignment_rows.append(row)

        # Create new filter widgets:
        for idx, parameter in enumerate(img_filter.get_parameters()):
            row = []

            def _update_param_in_json(new_value: ParamType, param_idx=idx, param_key=filter_name) -> None:
                if self._filter_params[param_key][param_idx] != new_value:
                    self._filter_params[param_key][param_idx] = new_value
                    Cache().set(Cache.FILTER_TOOL_CACHED_PARAMETERS, json.dumps(self._filter_params))
            widget = parameter.get_input_widget()
            try:
                widget.setValue(self._filter_params[filter_name][idx])
            except (TypeError, ValueError):
                widget.setValue(parameter.default_value)  # type: ignore
                self._filter_params[filter_name][idx] = parameter.default_value
                Cache().set(Cache.FILTER_TOOL_CACHED_PARAMETERS, json.dumps(self._filter_params))
            widget.valueChanged.connect(_update_param_in_json)
            self._filter_widget_connections.append((widget, _update_param_in_json))
            if isinstance(widget, (IntSliderSpinbox, FloatSliderSpinbox, CheckBox)):
                widget.setText(parameter.name)
                if isinstance(widget, (IntSliderSpinbox, FloatSliderSpinbox)):
                    widget.set_slider_included(True)
                    row = [widget.label, None, widget.slider, None, widget.spinbox]
            else:
                widget_label = QLabel(parameter.name)
                widget_label.setBuddy(widget)
                widget_container = QWidget()
                widget_layout = QHBoxLayout()
                widget_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
                widget_layout.addWidget(widget_label)
                widget_layout.addWidget(widget)
                widget = widget_container
                row = [widget_label, None, widget, None, None]
            self._filter_layout.addWidget(widget)
            if len(row) > 0:
                alignment_rows.append(row)
        synchronize_row_widths(alignment_rows)
        self._current_filter = img_filter
