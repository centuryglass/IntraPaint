"""Shape tool control panel. Sets shape type, stroke properties, and fill properties."""
import logging
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QSize, QRegularExpression
from PySide6.QtGui import QPen, QBrush, QColor, QRegularExpressionValidator
from PySide6.QtWidgets import QWidget, QLabel, QGridLayout, QSizePolicy

from src.config.cache import Cache
from src.ui.input_fields.fill_style_combo_box import FillStyleComboBox
from src.ui.input_fields.pen_join_style_combo_box import PenJoinStyleComboBox
from src.ui.input_fields.pen_style_combo_box import PenStyleComboBox
from src.ui.input_fields.shape_mode_combo_box import ShapeModeComboBox
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox, FloatSliderSpinbox
from src.ui.layout.divider import Divider
from src.ui.widget.color_button import ColorButton
from src.util.layout import clear_layout
from src.util.shared_constants import ICON_SIZE
from src.util.visual.shape_mode import ShapeMode

logger = logging.getLogger(__name__)


class ShapeToolPanel(QWidget):
    """Shape tool control panel. Sets shape type, stroke properties, and fill properties."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self._orientation = Qt.Orientation.Horizontal
        cache = Cache()
        try:
            initial_mode = ShapeMode.from_text(cache.get(Cache.SHAPE_TOOL_MODE))
        except ValueError:
            initial_mode = ShapeMode.ELLIPSE
            cache.set(Cache.SHAPE_TOOL_MODE, initial_mode.display_text())

        # Shape type:
        self._shape_mode_label = QLabel(cache.get_label(Cache.SHAPE_TOOL_MODE), parent=self)
        self._shape_mode_combobox = ShapeModeComboBox(Cache.SHAPE_TOOL_MODE, self)
        self._shape_mode_combobox.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self._shape_mode_label.setBuddy(self._shape_mode_combobox)
        self._shape_mode_label.setToolTip(self._shape_mode_combobox.toolTip())

        def _on_mode_change(mode_name: str) -> None:
            try:
                shape_mode = ShapeMode.from_text(mode_name)
            except ValueError:
                shape_mode = ShapeMode.ELLIPSE
            self._vertex_spinbox.setVisible(shape_mode in (ShapeMode.POLYGON, ShapeMode.STAR))
            self._inner_radius_spinbox.setVisible(shape_mode == ShapeMode.STAR)
        cache.connect(self._shape_mode_combobox, Cache.SHAPE_TOOL_MODE, _on_mode_change)

        def _update_shape_dropdown_icons(_=None) -> None:
            try:
                pen = QPen()
                pen.setStyle(PenStyleComboBox.get_pen_style(cache.get(Cache.SHAPE_TOOL_LINE_STYLE)))
                pen.setWidth(min(cache.get(Cache.SHAPE_TOOL_LINE_WIDTH), ICON_SIZE // 3))
                pen.setColor(cache.get_color(Cache.SHAPE_TOOL_LINE_COLOR, Qt.GlobalColor.black))
                if pen.style() == Qt.PenStyle.CustomDashLine:
                    pen.setStyle(Qt.PenStyle.DashLine)

                brush = QBrush()
                brush.setStyle(FillStyleComboBox.get_style(cache.get(Cache.SHAPE_TOOL_FILL_PATTERN)))
                brush.setColor(cache.get_color(Cache.SHAPE_TOOL_FILL_COLOR, Qt.GlobalColor.white))

                vertex_count = cache.get(Cache.SHAPE_TOOL_VERTEX_COUNT)
                inner_radius = cache.get(Cache.SHAPE_TOOL_STAR_INNER_POINT_FRACTION)
                self._shape_mode_combobox.update_icon_style(pen, brush, vertex_count, inner_radius)
            except (KeyError, ValueError) as err:
                logger.error(f'Invalid shape cache value: {err}')
        for cache_key in (Cache.SHAPE_TOOL_LINE_STYLE, Cache.SHAPE_TOOL_LINE_WIDTH, Cache.SHAPE_TOOL_LINE_COLOR,
                          Cache.SHAPE_TOOL_FILL_PATTERN, Cache.SHAPE_TOOL_FILL_COLOR, Cache.SHAPE_TOOL_VERTEX_COUNT,
                          Cache.SHAPE_TOOL_STAR_INNER_POINT_FRACTION):
            cache.connect(self._shape_mode_combobox, cache_key, _update_shape_dropdown_icons)
        _update_shape_dropdown_icons()

        # Shape-specific extra parameters:
        self._vertex_spinbox = cache.get_control_widget(Cache.SHAPE_TOOL_VERTEX_COUNT)
        assert isinstance(self._vertex_spinbox, IntSliderSpinbox)
        self._vertex_spinbox.setText(cache.get_label(Cache.SHAPE_TOOL_VERTEX_COUNT))
        self._vertex_spinbox.setVisible(initial_mode in (ShapeMode.POLYGON, ShapeMode.STAR))
        self._vertex_spinbox.setParent(self)

        self._inner_radius_spinbox = cache.get_control_widget(Cache.SHAPE_TOOL_STAR_INNER_POINT_FRACTION)
        assert isinstance(self._inner_radius_spinbox, FloatSliderSpinbox)
        self._inner_radius_spinbox.setText(cache.get_label(Cache.SHAPE_TOOL_STAR_INNER_POINT_FRACTION))
        self._inner_radius_spinbox.set_slider_included(False)
        self._inner_radius_spinbox.setVisible(initial_mode == ShapeMode.STAR)
        self._inner_radius_spinbox.setParent(self)

        # Fill parameters:
        self._fill_color_button = ColorButton(Cache.SHAPE_TOOL_FILL_COLOR, self)
        self._fill_pattern_label = QLabel(cache.get_label(Cache.SHAPE_TOOL_FILL_PATTERN), parent=self)
        self._fill_style_dropdown = FillStyleComboBox(Cache.SHAPE_TOOL_FILL_PATTERN, True, self)
        self._fill_pattern_label.setBuddy(self._fill_style_dropdown)
        self._fill_pattern_label.setToolTip(self._fill_style_dropdown.toolTip())

        def _update_fill_previews(color_str) -> None:
            if QColor.isValidColor(color_str):
                color = QColor(color_str)
                self._fill_style_dropdown.set_icon_colors(color)
        cache.connect(self._fill_style_dropdown, Cache.SHAPE_TOOL_FILL_COLOR, _update_fill_previews)

        # Line parameters:
        self._line_color_button = ColorButton(Cache.SHAPE_TOOL_LINE_COLOR, self)

        self._line_width_slider = cache.get_control_widget(Cache.SHAPE_TOOL_LINE_WIDTH)
        self._line_width_slider.setText(cache.get_label(Cache.SHAPE_TOOL_LINE_WIDTH))
        self._line_width_slider.setParent(self)

        # Line_style:
        self._pen_style_label = QLabel(cache.get_label(Cache.SHAPE_TOOL_LINE_STYLE), self)
        self._pen_style_dropdown = PenStyleComboBox(Cache.SHAPE_TOOL_LINE_STYLE, self)
        self._pen_style_label.setBuddy(self._pen_style_dropdown)
        self._pen_style_label.setToolTip(self._pen_style_dropdown.toolTip())

        # Line join style:
        self._pen_join_style_label = QLabel(cache.get_label(Cache.SHAPE_TOOL_LINE_JOIN_STYLE))
        self._pen_join_style_dropdown = PenJoinStyleComboBox(Cache.SHAPE_TOOL_LINE_JOIN_STYLE, self)
        self._pen_join_style_label.setBuddy(self._pen_join_style_dropdown)
        self._pen_join_style_label.setToolTip(self._pen_join_style_dropdown.toolTip())

        self._antialiasing_checkbox = cache.get_control_widget(Cache.SHAPE_TOOL_ANTIALIAS)
        self._antialiasing_checkbox.setText(cache.get_label(Cache.SMUDGE_TOOL_ANTIALIAS))

        def _update_line_previews(color_str) -> None:
            if QColor.isValidColor(color_str):
                color = QColor(color_str)
                self._pen_style_dropdown.set_icon_colors(color)
                self._pen_join_style_dropdown.set_icon_colors(color)
        cache.connect(self._pen_style_dropdown, Cache.SHAPE_TOOL_LINE_COLOR, _update_line_previews)

        # Custom dash pattern row:
        self._dash_label = QLabel(cache.get_label(Cache.SHAPE_TOOL_DASH_PATTERN), parent=self)
        self._dash_textbox = cache.get_control_widget(Cache.SHAPE_TOOL_DASH_PATTERN)
        self._dash_label.setBuddy(self._dash_textbox)
        self._dash_label.setToolTip(self._dash_textbox.toolTip())
        dash_pattern_regex = QRegularExpression('(\\d+\\s+\\d+\\s+)+')
        dash_pattern_validator = QRegularExpressionValidator(dash_pattern_regex, self)
        self._dash_textbox.setValidator(dash_pattern_validator)
        self._dash_textbox.setParent(self)

        def _on_line_style_change(style_name: str) -> None:
            line_style = self._pen_style_dropdown.get_pen_style(style_name)
            for widget in (self._dash_label, self._dash_textbox):
                widget.setVisible(line_style == Qt.PenStyle.CustomDashLine)
        self._pen_style_dropdown.currentTextChanged.connect(_on_line_style_change)
        _on_line_style_change(self._pen_style_dropdown.currentText())
        self._build_layout()

    def _build_layout(self) -> None:
        clear_layout(self._layout, hide=True)
        if self._orientation == Qt.Orientation.Horizontal:
            # widget, row, col, row_span, col_span
            grid_contents: Tuple[Tuple[QWidget, int, int, int, int], ...] = (
                (self._shape_mode_label, 0, 0, 1, 1),
                (self._shape_mode_combobox, 0, 1, 1, 8),
                (self._line_width_slider, 1, 0, 1, 9),
                (self._vertex_spinbox, 2, 0, 1, 4),
                (self._inner_radius_spinbox, 2, 4, 1, 4),
                (Divider(Qt.Orientation.Horizontal), 3, 0, 1, 9),
                (Divider(Qt.Orientation.Vertical), 4, 4, 5, 1),
                (self._fill_color_button, 5, 0, 1, 4),
                (self._line_color_button, 5, 5, 1, 4),
                (self._fill_pattern_label, 6, 0, 1, 1),
                (self._fill_style_dropdown, 6, 1, 1, 3),
                (self._antialiasing_checkbox, 7, 0, 1, 4),
                (self._pen_style_label, 6, 5, 1, 1),
                (self._pen_style_dropdown, 6, 6, 1, 3),
                (self._pen_join_style_label, 7, 5, 1, 1),
                (self._pen_join_style_dropdown, 7, 6, 1, 3),
                (self._dash_label, 8, 5, 1, 1),
                (self._dash_textbox, 8, 6, 1, 3)
            )
            self._layout.setColumnStretch(1, 1)
            self._layout.setColumnStretch(3, 0)
            self._layout.setColumnStretch(6, 1)
        else:
            assert self._orientation == Qt.Orientation.Vertical
            grid_contents = (
                (self._shape_mode_label, 0, 0, 1, 1),
                (self._shape_mode_combobox, 0, 1, 1, 3),
                (self._vertex_spinbox, 1, 0, 1, 4),
                (self._inner_radius_spinbox, 2, 0, 1, 4),
                (Divider(Qt.Orientation.Horizontal), 3, 0, 1, 4),
                (self._fill_color_button, 4, 0, 1, 2),
                (self._line_color_button, 4, 2, 1, 2),
                (self._fill_pattern_label, 5, 0, 1, 1),
                (self._fill_style_dropdown, 5, 1, 1, 3),
                (self._pen_style_label, 6, 0, 1, 1),
                (self._pen_style_dropdown, 6, 1, 1, 3),
                (self._line_width_slider, 7, 0, 1, 4),
                (self._pen_join_style_label, 8, 0, 1, 1),
                (self._pen_join_style_dropdown, 8, 1, 1, 3),
                (self._antialiasing_checkbox, 9, 0, 1, 4),
                (self._dash_label, 10, 0, 1, 1),
                (self._dash_textbox, 10, 1, 1, 3)
            )
            self._layout.setColumnStretch(1, 1)
            self._layout.setColumnStretch(3, 1)
            self._layout.setColumnStretch(6, 0)
        for widget, row, col, row_span, col_span in grid_contents:
            self._layout.addWidget(widget, row, col, row_span, col_span)
            widget.show()
        shape_mode = ShapeMode.from_text(self._shape_mode_combobox.currentText())
        self._vertex_spinbox.setVisible(shape_mode in (ShapeMode.POLYGON, ShapeMode.STAR))
        self._inner_radius_spinbox.setVisible(shape_mode == ShapeMode.STAR)
        line_style = self._pen_style_dropdown.value()
        self._dash_label.setVisible(line_style == Qt.PenStyle.CustomDashLine)
        self._dash_textbox.setVisible(line_style == Qt.PenStyle.CustomDashLine)

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Update the panel orientation."""
        if self._orientation != orientation:
            self._orientation = orientation
            self._build_layout()
