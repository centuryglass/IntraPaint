"""Control panel widget for the filter tool."""
import json
from typing import Any, Callable, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QGridLayout, QLabel, QWidget

from src.config.cache import Cache
from src.image.filter.filter import ImageFilter
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.segmented_control import DisplayMode, MAX_SEGMENTS, Segment, SegmentedControl
from src.ui.input_fields.slider_field import number_field_for_parameter
from src.ui.layout.label_column_layout import normalize_row_label
from src.ui.panel.tool_control_panels.stroke_block import (FIELD_COLUMN_MAX_WIDTH, StrokeBlock, StrokeToolPanel,
                                                                tool_section)
from src.ui.panel.tool_control_panels.stroke_preview import FilterStrokePreview
from src.util.parameter import Parameter, ParamType, TYPE_FLOAT, TYPE_INT, TYPE_STR
from src.util.shared_constants import ICON_SIZE
from src.ui.input_fields.field_factory import create_control_widget, create_input_widget

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.filter_tool_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


LABEL_TEXT_FILTER_TYPE = _tr('Filter')
SECTION_TITLE = _tr('Filter')
STRENGTH_LABEL = _tr('Strength')
STRENGTH_TOOLTIP = _tr('How strongly the filter is applied where you paint')
# Parameters wrap into this many columns in a strip:
STRIP_PARAMETER_COLUMNS = 3


class FilterToolPanel(StrokeToolPanel):
    """Control panel widget for the filter tool: the stroke block with Opacity read as Strength and a preview of
    the filter, then the filter section."""

    def __init__(self, filter_list: list[ImageFilter]) -> None:
        self._filters = filter_list
        super().__init__(StrokeBlock(size_key=Cache.FILTER_TOOL_BRUSH_SIZE,
                                     pressure_size_key=Cache.FILTER_TOOL_PRESSURE_SIZE,
                                     opacity_key=Cache.FILTER_TOOL_OPACITY,
                                     opacity_label=STRENGTH_LABEL,
                                     opacity_tooltip=STRENGTH_TOOLTIP,
                                     pressure_opacity_key=Cache.FILTER_TOOL_PRESSURE_OPACITY,
                                     hardness_key=Cache.FILTER_TOOL_HARDNESS,
                                     pressure_hardness_key=Cache.FILTER_TOOL_PRESSURE_HARDNESS,
                                     antialias_key=Cache.FILTER_TOOL_ANTIALIAS,
                                     preview=FilterStrokePreview(filter_list, Cache.FILTER_TOOL_BRUSH_SIZE,
                                                                 Cache.FILTER_TOOL_OPACITY,
                                                                 Cache.FILTER_TOOL_HARDNESS,
                                                                 Cache.FILTER_TOOL_ANTIALIAS)))
        self._strip = False
        self._filter_dropdown = create_control_widget(Cache(), Cache.FILTER_TOOL_SELECTED_FILTER)
        self._filter_dropdown.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        for i in range(self._filter_dropdown.count()):
            name = self._filter_dropdown.itemText(i)
            img_filter = self._filter_from_name(name)
            self._filter_dropdown.setItemIcon(i, img_filter.get_icon())
        self._filter_dropdown.valueChanged.connect(self._update_filter_option_slot)
        self._filter_label = QLabel(LABEL_TEXT_FILTER_TYPE)
        self._filter_label.setBuddy(self._filter_dropdown)

        self._parameter_widgets: list[QWidget] = []
        self._parameter_container = QWidget(self)
        self._parameter_layout = QGridLayout(self._parameter_container)
        self._parameter_layout.setContentsMargins(0, 0, 0, 0)
        self._parameter_layout.setSpacing(4)
        self._current_filter: Optional[ImageFilter] = None
        self._filter_params = json.loads(Cache().get(Cache.FILTER_TOOL_CACHED_PARAMETERS))
        # One setter per parameter widget of the current filter, to apply cached values:
        self._parameter_setters: list[Callable[[Any], None]] = []
        self._update_filter_option_slot(self._filter_dropdown.currentText())
        Cache().connect(self, Cache.FILTER_TOOL_CACHED_PARAMETERS, self._update_filter_param_slot)
        # The section goes in after the first parameters, so no layout caches a size hint without them:
        self._section = tool_section(SECTION_TITLE, self._filter_row(), self._parameter_container)
        self._column_width = max(FIELD_COLUMN_MAX_WIDTH, self._section.minimumSizeHint().width())
        self._section.setMaximumWidth(self._column_width)
        self.add_tool_section(self._section)

    def _filter_row(self) -> QWidget:
        row = QWidget(self)
        row_layout = QGridLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self._filter_label, 0, 0)
        row_layout.addWidget(self._filter_dropdown, 0, 1)
        row_layout.setColumnStretch(1, 1)
        return row

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Passes the dock's orientation to the block, and wraps parameters into extra columns in a strip."""
        super().set_orientation(orientation)
        strip = orientation == Qt.Orientation.Horizontal
        if strip != self._strip:
            self._strip = strip
            # Wrapped parameters get a column width each:
            self._section.setMaximumWidth(self._column_width * (STRIP_PARAMETER_COLUMNS if strip else 1))
            self._arrange_parameters()

    def _arrange_parameters(self) -> None:
        for widget in self._parameter_widgets:
            self._parameter_layout.removeWidget(widget)
        columns = STRIP_PARAMETER_COLUMNS if self._strip else 1
        for index in range(STRIP_PARAMETER_COLUMNS):
            self._parameter_layout.setColumnStretch(index, 1 if index < columns else 0)
        for index, widget in enumerate(self._parameter_widgets):
            self._parameter_layout.addWidget(widget, index // columns, index % columns)

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
            self._parameter_setters[i](filter_value)

    def _build_parameter_widget(self, parameter: Parameter) -> tuple[QWidget, Any, Callable[[Any], None]]:
        """Returns a parameter's widget, the signal that reports its value, and a function that sets its value.

        Parameter labels are sentence case without colons.
        """
        label = normalize_row_label(parameter.name)
        if parameter.type_name in (TYPE_INT, TYPE_FLOAT):
            field = number_field_for_parameter(parameter)
            field.set_label(label)
            return field, field.valueChanged, field.set_value
        if parameter.type_name == TYPE_STR and parameter.options is not None and 2 <= len(
                parameter.options) <= MAX_SEGMENTS:
            # The options are the stored values, so segments bind them raw:
            options = [str(option) for option in parameter.options]
            control = SegmentedControl([Segment(option, option) for option in options],
                                       display_mode=DisplayMode.LABEL, combo_fallback=True)
            return self._labeled(label, control, parameter.description), control.valueChanged, control.set_value
        widget = create_input_widget(parameter)
        if isinstance(widget, CheckBox):
            widget.setText(label)
            return widget, widget.valueChanged, widget.setValue
        return self._labeled(label, widget, parameter.description), widget.valueChanged, widget.setValue

    @staticmethod
    def _labeled(label: str, widget: QWidget, description: str) -> QWidget:
        container = QWidget()
        container_layout = QGridLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        label_widget = QLabel(label)
        label_widget.setBuddy(widget)
        label_widget.setToolTip(description)
        container_layout.addWidget(label_widget, 0, 0)
        container_layout.addWidget(widget, 0, 1)
        container_layout.setColumnStretch(1, 1)
        return container

    def _update_filter_option_slot(self, filter_name: str) -> None:
        """Update panel layout with new filter parameters when the filter changes"""
        img_filter = self._filter_from_name(filter_name)
        if img_filter == self._current_filter:
            return

        for widget in self._parameter_widgets:
            self._parameter_layout.removeWidget(widget)
            widget.setVisible(False)
            widget.setParent(None)
            widget.deleteLater()
        self._parameter_widgets = []
        self._parameter_setters = []

        for idx, parameter in enumerate(img_filter.get_parameters()):
            def _update_param_in_json(new_value: ParamType, param_idx=idx, param_key=filter_name) -> None:
                if self._filter_params[param_key][param_idx] != new_value:
                    self._filter_params[param_key][param_idx] = new_value
                    Cache().set(Cache.FILTER_TOOL_CACHED_PARAMETERS, json.dumps(self._filter_params))

            widget, value_signal, set_value = self._build_parameter_widget(parameter)
            try:
                set_value(self._filter_params[filter_name][idx])
            except (TypeError, ValueError):
                set_value(parameter.default_value)
                self._filter_params[filter_name][idx] = parameter.default_value
                Cache().set(Cache.FILTER_TOOL_CACHED_PARAMETERS, json.dumps(self._filter_params))
            value_signal.connect(_update_param_in_json)
            self._parameter_widgets.append(widget)
            self._parameter_setters.append(set_value)
        self._arrange_parameters()
        self._current_filter = img_filter
