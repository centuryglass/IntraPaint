"""The stroke controls shared by the brush-like tool panels, and the panel that hosts them.

`StrokeBlock` is a view over `Cache` values, in a fixed order so Size never moves between tools:

1. A Stroke section: Size, Opacity and Hardness as `SliderField`s, with pen pressure links inside the fields. The
   links appear once a tablet has been seen and add no row. Key hints are in the field tooltips.
2. A "Color and options" section, or "Options" for a tool with no color: the color pair and Pattern if the tool
   paints a color, then Antialiasing and "Only inside selection".

Both sections are `PanelSection`s that collapse to a summary line. A strip too short for headers hides them.

Tool-specific sections go after the block, in `StrokeToolPanel`. Sections added with `StrokeBlock.add_tool_section`
join the block's grid, and can be planned with its items.

Layout is planned by fit (`src.ui.layout.panel_fit`) in the space the Tools panel gives `StrokeToolPanel`:
- Side: the Stroke and options sections share column 1, and a preview beside them takes column 2. Tool sections go
  below, spanning every column up to their own width caps. Strip: the Stroke section in column 1, the options section
  in column 2, a preview beside them in column 3, and one column per tool section after that.
- Every control column stops at `FIELD_COLUMN_MAX_WIDTH`, so a wide panel leaves spare width after the last column
  instead of stretching the columns apart.
- The color pair and Pattern, and the checkboxes, are required items. In a side panel each row stacks into a column
  when it doesn't fit across. In a strip the color pair row stays inline, because stacking would make it taller.
- In a strip, the checkboxes take one row each when the strip is tall enough for the extra row. A tool with a color
  pair keeps them on one row unless that row is wider than the options column's cap, which would cut off a label.
- A tool with a `StrokePreview` shows it beside the fields or below them in the Stroke section, or hides it. A side
  panel prefers below, where the preview can take the column's width, and goes beside only when below doesn't fit. A
  strip prefers beside, since height is what it lacks. The preview is decorative, so it never moves to the More
  popover. Beside the fields, they keep at least `BESIDE_FIELD_MIN_WIDTH`.
- Headers are required in a side panel and optional in a strip, where they cost height.
"""
from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QColor, QResizeEvent
from PySide6.QtWidgets import (QApplication, QBoxLayout, QCheckBox, QGridLayout, QLabel, QLayout, QVBoxLayout,
                               QWidget)

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.ui.ink_style import set_signal
from src.ui.input_fields.fill_style_combo_box import FillStyleComboBox
from src.ui.input_fields.number_field import NumberField
from src.ui.input_fields.slider_field import SliderField
from src.ui.panel.tool_control_panels.stroke_preview import StrokePreview
from src.ui.layout.panel_fit import REQUIRED, FitItem, FitPlanner, Orientation, Placement, fresh_minimum_size, \
    held_weakly
from src.ui.layout.label_column_layout import normalize_row_label
from src.ui.widget.color_pair_widget import ColorPairWidget
from src.ui.widget.panel_section import PanelSection

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.stroke_block'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


ONLY_INSIDE_SELECTION_LABEL = _tr('Only inside selection')
STROKE_SECTION_TITLE = _tr('Stroke')
COLOR_AND_OPTIONS_SECTION_TITLE = _tr('Color and options')
OPTIONS_SECTION_TITLE = _tr('Options')
PIXEL_SUFFIX = _tr(' px')
PERCENT_SUFFIX = _tr('%')
KEYS_TOOLTIP = _tr('{description}\nKeys: {decrease} / {increase}')

BESIDE_FIELD_MIN_WIDTH = 200
FIELD_COLUMN_MAX_WIDTH = 290
COLUMN_SPACING = 10
MIN_PATTERN_CHARACTERS = 6
# Capped columns share width until they reach their caps, and a spare column after them takes what is left. Without
# it the layout would center each capped column in a wider cell:
CONTROL_COLUMN_STRETCH = 100
SPARE_COLUMN_STRETCH = 1

# The block's planner items, and their forms:
HEADERS_ITEM = 'headers'
PAINT_ITEM = 'paint'
CHECKS_ITEM = 'checks'
PREVIEW_ITEM = 'preview'
INLINE = 0
STACKED = 1
BESIDE = 0
BELOW = 1
# The preview's planner forms are tried in order, so each orientation lists the layout it prefers first:
_PREVIEW_FORMS = {Orientation.SIDE: (BELOW, BESIDE), Orientation.STRIP: (BESIDE, BELOW)}
HEADERS_PRIORITY = 1
PREVIEW_PRIORITY = 2
_FIT_ITEMS = {
    HEADERS_ITEM: FitItem(HEADERS_PRIORITY),
    PAINT_ITEM: FitItem(REQUIRED, 2),
    CHECKS_ITEM: FitItem(REQUIRED, 2),
    PREVIEW_ITEM: FitItem(PREVIEW_PRIORITY, 2),
}


@dataclass(frozen=True)
class StrokeArrangement:
    """How a `StrokeBlock` is laid out: the orientation, whether each row is stacked into a column, the preview's
    form or None while it is hidden, and whether the section headers show."""
    orientation: Orientation
    paint_stacked: bool = False
    checks_stacked: bool = False
    preview: Optional[int] = None
    headers: bool = True


def build_paint_row(color_key: Optional[str], pattern_key: Optional[str], parent: QWidget) -> Optional[QWidget]:
    """Returns the color pair and Pattern dropdown as one row, or None if the tool has neither."""
    if color_key is None and pattern_key is None:
        return None
    cache = Cache()
    row = QWidget(parent)
    row_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    if color_key == Cache.LAST_BRUSH_COLOR:
        row_layout.addWidget(ColorPairWidget(row))
    if pattern_key is not None:
        pattern_label = QLabel(normalize_row_label(cache.get_label(pattern_key)))
        pattern_dropdown = FillStyleComboBox(pattern_key)
        pattern_label.setBuddy(pattern_dropdown)
        pattern_dropdown.setSizeAdjustPolicy(pattern_dropdown.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        pattern_dropdown.setMinimumContentsLength(MIN_PATTERN_CHARACTERS)
        row_layout.addWidget(pattern_label)
        row_layout.addWidget(pattern_dropdown, stretch=1)  # Stretches to the row's edge, see `StrokeBlock._arrange`
        if color_key is not None:
            def _pattern_color_update(color_str: str, *_) -> None:
                if QColor(color_str).isValid():
                    pattern_dropdown.set_icon_colors(QColor(color_str))

            cache.connect(row, color_key, _pattern_color_update)
            pattern_dropdown.set_icon_colors(cache.get_color(color_key, Qt.GlobalColor.black))
    if pattern_key is None:
        row_layout.addStretch(1)
    return row


def tool_section(title: str, *items: QWidget | QLayout) -> PanelSection:
    """Returns a titled section holding `items` in a column, for a tool panel's sections after the stroke block."""
    body = QWidget()
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(0, 0, 0, 0)
    for item in items:
        if isinstance(item, QLayout):
            body_layout.addLayout(item)
        else:
            body_layout.addWidget(item)
    return PanelSection(title, body)


def build_selection_only_checkbox() -> QWidget:
    """Returns the "Only inside selection" checkbox shared by every tool that paints."""
    checkbox = Cache().get_control_widget(Cache.PAINT_SELECTION_ONLY)
    set_signal(checkbox)
    if isinstance(checkbox, QCheckBox):
        checkbox.setText(ONLY_INSIDE_SELECTION_LABEL)
    return checkbox


class StrokeBlock(QWidget):
    """Size, Opacity and Hardness fields, the color pair and Pattern, and the shared checkboxes.

    `size_label` and `opacity_label` replace the Cache labels, for tools that name those values differently (the
    smudge and filter tools call opacity "Strength"). `opacity_tooltip` replaces the description to match.
    `preview` is the tool's stroke preview, if it has one.
    """

    def __init__(self, size_key: str, opacity_key: Optional[str] = None, hardness_key: Optional[str] = None,
                 pressure_size_key: Optional[str] = None, pressure_opacity_key: Optional[str] = None,
                 pressure_hardness_key: Optional[str] = None, color_key: Optional[str] = None,
                 pattern_key: Optional[str] = None, antialias_key: Optional[str] = None,
                 preview: Optional[StrokePreview] = None, opacity_label: Optional[str] = None,
                 opacity_tooltip: Optional[str] = None, size_label: Optional[str] = None,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        cache = Cache()
        self._label_overrides = {size_key: size_label}
        self._tooltip_overrides: dict[str, Optional[str]] = {}
        if opacity_key is not None:
            self._label_overrides[opacity_key] = opacity_label
            self._tooltip_overrides[opacity_key] = opacity_tooltip
        self._fields: dict[str, NumberField] = {}
        self._pressure_fields: list[NumberField] = []
        self._arrangement: Optional[StrokeArrangement] = None

        self._fields_widget = QWidget()
        fields_layout = QVBoxLayout(self._fields_widget)
        fields_layout.setContentsMargins(0, 0, 0, 0)
        fields_layout.setSpacing(4)
        for key, pressure_key, decrease, increase, suffix, scale in (
                (size_key, pressure_size_key, KeyConfig.BRUSH_SIZE_DECREASE, KeyConfig.BRUSH_SIZE_INCREASE,
                 PIXEL_SUFFIX, 1.0),
                (opacity_key, pressure_opacity_key, KeyConfig.BRUSH_OPACITY_DECREASE,
                 KeyConfig.BRUSH_OPACITY_INCREASE, PERCENT_SUFFIX, 100.0),
                (hardness_key, pressure_hardness_key, KeyConfig.BRUSH_HARDNESS_DECREASE,
                 KeyConfig.BRUSH_HARDNESS_INCREASE, PERCENT_SUFFIX, 100.0)):
            if key is None:
                continue
            field = self._build_field(key, pressure_key, decrease, increase, suffix, scale)
            self._fields[key] = field
            fields_layout.addWidget(field)
        self._field_keys = list(self._fields)

        self._paint_widget = build_paint_row(color_key, pattern_key, self)
        paint_layout = self._paint_widget.layout() if self._paint_widget is not None else None
        self._paint_layout = paint_layout if isinstance(paint_layout, QBoxLayout) else None

        self._checks_widget = QWidget()
        self._checks_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self._checks_widget)
        self._checks_layout.setContentsMargins(0, 0, 0, 0)
        self._checks_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        if antialias_key is not None:
            antialias_checkbox = cache.get_control_widget(antialias_key)
            if isinstance(antialias_checkbox, QCheckBox):
                antialias_checkbox.setText(normalize_row_label(cache.get_label(antialias_key)))
            self._checks_layout.addWidget(antialias_checkbox)
        self._checks_layout.addWidget(build_selection_only_checkbox())

        self._preview = preview
        if preview is not None:
            preview.setParent(self)

        self._stroke_body = QWidget()
        self._stroke_layout = QVBoxLayout(self._stroke_body)
        self._stroke_layout.setContentsMargins(0, 0, 0, 0)
        self._stroke_layout.setSpacing(6)
        self._stroke_layout.addWidget(self._fields_widget)
        self._stroke_section = PanelSection(STROKE_SECTION_TITLE, self._stroke_body)
        self._stroke_section.bind_summary(self._stroke_summary,
                                          *(field.valueChanged for field in self._fields.values()))
        self._options_body = QWidget()
        options_layout = QVBoxLayout(self._options_body)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(6)
        if self._paint_widget is not None:
            options_layout.addWidget(self._paint_widget)
        options_layout.addWidget(self._checks_widget)
        self._options_section = PanelSection(
            COLOR_AND_OPTIONS_SECTION_TITLE if self._paint_widget is not None else OPTIONS_SECTION_TITLE,
            self._options_body)

        # The tool's own sections, after the block's, and whether each takes the height the others leave:
        self._tool_sections: list[tuple[PanelSection, bool]] = []
        # Each tool section's grid column in a strip:
        self._tool_columns: dict[PanelSection, int] = {}
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(COLUMN_SPACING)
        self._grid.setVerticalSpacing(6)
        self._fit_keys = [key for key, present in ((HEADERS_ITEM, True), (PAINT_ITEM, self._paint_widget is not None),
                                                   (CHECKS_ITEM, True), (PREVIEW_ITEM, self._preview is not None))
                          if present]
        self._arrange(StrokeArrangement(Orientation.SIDE))

    # -----------------------------------------------------------------------------------------------------------------
    # Fields
    # -----------------------------------------------------------------------------------------------------------------

    def field(self, key: str) -> NumberField:
        """Returns the field bound to a Cache key."""
        return self._fields[key]

    def fields(self) -> list[NumberField]:
        """Returns the Size, Opacity and Hardness fields that exist, in display order."""
        return [self._fields[key] for key in self._field_keys]

    def _build_field(self, key: str, pressure_key: Optional[str], decrease_key: str, increase_key: str, suffix: str,
                     display_scale: float) -> NumberField:
        cache = Cache()
        minimum, maximum, step = cache.get_range(key)
        label = self._label_overrides.get(key) or normalize_row_label(cache.get_label(key))
        if minimum is None or maximum is None or step is None:
            raise ValueError(f'Cache key {key} needs a numeric range')
        field = SliderField(label, cache.get(key), minimum, maximum, step=step, suffix=suffix,
                            display_scale=display_scale, parent=self)
        description = self._tooltip_overrides.get(key) or cache.get_tooltip(key)
        keys = KeyConfig()
        field.setToolTip(KEYS_TOOLTIP.format(description=description, decrease=keys.get(decrease_key),
                                             increase=keys.get(increase_key)))

        def _field_changed(value: int | float) -> None:
            if cache.get(key) != value:
                cache.set(key, value)

        field.valueChanged.connect(_field_changed)
        cache.connect(self, key, lambda value, *_: field.set_value(value))
        if pressure_key is not None:
            self._pressure_fields.append(field)
            field.set_pressure_link_tooltip(cache.get_tooltip(pressure_key))
            field.set_pressure_link_enabled(bool(cache.get(pressure_key)))
            field.set_pressure_link_available(bool(cache.get(Cache.EXPECT_TABLET_INPUT)))

            def _link_toggled(enabled: bool) -> None:
                if cache.get(pressure_key) != enabled:
                    cache.set(pressure_key, enabled)

            field.pressureLinkToggled.connect(_link_toggled)
            cache.connect(self, pressure_key, lambda enabled, *_: field.set_pressure_link_enabled(bool(enabled)))
        return field

    def show_pressure_links(self) -> None:
        """Reveals the pressure links on the fields that have one, once a tablet has been seen."""
        for field in self._pressure_fields:
            field.set_pressure_link_available(True)

    # -----------------------------------------------------------------------------------------------------------------
    # Layout
    # -----------------------------------------------------------------------------------------------------------------

    @property
    def fit_items(self) -> list[FitItem]:
        """The block's items for planning: the paint row if the tool has one, the checkboxes, and the preview if the
        tool has one."""
        return [_FIT_ITEMS[key] for key in self._fit_keys]

    @property
    def arrangement(self) -> StrokeArrangement:
        """The block's current arrangement."""
        assert self._arrangement is not None
        return self._arrangement

    def apply_fit(self, orientation: Orientation, placement: Placement) -> None:
        """Arranges the block for the forms its `fit_items` take in a placement."""
        forms = dict(zip(self._fit_keys, placement))
        preview_form = forms.get(PREVIEW_ITEM)
        if preview_form is not None:
            forms[PREVIEW_ITEM] = _PREVIEW_FORMS[orientation][preview_form]
        # Stacking the paint row makes it taller, which only saves room in a side panel:
        side = orientation == Orientation.SIDE
        self._arrange(StrokeArrangement(orientation, paint_stacked=side and forms.get(PAINT_ITEM) == STACKED,
                                        checks_stacked=self._checks_stacked(orientation, forms[CHECKS_ITEM]),
                                        preview=forms.get(PREVIEW_ITEM),
                                        headers=side or forms.get(HEADERS_ITEM) is not None))

    def _checks_stacked(self, orientation: Orientation, form: int) -> bool:
        """Returns whether the checkboxes take one row each in a placement's form for them.

        A side panel tries inline first and stacks when that doesn't fit across. A strip tries stacked first, which fits
        when the strip is tall enough. A tool with a color pair stacks there only if the inline row is wider than the
        options column's cap, since the planner can't see that clipping on the strip's scroll axis.
        """
        if orientation == Orientation.SIDE:
            return form == STACKED
        if self._paint_widget is not None and self._inline_checks_width() <= FIELD_COLUMN_MAX_WIDTH:
            return False
        return form == INLINE

    def _inline_checks_width(self) -> int:
        """Returns the width the checkboxes need in one row."""
        direction = self._checks_layout.direction()
        self._checks_layout.setDirection(QBoxLayout.Direction.LeftToRight)
        width = self._checks_layout.minimumSize().width()
        self._checks_layout.setDirection(direction)
        return width

    def add_tool_section(self, section: PanelSection, stretch: bool = False) -> None:
        """Adds a tool's own section after the block's: below them in a side panel, and in the next column in a
        strip. A `stretch` section takes the height the others leave. The owner caps the section's width."""
        self._tool_sections.append((section, stretch))
        arrangement = self.arrangement
        self._arrangement = None
        self._arrange(arrangement)

    def set_tool_section_stretch(self, section: PanelSection, stretch: bool) -> None:
        """Changes whether a tool section takes the height the others leave."""
        sections = [(added, stretch if added is section else added_stretch)
                    for added, added_stretch in self._tool_sections]
        if sections != self._tool_sections:
            self._tool_sections = sections
            arrangement = self.arrangement
            self._arrangement = None
            self._arrange(arrangement)

    def update_tool_columns(self) -> None:
        """Shares a strip's spare width only between tool section columns that show, after a section is shown or
        hidden."""
        for section, column in self._tool_columns.items():
            self._grid.setColumnStretch(column, 0 if section.isHidden() else CONTROL_COLUMN_STRETCH)

    def _stroke_summary(self) -> str:
        return ', '.join(f'{field.label()} {field.value_text()}' for field in self._fields.values())

    def _arrange(self, arrangement: StrokeArrangement) -> None:
        # Adding the preview to a layout reparents it, which hides it until a queued call shows it again. Its
        # visibility is set after it is placed, so a trial measurement counts it:
        self._place(arrangement)
        if self._preview is not None:
            self._preview.setVisible(arrangement.preview is not None)

    def _place(self, arrangement: StrokeArrangement) -> None:
        if arrangement == self._arrangement:
            return
        self._arrangement = arrangement
        tool_sections = [section for section, _ in self._tool_sections]
        for widget in (self._stroke_section, self._options_section, self._preview, *tool_sections):
            if widget is not None:
                self._grid.removeWidget(widget)
        if self._preview is not None:
            self._stroke_layout.removeWidget(self._preview)
        for index in range(self._grid.columnCount()):
            self._grid.setColumnStretch(index, 0)
        for index in range(self._grid.rowCount()):
            self._grid.setRowStretch(index, 0)
        for section in (self._stroke_section, self._options_section, *tool_sections):
            section.set_header_visible(arrangement.headers)
        self._checks_layout.setDirection(QBoxLayout.Direction.TopToBottom if arrangement.checks_stacked
                                         else QBoxLayout.Direction.LeftToRight)
        if self._paint_layout is not None:
            self._paint_layout.setDirection(QBoxLayout.Direction.TopToBottom if arrangement.paint_stacked
                                            else QBoxLayout.Direction.LeftToRight)
            # The Pattern combo fills the row's width, but not extra height when stacked:
            for dropdown in self._paint_widget.findChildren(FillStyleComboBox):  # type: ignore[union-attr]
                self._paint_layout.setStretchFactor(dropdown, 0 if arrangement.paint_stacked else 1)
        beside = arrangement.preview == BESIDE
        self._fields_widget.setMinimumWidth(BESIDE_FIELD_MIN_WIDTH if beside else 0)
        for widget in (self._stroke_section, self._options_section):
            widget.setMaximumWidth(FIELD_COLUMN_MAX_WIDTH)
        if self._preview is not None and arrangement.preview == BELOW:
            self._stroke_layout.addWidget(self._preview)
        # Top-aligned, so Size stays put when a taller preview sits beside the sections. No horizontal alignment,
        # which would size each widget to its hint instead of its column:
        top = Qt.AlignmentFlag.AlignTop
        self._grid.addWidget(self._stroke_section, 0, 0, top)
        if arrangement.orientation == Orientation.STRIP:
            self._grid.addWidget(self._options_section, 0, 1, top)
            self._grid.setColumnStretch(0, CONTROL_COLUMN_STRETCH)
            self._grid.setColumnStretch(1, CONTROL_COLUMN_STRETCH)
            column = 2
            if len(self._tool_sections) > 0:
                # With columns after it, an options column wider than its content would leave a gap before them. The
                # fresh measurement counts the checkboxes' direction, which was set a moment ago:
                fresh_minimum_size(self._options_section)
                self._options_section.setMaximumWidth(min(FIELD_COLUMN_MAX_WIDTH,
                                                          self._options_section.sizeHint().width()))
            self._tool_columns = {}
            for section, stretch in self._tool_sections:
                # A stretching section spans the spare row too, so it fills the strip's height:
                if stretch:
                    self._grid.addWidget(section, 0, column, 2, 1)
                else:
                    self._grid.addWidget(section, 0, column, top)
                self._tool_columns[section] = column
                column += 1
            self.update_tool_columns()
            # The preview is decorative, so it follows the tool's own columns:
            if self._preview is not None and beside:
                self._grid.addWidget(self._preview, 0, column)
                self._grid.setColumnStretch(column, CONTROL_COLUMN_STRETCH)
                column += 1
            self._grid.setColumnStretch(column, SPARE_COLUMN_STRETCH)
            # Height beyond what the sections need goes below them:
            self._grid.setRowStretch(1, 1)
            return
        self._tool_columns = {}
        self._grid.addWidget(self._options_section, 1, 0, top)
        self._grid.setColumnStretch(0, CONTROL_COLUMN_STRETCH)
        spare_column = 1
        if self._preview is not None and beside:
            # The preview spans both sections' rows, and the sections stay in column 1:
            self._grid.addWidget(self._preview, 0, 1, 2, 1)
            self._grid.setColumnStretch(1, CONTROL_COLUMN_STRETCH)
            spare_column = 2
        self._grid.setColumnStretch(spare_column, SPARE_COLUMN_STRETCH)
        # Tool sections span every column, so a section capped wider than the block's columns can use the spare one:
        row = 2
        stretched = False
        for section, stretch in self._tool_sections:
            self._grid.addWidget(section, row, 0, 1, spare_column + 1,
                                 Qt.AlignmentFlag(0) if stretch else top)
            if stretch:
                self._grid.setRowStretch(row, 1)
                stretched = True
            row += 1
        # Height beyond what the sections need goes below them, unless a tool section takes it:
        if not stretched:
            self._grid.setRowStretch(row, 1)


class StrokeToolPanel(QWidget):
    """A tool control panel with a `StrokeBlock` first, and the tool's own sections after it.

    - It is a `src.ui.layout.panel_fit.FitContent`: the Tools panel measures it at `fit_base_size`, then
      `set_fit_space` plans the block in the space left over.
    - Without a host that calls `set_fit_space`, it plans for its own size when resized. That size must not follow
      its content, or each plan would resize it and plan again. A resize during a plan doesn't start another.
      A new parent clears the host's space, so a host calls `set_fit_space` again after adding the panel.
    - Sections added with `add_tool_section` join the block's arrangement, and those given a `FitItem` are planned
      with the block's items. Controls a plan leaves out go in `overflow_content`, which the Tools panel shows in its
      More popover.
    - `set_orientation` arranges it for an orientation, vertical for a side panel. Subclasses extend it for their own
      sections.
    """

    def __init__(self, block: StrokeBlock, sections: Optional[list[QWidget]] = None) -> None:
        super().__init__()
        self._block = block
        self._orientation = Qt.Orientation.Vertical
        self._space: Optional[QSize] = None
        self._planning = False
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.addWidget(block)
        for section in sections or []:
            self._layout.addWidget(section)
        self._tool_items: list[tuple[FitItem, Callable[[Orientation, Optional[int]], None]]] = []
        self._overflow = QWidget()
        self._overflow_layout = QVBoxLayout(self._overflow)
        self._overflow_layout.setContentsMargins(0, 0, 0, 0)
        self._planner = self._build_planner()

    @property
    def stroke_block(self) -> StrokeBlock:
        """The panel's stroke controls."""
        return self._block

    @property
    def fit_space(self) -> Optional[QSize]:
        """The size being planned for, or the latest plan's, or None before the first plan."""
        return self._planner.available

    def add_tool_section(self, section: PanelSection, item: Optional[FitItem] = None,
                         apply: Optional[Callable[[Orientation, Optional[int]], None]] = None,
                         stretch: bool = False) -> None:
        """Adds a section after the block's, with `StrokeBlock.add_tool_section`.

        With an `item`, planning calls `apply` with the orientation and the form the item takes, or None for an
        optional item left out. `apply` hides a left-out section, or moves its controls to `overflow_content`. A bound
        method is held weakly, since the panel usually owns it.
        """
        self._block.add_tool_section(section, stretch)
        if item is not None:
            assert apply is not None
            self._tool_items.append((item, held_weakly(apply)))
            self._planner = self._build_planner()

    def overflow_content(self) -> QWidget:
        """Returns the widget holding controls the latest plan left out, for the host's More popover. Subclasses add
        and remove its controls in their `add_tool_section` callbacks."""
        return self._overflow

    @property
    def overflow_layout(self) -> QVBoxLayout:
        """The layout of `overflow_content`."""
        return self._overflow_layout

    def fit_base_size(self, orientation: Orientation) -> QSize:
        """Returns the minimum size with required items in their smallest forms and no optional items, and keeps that
        arrangement until the next `set_fit_space`."""
        self._follow_orientation(orientation)
        return self._planner.base_size(orientation)

    def set_fit_space(self, orientation: Orientation, size: QSize) -> None:
        """Plans the block and the tool's sections for the space the Tools panel gives the panel."""
        self._follow_orientation(orientation)
        self._space = QSize(size)
        self._planner.update(orientation, size)

    def _build_planner(self) -> FitPlanner:
        items = [*self._block.fit_items, *(item for item, _ in self._tool_items)]
        return FitPlanner(items, self._apply_fit, self._measure_fit)

    def _measure_fit(self) -> QSize:
        return fresh_minimum_size(self)

    def _apply_fit(self, orientation: Orientation, placement: Placement) -> None:
        block_count = len(self._block.fit_items)
        self._block.apply_fit(orientation, placement[:block_count])
        for (_, apply), form in zip(self._tool_items, placement[block_count:]):
            apply(orientation, form)
        self._block.update_tool_columns()

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Vertical is a side panel, horizontal a strip. Subclasses extend this to arrange their own sections."""
        self._orientation = orientation

    def event(self, event: QEvent) -> bool:
        """Forgets the host's space when the panel moves to a new parent."""
        if event.type() == QEvent.Type.ParentChange:
            self._space = None
        return super().event(event)

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:  # pylint: disable=invalid-name
        """Plans for the new size, unless a host plans the panel."""
        super().resizeEvent(event)
        # Trial placements show and hide section headers, which can resize the panel and re-enter this handler:
        if self._space is None and not self._planning:
            self._planning = True
            try:
                self._planner.update(self._fit_orientation(), self.size())
            finally:
                self._planning = False

    def show_pressure_checkboxes(self) -> None:
        """Reveals the pen pressure links after a tablet is seen, and replans once for the reveal.

        Pen use calls this on every tablet event. The reveal changes no measured size, so only the first call
        replans: a forced replan on every event rearranges the panel in a stream, which flickers it.
        """
        first_reveal = not Cache().get(Cache.EXPECT_TABLET_INPUT)
        self._block.show_pressure_links()
        Cache().set(Cache.EXPECT_TABLET_INPUT, True)
        if first_reveal:
            self._planner.update(self._fit_orientation(), self._space if self._space is not None else self.size(),
                                 force=True)

    def _fit_orientation(self) -> Orientation:
        return Orientation.SIDE if self._orientation == Qt.Orientation.Vertical else Orientation.STRIP

    def _follow_orientation(self, orientation: Orientation) -> None:
        qt_orientation = Qt.Orientation.Vertical if orientation == Orientation.SIDE else Qt.Orientation.Horizontal
        if qt_orientation != self._orientation:
            self.set_orientation(qt_orientation)
