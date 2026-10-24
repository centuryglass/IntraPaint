"""Shape tool control panel: a Shape section, an Outline section, a Fill section, and Antialiasing.

The panel is a view over the shape tool's `Cache` values:
- Shape: the shape type as a `SegmentedControl`, with Vertices and Inner radius under it for the shapes that use them.
- Outline: Width, the line color with the line style, Dash pattern with its hint while the style is custom, then Join.
- Fill: the fill color with the fill pattern.
- Antialiasing: at the bottom of a side panel, and in the Shape column of a strip.

The shape type and join controls save untranslated names in `Cache` (`ShapeMode.name` and the `JOIN_STYLE_*`
constants), which the shape tool reads. Their segment values are the `ShapeMode` and `_JOIN_STYLES` names.

The panel is a `src.ui.layout.panel_fit.FitContent`, planned in the space the Tools panel gives it:
- Side: one column. The roomy arrangement puts Outline and Fill side by side, the compact one stacks them. The shape
  type and join show labels, or icons where labels don't fit across. Section headers always show.
- Strip: Shape, Outline and Fill are columns of up to `STRIP_SECTION_MAX_WIDTH`. The roomy arrangement gives each
  control its own row. The compact one pairs them into two rows per column, with icon-only shape types. Section headers
  are optional, and Width is labeled "Outline" and the fill row "Fill" while they are hidden.
- Join is optional: a plan without room for it moves it to `overflow_content`, which the Tools panel shows in its More
  popover.
"""
from typing import Optional

from PySide6.QtCore import QEvent, QRegularExpression, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPalette, QPen, QRegularExpressionValidator
from PySide6.QtWidgets import QApplication, QCheckBox, QGridLayout, QLabel, QLineEdit, QSizePolicy, QWidget

from src.config.cache import Cache
from src.ui.ink_style import signal_color
from src.ui.input_fields.fill_style_combo_box import FillStyleComboBox
from src.ui.input_fields.number_field import NumberField
from src.ui.input_fields.pen_join_style_combo_box import (JOIN_STYLE_BEVEL, JOIN_STYLE_LABELS, JOIN_STYLE_MITER,
                                                          JOIN_STYLE_ROUND,
                                                          PenJoinStyleComboBox)
from src.ui.input_fields.pen_style_combo_box import PenStyleComboBox
from src.ui.input_fields.segmented_control import DisplayMode, Segment, SegmentedControl
from src.ui.input_fields.shape_mode_combo_box import ShapeModeComboBox
from src.ui.input_fields.slider_field import SliderField
from src.ui.layout.label_column_layout import normalize_row_label
from src.ui.layout.panel_fit import REQUIRED, FitItem, FitPlanner, Orientation, Placement
from src.ui.panel.tool_control_panels.fit_tool_panel import FitToolPanel
from src.ui.widget.color_button import ColorButton
from src.ui.widget.panel_section import PanelSection
from src.util.visual.shape_mode import ShapeMode

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.shape_tool_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


SHAPE_SECTION_TITLE = _tr('Shape')
OUTLINE_SECTION_TITLE = _tr('Outline')
FILL_SECTION_TITLE = _tr('Fill')
VERTICES_LABEL = _tr('Vertices')
INNER_RADIUS_LABEL = _tr('Inner radius')
WIDTH_LABEL = _tr('Width')
COLOR_LABEL = _tr('Color')
DASH_LABEL = _tr('Dash')
JOIN_LABEL = _tr('Join')
NO_LINE_TEXT = _tr('none')
PIXEL_SUFFIX = _tr(' px')
DASH_HINT = _tr('Dash and gap lengths in px, in pairs')
SHAPE_SUMMARY_STAR = _tr('{shape}, {count} points')
SHAPE_SUMMARY_POLYGON = _tr('{shape}, {count} vertices')
OUTLINE_SUMMARY = _tr('{width} {style}')

# Pairs of whole numbers separated by spaces, such as "6 3" or "6 3 2 3":
DASH_PATTERN_REGEX = r'\s*(\d+\s+\d+\s*)+'
MIN_COMBO_CHARACTERS = 6
SECTION_SPACING = 10
SEGMENT_ICON_LINE_WIDTH = 6

_JOIN_STYLES = {
    'ROUND': (JOIN_STYLE_ROUND, Qt.PenJoinStyle.RoundJoin),
    'BEVEL': (JOIN_STYLE_BEVEL, Qt.PenJoinStyle.BevelJoin),
    'MITER': (JOIN_STYLE_MITER, Qt.PenJoinStyle.MiterJoin),
}

# The planned items, in placement order:
SHAPE_TYPE_ITEM = FitItem(REQUIRED, 2)
ARRANGEMENT_ITEM = FitItem(REQUIRED, 2)
JOIN_ITEM = FitItem(1, 2)
HEADERS_ITEM = FitItem(2)
# Forms of the shape type and join items:
LABELS = 0
ICONS = 1
# Forms of the arrangement item:
ROOMY = 0
COMPACT = 1


def _shape_mode(mode_text: str) -> Optional[ShapeMode]:
    try:
        return ShapeMode.from_text(mode_text)
    except ValueError:
        return None


def _join_name(join_option: str) -> Optional[str]:
    for name, (option, _) in _JOIN_STYLES.items():
        if option == join_option:
            return name
    return None


def build_dash_pattern_validator(parent: Optional[QWidget] = None) -> QRegularExpressionValidator:
    """Returns a validator that accepts dash patterns: one or more pairs of dash and gap lengths, separated by spaces.
    An odd count of numbers is intermediate input, never acceptable."""
    return QRegularExpressionValidator(QRegularExpression(DASH_PATTERN_REGEX), parent)


class ShapeToolPanel(FitToolPanel):
    """Shape tool control panel. Sets shape type, outline properties, and fill properties.

    Without a host that calls `set_fit_space`, the panel plans for its own size when resized.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        cache = Cache()
        # Whether the Outline rows are paired, which drops the dash pattern's label and hint:
        self._paired = False
        if _shape_mode(cache.get(Cache.SHAPE_TOOL_MODE)) is None:
            cache.set(Cache.SHAPE_TOOL_MODE, ShapeMode.ELLIPSE.name)

        # Shape section:
        self._shape_control = SegmentedControl([Segment(mode.name, mode.display_text(), self._shape_icon(mode))
                                                for mode in ShapeMode], DisplayMode.LABEL, parent=self)
        self._shape_control.setToolTip(cache.get_tooltip(Cache.SHAPE_TOOL_MODE))
        self._shape_control.valueChanged.connect(
            lambda name: cache.set(Cache.SHAPE_TOOL_MODE, ShapeMode[name].name))
        self._vertex_field = self._bound_field(Cache.SHAPE_TOOL_VERTEX_COUNT, VERTICES_LABEL)
        self._inner_radius_field = self._bound_field(Cache.SHAPE_TOOL_STAR_INNER_POINT_FRACTION, INNER_RADIUS_LABEL,
                                                     step=0.01, page_step=0.1)
        self._antialias_checkbox = cache.get_control_widget(Cache.SHAPE_TOOL_ANTIALIAS)
        if isinstance(self._antialias_checkbox, QCheckBox):
            self._antialias_checkbox.setText(normalize_row_label(cache.get_label(Cache.SHAPE_TOOL_ANTIALIAS)))
        self._antialias_checkbox.setParent(self)
        self._antialias_checkbox.show()
        self._shape_body = QWidget(self)
        self._shape_layout = self._body_grid(self._shape_body)
        self._shape_section = PanelSection(SHAPE_SECTION_TITLE, self._shape_body, parent=self)
        self._shape_section.bind_summary(self._shape_summary, self._shape_control.valueChanged,
                                         self._vertex_field.valueChanged)

        # Outline section:
        self._width_field = self._bound_field(Cache.SHAPE_TOOL_LINE_WIDTH, WIDTH_LABEL, suffix=PIXEL_SUFFIX,
                                              zero_text=NO_LINE_TEXT)
        self._line_color_label = QLabel(COLOR_LABEL, self)
        self._line_color_button = self._swatch(Cache.SHAPE_TOOL_LINE_COLOR)
        self._pen_style_dropdown = PenStyleComboBox(Cache.SHAPE_TOOL_LINE_STYLE, self)
        self._fit_combo(self._pen_style_dropdown)
        self._line_color_label.setBuddy(self._line_color_button)
        self._dash_label = QLabel(DASH_LABEL, self)
        self._dash_textbox = cache.get_control_widget(Cache.SHAPE_TOOL_DASH_PATTERN)
        assert isinstance(self._dash_textbox, QLineEdit)
        self._dash_textbox.setValidator(build_dash_pattern_validator(self))
        self._dash_textbox.setParent(self)
        self._dash_label.setBuddy(self._dash_textbox)
        self._dash_textbox.setToolTip(f'{self._dash_textbox.toolTip()}\n{DASH_HINT}')
        self._dash_label.setToolTip(self._dash_textbox.toolTip())
        self._dash_hint = QLabel(DASH_HINT, self)
        self._dash_hint.setWordWrap(True)
        self._dash_textbox.textChanged.connect(self._update_dash_hint)
        self._update_dash_hint()
        self._join_label = QLabel(JOIN_LABEL, self)
        self._join_control = SegmentedControl([Segment(name, JOIN_STYLE_LABELS[option], None) for name, (option, _) in
                                               _JOIN_STYLES.items()], DisplayMode.LABEL, parent=self)
        self._join_control.setToolTip(cache.get_tooltip(Cache.SHAPE_TOOL_LINE_JOIN_STYLE))
        self._join_control.valueChanged.connect(
            lambda name: cache.set(Cache.SHAPE_TOOL_LINE_JOIN_STYLE, _JOIN_STYLES[name][0]))
        self._outline_body = QWidget(self)
        self._outline_layout = self._body_grid(self._outline_body)
        self._outline_section = PanelSection(OUTLINE_SECTION_TITLE, self._outline_body, parent=self)
        self._outline_section.bind_summary(self._outline_summary, self._width_field.valueChanged,
                                           self._pen_style_dropdown.currentTextChanged)

        # Fill section:
        self._fill_color_label = QLabel(COLOR_LABEL, self)
        self._fill_color_button = self._swatch(Cache.SHAPE_TOOL_FILL_COLOR)
        self._fill_color_label.setBuddy(self._fill_color_button)
        self._fill_style_dropdown = FillStyleComboBox(Cache.SHAPE_TOOL_FILL_PATTERN, True, self)
        self._fit_combo(self._fill_style_dropdown)
        self._fill_body = QWidget(self)
        self._fill_layout = self._body_grid(self._fill_body)
        self._fill_section = PanelSection(FILL_SECTION_TITLE, self._fill_body, parent=self)
        self._fill_section.bind_summary(self._fill_style_dropdown.currentText,
                                        self._fill_style_dropdown.currentTextChanged)

        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(SECTION_SPACING)
        self._sections = (self._shape_section, self._outline_section, self._fill_section)

        cache.connect(self, Cache.SHAPE_TOOL_MODE, self._shape_mode_changed)
        cache.connect(self, Cache.SHAPE_TOOL_LINE_JOIN_STYLE, self._join_style_changed)
        self._pen_style_dropdown.currentTextChanged.connect(self._line_style_changed)
        for cache_key in (Cache.SHAPE_TOOL_VERTEX_COUNT, Cache.SHAPE_TOOL_STAR_INNER_POINT_FRACTION):
            cache.connect(self._shape_control, cache_key, self._update_shape_icons)
        cache.connect(self._fill_style_dropdown, Cache.SHAPE_TOOL_FILL_COLOR, self._update_fill_icons)
        cache.connect(self._pen_style_dropdown, Cache.SHAPE_TOOL_LINE_COLOR, self._update_line_icons)
        self._update_fill_icons(cache.get(Cache.SHAPE_TOOL_FILL_COLOR))
        self._update_line_icons(cache.get(Cache.SHAPE_TOOL_LINE_COLOR))
        self._join_style_changed(cache.get(Cache.SHAPE_TOOL_LINE_JOIN_STYLE))
        self._shape_mode_changed(cache.get(Cache.SHAPE_TOOL_MODE), refit=False)
        self._line_style_changed(self._pen_style_dropdown.currentText(), refit=False)

        self._planner = FitPlanner([SHAPE_TYPE_ITEM, ARRANGEMENT_ITEM, JOIN_ITEM, HEADERS_ITEM], self._apply_fit,
                                   self._measure_fit)
        self._apply_fit(Orientation.SIDE, (LABELS, ROOMY, LABELS, 0))

    # -----------------------------------------------------------------------------------------------------------------
    # Controls
    # -----------------------------------------------------------------------------------------------------------------

    @property
    def shape_control(self) -> SegmentedControl:
        """The shape type control."""
        return self._shape_control

    @property
    def join_control(self) -> SegmentedControl:
        """The line join control."""
        return self._join_control

    @property
    def dash_textbox(self) -> QLineEdit:
        """The dash pattern field."""
        assert isinstance(self._dash_textbox, QLineEdit)
        return self._dash_textbox

    @property
    def dash_hint(self) -> QLabel:
        """The hint line under the dash pattern field."""
        return self._dash_hint

    @property
    def vertex_field(self) -> NumberField:
        """The Vertices field."""
        return self._vertex_field

    @property
    def inner_radius_field(self) -> NumberField:
        """The Inner radius field."""
        return self._inner_radius_field

    @property
    def width_field(self) -> NumberField:
        """The outline Width field."""
        return self._width_field

    def _bound_field(self, key: str, label: str, **kwargs) -> SliderField:
        """Returns a slider field bound to a numeric Cache key."""
        cache = Cache()
        minimum, maximum, step = cache.get_range(key)
        if minimum is None or maximum is None or step is None:
            raise ValueError(f'Cache key {key} needs a numeric range')
        kwargs.setdefault('step', step)
        field = SliderField(label, cache.get(key), minimum, maximum, parent=self, **kwargs)
        field.setToolTip(cache.get_tooltip(key))

        def _field_changed(value: int | float) -> None:
            if cache.get(key) != value:
                cache.set(key, value)

        field.valueChanged.connect(_field_changed)
        cache.connect(field, key, lambda value, *_: field.set_value(value))
        return field

    def _swatch(self, key: str) -> ColorButton:
        button = ColorButton(key, self)
        button.setText('')
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        return button

    @staticmethod
    def _fit_combo(combo_box: PenStyleComboBox | FillStyleComboBox) -> None:
        combo_box.setSizeAdjustPolicy(combo_box.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo_box.setMinimumContentsLength(MIN_COMBO_CHARACTERS)
        combo_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _shape_icon(self, mode: ShapeMode) -> QIcon:
        cache = Cache()
        line_color = self.palette().color(QPalette.ColorRole.WindowText)
        pen = QPen(line_color, SEGMENT_ICON_LINE_WIDTH)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return ShapeModeComboBox.draw_icon(mode, pen, QBrush(Qt.BrushStyle.NoBrush),
                                           cache.get(Cache.SHAPE_TOOL_VERTEX_COUNT),
                                           cache.get(Cache.SHAPE_TOOL_STAR_INNER_POINT_FRACTION),
                                           Qt.GlobalColor.transparent)

    def _update_shape_icons(self, _=None) -> None:
        for mode in ShapeMode:
            self._shape_control.set_segment_icon(mode.name, self._shape_icon(mode))

    def _update_join_icons(self) -> None:
        line_color = self.palette().color(QPalette.ColorRole.WindowText)
        for name, (_, join_style) in _JOIN_STYLES.items():
            icon = PenJoinStyleComboBox.draw_icon(join_style, line_color, Qt.GlobalColor.transparent)
            self._join_control.set_segment_icon(name, QIcon(icon))

    def _update_fill_icons(self, color_str: str) -> None:
        if QColor(color_str).isValid():
            self._fill_style_dropdown.set_icon_colors(QColor(color_str))

    def _update_line_icons(self, color_str: str) -> None:
        if QColor(color_str).isValid():
            self._pen_style_dropdown.set_icon_colors(QColor(color_str))

    def _shape_mode_changed(self, mode_text: str, refit: bool = True) -> None:
        mode = _shape_mode(mode_text)
        if mode is None:
            return
        self._shape_control.set_value(mode.name)
        self._vertex_field.setVisible(mode in (ShapeMode.POLYGON, ShapeMode.STAR))
        self._inner_radius_field.setVisible(mode == ShapeMode.STAR)
        if refit:
            self._refit()

    def _join_style_changed(self, join_text: str) -> None:
        name = _join_name(join_text)
        self._join_control.set_value(name if name is not None else 'ROUND')

    def _custom_dash(self) -> bool:
        return self._pen_style_dropdown.value() == Qt.PenStyle.CustomDashLine

    def _line_style_changed(self, _style_name: str, refit: bool = True) -> None:
        """Shows the dash pattern field while the line style is custom, with its label and hint unless the Outline
        rows are paired."""
        custom = self._custom_dash()
        self._dash_textbox.setVisible(custom)
        for widget in (self._dash_label, self._dash_hint):
            widget.setVisible(custom and not self._paired)
        if refit:
            self._refit()

    def _update_dash_hint(self, _=None) -> None:
        """Draws the hint and the dash pattern in the signal color while the pattern can't be used, and the hint dim
        otherwise."""
        invalid = self.dash_textbox.text().strip() != '' and not self.dash_textbox.hasAcceptableInput()
        signal = signal_color()
        if signal is None:
            signal = QColor(Qt.GlobalColor.red)
        hint_palette = QPalette(self.palette())
        hint_palette.setColor(QPalette.ColorRole.WindowText,
                              signal if invalid else self.palette().color(QPalette.ColorRole.PlaceholderText))
        self._dash_hint.setPalette(hint_palette)
        field_palette = QPalette(self.palette())
        if invalid:
            field_palette.setColor(QPalette.ColorRole.Text, signal)
        self.dash_textbox.setPalette(field_palette)
        self._dash_hint.setProperty('invalid', invalid)

    def dash_pattern_invalid(self) -> bool:
        """Returns whether the hint under the dash pattern field marks its text as unusable."""
        return bool(self._dash_hint.property('invalid'))

    def _shape_summary(self) -> str:
        mode = ShapeMode[self._shape_control.value()]
        count = self._vertex_field.value_text()
        if mode == ShapeMode.STAR:
            return SHAPE_SUMMARY_STAR.format(shape=mode.display_text(), count=count)
        if mode == ShapeMode.POLYGON:
            return SHAPE_SUMMARY_POLYGON.format(shape=mode.display_text(), count=count)
        return mode.display_text()

    def _outline_summary(self) -> str:
        if self._width_field.value() == 0:
            return self._width_field.value_text()
        return OUTLINE_SUMMARY.format(width=self._width_field.value_text(),
                                      style=self._pen_style_dropdown.currentText())

    def changeEvent(self, event: Optional[QEvent]) -> None:  # pylint: disable=invalid-name
        """Redraws the segment icons in the new text color after a palette change."""
        super().changeEvent(event)
        if event is not None and event.type() == QEvent.Type.PaletteChange:
            self._update_shape_icons()
            self._update_join_icons()
            self._update_dash_hint()

    # -----------------------------------------------------------------------------------------------------------------
    # Layout
    # -----------------------------------------------------------------------------------------------------------------

    def _apply_fit(self, orientation: Orientation, placement: Placement) -> None:
        shape_form, arrangement, join_form, headers = placement
        self._orientation = orientation
        strip = orientation == Orientation.STRIP
        compact = arrangement == COMPACT
        # A strip plans by height, where both shape type forms are the same, so its compact form picks the icons:
        shape_icons = compact if strip else shape_form == ICONS
        self._shape_control.set_display_mode(DisplayMode.ICON if shape_icons else DisplayMode.LABEL)
        if join_form is not None:
            if self._join_control.segments[0].icon is None:
                self._update_join_icons()
            self._join_control.set_display_mode(DisplayMode.ICON if join_form == ICONS else DisplayMode.LABEL)
        show_headers = not strip or headers is not None
        for section in self._sections:
            section.set_header_visible(show_headers)
        self._width_field.set_label(WIDTH_LABEL if show_headers else OUTLINE_SECTION_TITLE)
        self._fill_color_label.setText(COLOR_LABEL if show_headers else FILL_SECTION_TITLE)
        self._arrange_shape(strip, strip and compact)
        self._arrange_outline(strip and compact, join_form is not None)
        self._arrange_fill()
        self._arrange_sections(strip, not strip and not compact)
        # Moving between the Shape section and the panel reparents the checkbox, which hides it:
        self._antialias_checkbox.show()

    def _arrange_shape(self, strip: bool, paired: bool) -> None:
        """Puts the shape type over the Vertices and Inner radius row, with Antialiasing beside the shape type in a
        paired strip and under the fields in a roomy one. A side panel puts Antialiasing below every section."""
        layout = self._shape_layout
        self._clear(layout, (self._shape_control, self._vertex_field, self._inner_radius_field,
                             self._antialias_checkbox))
        if paired:
            layout.addWidget(self._shape_control, 0, 0)
            layout.addWidget(self._antialias_checkbox, 0, 1)
        else:
            layout.addWidget(self._shape_control, 0, 0, 1, 2)
        layout.addWidget(self._vertex_field, 1, 0)
        layout.addWidget(self._inner_radius_field, 1, 1)
        if strip and not paired:
            layout.addWidget(self._antialias_checkbox, 2, 0, 1, 2)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

    def _arrange_outline(self, paired: bool, join_shown: bool) -> None:
        """Lays out the Outline rows: labeled rows, or in a paired strip Width beside the color, then the line style
        beside Join, or beside Dash pattern with Join under them while the style is custom."""
        self._paired = paired
        layout = self._outline_layout
        widgets = (self._width_field, self._line_color_label, self._line_color_button, self._pen_style_dropdown,
                   self._dash_label, self._dash_textbox, self._dash_hint, self._join_label, self._join_control)
        self._clear(layout, widgets)
        if join_shown:
            self._overflow_layout.removeWidget(self._join_label)
            self._overflow_layout.removeWidget(self._join_control)
        else:
            self._overflow_layout.addWidget(self._join_label)
            self._overflow_layout.addWidget(self._join_control)
        self._join_label.show()
        self._join_control.show()
        if paired:
            layout.addWidget(self._width_field, 0, 0)
            layout.addWidget(self._line_color_button, 0, 1)
            layout.addWidget(self._pen_style_dropdown, 1, 0)
            custom = self._custom_dash()
            if custom:
                layout.addWidget(self._dash_textbox, 1, 1)
            if join_shown:
                layout.addWidget(self._join_control, 2 if custom else 1, 0 if custom else 1, 1, 2 if custom else 1)
                self._join_label.hide()
            layout.setColumnStretch(0, 1)
            self._line_color_label.hide()
            self._line_style_changed(self._pen_style_dropdown.currentText(), refit=False)
            return
        layout.addWidget(self._width_field, 0, 0, 1, 3)
        layout.addWidget(self._line_color_label, 1, 0)
        layout.addWidget(self._line_color_button, 1, 1)
        layout.addWidget(self._pen_style_dropdown, 1, 2)
        layout.addWidget(self._dash_label, 2, 0)
        layout.addWidget(self._dash_textbox, 2, 1, 1, 2)
        layout.addWidget(self._dash_hint, 3, 1, 1, 2)
        if join_shown:
            layout.addWidget(self._join_label, 4, 0)
            layout.addWidget(self._join_control, 4, 1, 1, 2)
        layout.setColumnStretch(2, 1)
        self._line_color_label.show()
        self._line_style_changed(self._pen_style_dropdown.currentText(), refit=False)

    def _arrange_fill(self) -> None:
        layout = self._fill_layout
        self._clear(layout, (self._fill_color_label, self._fill_color_button, self._fill_style_dropdown))
        layout.addWidget(self._fill_color_label, 0, 0)
        layout.addWidget(self._fill_color_button, 0, 1)
        layout.addWidget(self._fill_style_dropdown, 0, 2)
        layout.setColumnStretch(2, 1)

    def _arrange_sections(self, strip: bool, beside: bool) -> None:
        """Places the sections in strip columns, side by side under Shape, or stacked, with spare room after them."""
        grid = self._grid
        self._clear(grid, (*self._sections, self._antialias_checkbox))
        top = Qt.AlignmentFlag.AlignTop
        if strip:
            for column, section in enumerate(self._sections):
                grid.addWidget(section, 0, column, top)
            spare_column = len(self._sections)
            grid.setRowStretch(1, 1)
        elif beside:
            grid.addWidget(self._shape_section, 0, 0, 1, 2, top)
            grid.addWidget(self._outline_section, 1, 0, top)
            grid.addWidget(self._fill_section, 1, 1, top)
            grid.addWidget(self._antialias_checkbox, 2, 0, 1, 2, top)
            spare_column = 2
            grid.setRowStretch(3, 1)
        else:
            for row, widget in enumerate((*self._sections, self._antialias_checkbox)):
                grid.addWidget(widget, row, 0, top)
            spare_column = 1
            grid.setRowStretch(4, 1)
        for column in range(spare_column):
            grid.setColumnStretch(column, 1)
        grid.setColumnStretch(spare_column, 0)
        for section in self._sections:
            self._cap_width(section)
