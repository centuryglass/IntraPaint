"""Control panel widget for the clone stamp tool."""
from typing import Optional

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QApplication, QGridLayout, QWidget

from src.config.cache import Cache
from src.ui.input_fields.number_field import NumberField
from src.ui.input_fields.segmented_control import DisplayMode, Segment, SegmentedControl
from src.ui.panel.tool_control_panels.stroke_block import StrokeBlock, StrokeToolPanel, tool_section
from src.util.shared_constants import INT_MAX, INT_MIN

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.clone_stamp_tool_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


SOURCE_SECTION_TITLE = _tr('Source')
LABEL_TEXT_OFFSET_X = _tr('Offset X')
LABEL_TEXT_OFFSET_Y = _tr('Offset Y')
LABEL_TEXT_POSITION_X = _tr('Source X')
LABEL_TEXT_POSITION_Y = _tr('Source Y')

# Stored `Cache.CLONE_STAMP_TOOL_SOURCE_MODE` values; they match `src.tools.clone_stamp_tool` and the options in
# cache_value_definitions.json. The segmented control binds these raw values, never the translated labels.
SOURCE_MODE_FIXED_OFFSET = 'Fixed offset'
SOURCE_MODE_DYNAMIC_OFFSET = 'Dynamic offset'
SOURCE_MODE_STATIC = 'Fixed position'


class CloneStampToolPanel(StrokeToolPanel):
    """Control panel widget for the clone stamp tool: the stroke block, then a Source section."""

    source_xy_change = Signal(QPoint)

    def __init__(self) -> None:
        cache = Cache()
        super().__init__(StrokeBlock(size_key=Cache.CLONE_STAMP_TOOL_BRUSH_SIZE,
                                     pressure_size_key=Cache.CLONE_STAMP_TOOL_PRESSURE_SIZE,
                                     opacity_key=Cache.CLONE_STAMP_TOOL_OPACITY,
                                     pressure_opacity_key=Cache.CLONE_STAMP_TOOL_PRESSURE_OPACITY,
                                     hardness_key=Cache.CLONE_STAMP_TOOL_HARDNESS,
                                     pressure_hardness_key=Cache.CLONE_STAMP_TOOL_PRESSURE_HARDNESS,
                                     antialias_key=Cache.CLONE_STAMP_TOOL_ANTIALIAS))
        self._source_xy = QPoint()
        self._source_mode_control = SegmentedControl(
            [Segment(mode, cache.get_option_display(mode))
             for mode in (SOURCE_MODE_FIXED_OFFSET, SOURCE_MODE_DYNAMIC_OFFSET, SOURCE_MODE_STATIC)],
            display_mode=DisplayMode.LABEL, combo_fallback=True, parent=self)
        self._source_mode_control.set_value(cache.get(Cache.CLONE_STAMP_TOOL_SOURCE_MODE))

        def _mode_changed(mode: str) -> None:
            if cache.get(Cache.CLONE_STAMP_TOOL_SOURCE_MODE) != mode:
                cache.set(Cache.CLONE_STAMP_TOOL_SOURCE_MODE, mode)

        self._source_mode_control.valueChanged.connect(_mode_changed)

        self._x_field = NumberField(LABEL_TEXT_OFFSET_X, 0, INT_MIN, INT_MAX, parent=self)
        self._y_field = NumberField(LABEL_TEXT_OFFSET_Y, 0, INT_MIN, INT_MAX, parent=self)
        fields = QWidget(self)
        fields_layout = QGridLayout(fields)
        fields_layout.setContentsMargins(0, 0, 0, 0)
        fields_layout.addWidget(self._x_field, 0, 0)
        fields_layout.addWidget(self._y_field, 1, 0)
        self._fields_layout = fields_layout
        self._section = tool_section(SOURCE_SECTION_TITLE, self._source_mode_control, fields)
        self._layout.addWidget(self._section)

        def _source_mode_update(source_mode: str) -> None:
            self._source_mode_control.set_value(source_mode)
            static = source_mode == SOURCE_MODE_STATIC
            self._x_field.set_label(LABEL_TEXT_POSITION_X if static else LABEL_TEXT_OFFSET_X)
            self._y_field.set_label(LABEL_TEXT_POSITION_Y if static else LABEL_TEXT_OFFSET_Y)

        # `Config.connect` keeps one callback per object and key, so one function does both updates:
        cache.connect(self, Cache.CLONE_STAMP_TOOL_SOURCE_MODE, _source_mode_update)
        _source_mode_update(cache.get(Cache.CLONE_STAMP_TOOL_SOURCE_MODE))

        def _update_x(new_x: int | float) -> None:
            if new_x == self._source_xy.x():
                return
            self._source_xy.setX(int(new_x))
            self.source_xy_change.emit(QPoint(self._source_xy))

        def _update_y(new_y: int | float) -> None:
            if new_y == self._source_xy.y():
                return
            self._source_xy.setY(int(new_y))
            self.source_xy_change.emit(QPoint(self._source_xy))

        self._x_field.valueChanged.connect(_update_x)
        self._y_field.valueChanged.connect(_update_y)

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Passes the dock's orientation to the block, and puts X and Y side by side in a strip."""
        super().set_orientation(orientation)
        self._fields_layout.removeWidget(self._y_field)
        if orientation == Qt.Orientation.Horizontal:
            self._fields_layout.addWidget(self._y_field, 0, 1)
        else:
            self._fields_layout.addWidget(self._y_field, 1, 0)

    @property
    def source_xy(self) -> QPoint:
        """Accesses the current source position or offset value."""
        return QPoint(self._source_xy)

    @source_xy.setter
    def source_xy(self, new_source_xy: QPoint) -> None:
        self._x_field.set_value(new_source_xy.x())
        self._y_field.set_value(new_source_xy.y())
