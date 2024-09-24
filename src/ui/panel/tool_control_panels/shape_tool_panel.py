"""Shape tool control panel. Sets shape type, stroke properties, and fill properties."""
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QSize, QRegularExpression
from PySide6.QtGui import QIcon, QPen, QBrush, QColor, QRegularExpressionValidator
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
                (self._dash_label, 9, 0, 1, 1),
                (self._dash_textbox, 9, 1, 1, 3)
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

    # noinspection PyUnusedLocal
    def _update_mode_icons(self, *args, **kwargs) -> None:
        for mode in ShapeMode:
            mode_icon = self._draw_shape_preview_icon(mode)
            self._shape_mode_combobox.setItemIcon(mode.value, mode_icon)

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Update the panel orientation."""
        if self._orientation != orientation:
            self._orientation = orientation
            self._build_layout()

    @staticmethod
    def _draw_shape_preview_icon(mode: ShapeMode) -> QIcon:
        cache = Cache()

        # Create pen from config properties:
        drawn_icon_size = ICON_SIZE * 4
        line_color = cache.get_color(Cache.SHAPE_TOOL_LINE_COLOR, Qt.GlobalColor.black)
        line_width = min(cache.get(Cache.SHAPE_TOOL_LINE_WIDTH), drawn_icon_size // 8)
        try:
            line_style = PenStyleComboBox.get_pen_style(cache.get(Cache.SHAPE_TOOL_LINE_STYLE))
        except KeyError:
            line_style = Qt.PenStyle.SolidLine
        if line_style == Qt.PenStyle.CustomDashLine:
            line_style = Qt.PenStyle.DashLine  # Don't worry about line style on preview icons
        line_pen = QPen(line_color, line_width, line_style)

        # Create brush from config properties:
        fill_color = cache.get_color(Cache.SHAPE_TOOL_FILL_COLOR, Qt.GlobalColor.white)
        fill_brush = QBrush(fill_color)
        try:
            fill_brush.setStyle(FillStyleComboBox.get_style(cache.get(Cache.SHAPE_TOOL_FILL_PATTERN)))
        except KeyError:
            fill_brush.setStyle(Qt.BrushStyle.SolidPattern)

        return ShapeModeComboBox.draw_icon(mode, line_pen, fill_brush, cache.get(Cache.SHAPE_TOOL_VERTEX_COUNT),
                                           cache.get(Cache.SHAPE_TOOL_STAR_INNER_POINT_FRACTION))
