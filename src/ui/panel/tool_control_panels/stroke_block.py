"""The stroke controls shared by the brush-like tool panels, and the panel that hosts them.

`StrokeBlock` is a view over `Cache` values, in a fixed order so Size never moves between tools:

1. Size, Opacity and Hardness as `SliderField`s, with pen pressure links inside the fields. The links appear once a
   tablet has been seen and add no row. Key hints are in the field tooltips.
2. The color pair and Pattern, if the tool paints a color.
3. Antialiasing and "Only inside selection".

Tool-specific sections go after the block, in `StrokeToolPanel`.

Layout is planned by fit (`src.ui.layout.panel_fit`) in the space the Tools panel gives `StrokeToolPanel`:
- Side: one column. Strip: the fields in column 1, the color pair and checkboxes in column 2.
- The color pair and Pattern, and the checkboxes, are required items. In a side panel each row stacks into a column
  when it doesn't fit across. In a strip the rows stay inline, because stacking would make them taller.
- A tool with a `StrokePreview` shows it beside the fields or below them, whichever fits, or hides it. The preview is
  decorative, so it never moves to the More popover. Beside the fields, they keep at least
  `BESIDE_FIELD_MIN_WIDTH` and stop at `FIELD_COLUMN_MAX_WIDTH`.
"""
import math
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QEvent, QPointF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPalette, QRadialGradient, QResizeEvent
from PySide6.QtWidgets import (QApplication, QBoxLayout, QCheckBox, QGridLayout, QLabel, QLayout, QSizePolicy,
                               QVBoxLayout, QWidget)

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.ui.ink_style import set_signal
from src.ui.input_fields.fill_style_combo_box import FillStyleComboBox
from src.ui.input_fields.number_field import NumberField
from src.ui.input_fields.slider_field import SliderField
from src.ui.layout.panel_fit import REQUIRED, FitItem, FitPlanner, Orientation, Placement, fresh_minimum_size
from src.ui.layout.label_column_layout import normalize_row_label
from src.ui.widget.color_pair_widget import ColorPairWidget
from src.ui.widget.panel_section import PanelSection

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.stroke_block'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


ONLY_INSIDE_SELECTION_LABEL = _tr('Only inside selection')
PIXEL_SUFFIX = _tr(' px')
PERCENT_SUFFIX = _tr('%')
KEYS_TOOLTIP = _tr('{description}\nKeys: {decrease} / {increase}')

BESIDE_FIELD_MIN_WIDTH = 200
FIELD_COLUMN_MAX_WIDTH = 290
PREVIEW_MIN_SIZE = QSize(120, 72)
PREVIEW_MAX_SIZE = QSize(400, 160)
COLUMN_SPACING = 10
MIN_PATTERN_CHARACTERS = 6
PREVIEW_STAMP_SPACING = 0.2
QWIDGETSIZE_MAX = 16777215

# The block's planner items, and their forms:
PAINT_ITEM = 'paint'
CHECKS_ITEM = 'checks'
PREVIEW_ITEM = 'preview'
INLINE = 0
STACKED = 1
BESIDE = 0
BELOW = 1
PREVIEW_PRIORITY = 1
_FIT_ITEMS = {
    PAINT_ITEM: FitItem(REQUIRED, 2),
    CHECKS_ITEM: FitItem(REQUIRED, 2),
    PREVIEW_ITEM: FitItem(PREVIEW_PRIORITY, 2),
}


@dataclass(frozen=True)
class StrokeArrangement:
    """How a `StrokeBlock` is laid out: the orientation, whether each row is stacked into a column, and the preview's
    form, or None while it is hidden."""
    orientation: Orientation
    paint_stacked: bool = False
    checks_stacked: bool = False
    preview: Optional[int] = None


class StrokePreview(QWidget):
    """Draws a sample stroke with the current size, hardness and opacity, for the Qt brush tools."""

    def __init__(self, size_key: str, opacity_key: Optional[str], hardness_key: Optional[str],
                 color_key: Optional[str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._size_key = size_key
        self._opacity_key = opacity_key
        self._hardness_key = hardness_key
        self._color_key = color_key
        self.setMinimumSize(PREVIEW_MIN_SIZE)
        self.setMaximumSize(PREVIEW_MAX_SIZE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        cache = Cache()
        for key in (size_key, opacity_key, hardness_key, color_key):
            if key is not None:
                cache.connect(self, key, lambda *_: self.update())

    def sizeHint(self) -> QSize:
        """Returns a short, wide area."""
        return PREVIEW_MIN_SIZE

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws overlapping soft stamps along a wave, shrunk to fit the height."""
        cache = Cache()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        painter.fillRect(self.rect(), palette.color(QPalette.ColorRole.Base))
        color = QColor(palette.color(QPalette.ColorRole.Text))
        if self._color_key is not None:
            color = cache.get_color(self._color_key, color)
        opacity = cache.get(self._opacity_key) if self._opacity_key is not None else 1.0
        hardness = cache.get(self._hardness_key) if self._hardness_key is not None else 1.0
        diameter = float(cache.get(self._size_key))
        margin = 6.0
        available = max(self.height() - 2 * margin, 1.0)
        diameter = max(1.0, min(diameter, available * 0.5))
        radius = diameter / 2
        left, right = margin + radius, self.width() - margin - radius
        if right <= left:
            return
        amplitude = max((available - diameter) / 2, 0.0)
        spacing = max(1.0, diameter * PREVIEW_STAMP_SPACING)
        stamp_alpha = max(0.0, min(1.0, opacity))
        # Soft brushes build up under overlap, so each stamp's alpha is a fraction of the stroke opacity:
        stamp_color = QColor(color)
        stamp_color.setAlphaF(stamp_alpha * (0.35 if hardness < 1.0 else 1.0))
        painter.setPen(Qt.PenStyle.NoPen)
        x = left
        center_y = self.height() / 2
        span = max(right - left, 1.0)
        while x <= right:
            y = center_y + amplitude * math.sin((x - left) / span * 2 * math.pi)
            gradient = QRadialGradient(QPointF(x, y), radius)
            inner = QColor(stamp_color)
            outer = QColor(stamp_color)
            outer.setAlpha(0)
            gradient.setColorAt(0.0, inner)
            gradient.setColorAt(max(hardness, 0.01) * 0.999, inner)
            gradient.setColorAt(1.0, outer)
            painter.setBrush(gradient)
            painter.drawEllipse(QPointF(x, y), radius, radius)
            x += spacing
        painter.end()


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
        row_layout.addWidget(pattern_dropdown, stretch=1)
        if color_key is not None:
            def _pattern_color_update(color_str: str, *_) -> None:
                if QColor(color_str).isValid():
                    pattern_dropdown.set_icon_colors(QColor(color_str))

            cache.connect(row, color_key, _pattern_color_update)
            pattern_dropdown.set_icon_colors(cache.get_color(color_key, Qt.GlobalColor.black))
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
    """

    def __init__(self, size_key: str, opacity_key: Optional[str] = None, hardness_key: Optional[str] = None,
                 pressure_size_key: Optional[str] = None, pressure_opacity_key: Optional[str] = None,
                 pressure_hardness_key: Optional[str] = None, color_key: Optional[str] = None,
                 pattern_key: Optional[str] = None, antialias_key: Optional[str] = None,
                 show_preview: bool = False, opacity_label: Optional[str] = None,
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

        self._fields_widget = QWidget(self)
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

        self._checks_widget = QWidget(self)
        self._checks_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self._checks_widget)
        self._checks_layout.setContentsMargins(0, 0, 0, 0)
        self._checks_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        if antialias_key is not None:
            antialias_checkbox = cache.get_control_widget(antialias_key)
            if isinstance(antialias_checkbox, QCheckBox):
                antialias_checkbox.setText(normalize_row_label(cache.get_label(antialias_key)))
            self._checks_layout.addWidget(antialias_checkbox)
        self._checks_layout.addWidget(build_selection_only_checkbox())

        self._preview: Optional[StrokePreview] = None
        if show_preview:
            self._preview = StrokePreview(size_key, opacity_key, hardness_key, color_key, self)

        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(COLUMN_SPACING)
        self._grid.setVerticalSpacing(6)
        self._fit_keys = [key for key, present in ((PAINT_ITEM, self._paint_widget is not None), (CHECKS_ITEM, True),
                                                   (PREVIEW_ITEM, self._preview is not None)) if present]
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
        # Stacking a row makes it taller, which only saves room in a side panel:
        side = orientation == Orientation.SIDE
        self._arrange(StrokeArrangement(orientation, paint_stacked=side and forms.get(PAINT_ITEM) == STACKED,
                                        checks_stacked=side and forms.get(CHECKS_ITEM) == STACKED,
                                        preview=forms.get(PREVIEW_ITEM)))

    def _arrange(self, arrangement: StrokeArrangement) -> None:
        if arrangement == self._arrangement:
            return
        self._arrangement = arrangement
        for widget in (self._fields_widget, self._paint_widget, self._checks_widget, self._preview):
            if widget is not None:
                self._grid.removeWidget(widget)
        for index in range(3):
            self._grid.setColumnStretch(index, 0)
        for index in range(5):
            self._grid.setRowStretch(index, 0)
        self._checks_layout.setDirection(QBoxLayout.Direction.TopToBottom if arrangement.checks_stacked
                                         else QBoxLayout.Direction.LeftToRight)
        if self._paint_layout is not None:
            self._paint_layout.setDirection(QBoxLayout.Direction.TopToBottom if arrangement.paint_stacked
                                            else QBoxLayout.Direction.LeftToRight)
        if self._preview is not None:
            self._preview.setVisible(arrangement.preview is not None)
        beside = arrangement.preview == BESIDE
        self._fields_widget.setMinimumWidth(BESIDE_FIELD_MIN_WIDTH if beside else 0)
        self._fields_widget.setMaximumWidth(FIELD_COLUMN_MAX_WIDTH if beside else QWIDGETSIZE_MAX)
        # Top-aligned, so Size stays put when a taller preview sits beside the fields:
        top = Qt.AlignmentFlag.AlignTop
        if arrangement.orientation == Orientation.STRIP:
            self._grid.addWidget(self._fields_widget, 0, 0, 3, 1, top)
            row = 0
            for widget in (self._paint_widget, self._checks_widget):
                if widget is not None:
                    self._grid.addWidget(widget, row, 1)
                    row += 1
            if self._preview is not None and beside:
                self._grid.addWidget(self._preview, 0, 2, 3, 1)
            elif self._preview is not None and arrangement.preview == BELOW:
                self._grid.addWidget(self._preview, row, 1)
            self._grid.setColumnStretch(0, 1)
            self._grid.setColumnStretch(1, 1)
            return
        self._grid.addWidget(self._fields_widget, 0, 0, top)
        row = 1
        if self._preview is not None and beside:
            self._grid.addWidget(self._preview, 0, 1)
            self._grid.setColumnStretch(1, 1)
        else:
            self._grid.setColumnStretch(0, 1)
            if self._preview is not None and arrangement.preview == BELOW:
                self._grid.addWidget(self._preview, row, 0, 1, 2)
                row += 1
        for widget in (self._paint_widget, self._checks_widget):
            if widget is not None:
                self._grid.addWidget(widget, row, 0, 1, 2)
                row += 1
        # Height beyond what the rows need goes below them:
        self._grid.setRowStretch(row, 1)


class StrokeToolPanel(QWidget):
    """A tool control panel with a `StrokeBlock` first, and the tool's own sections after it.

    - It is a `src.ui.layout.panel_fit.FitContent`: the Tools panel measures it at `fit_base_size`, then
      `set_fit_space` plans the block in the space left over.
    - Without a host that calls `set_fit_space`, it plans for its own size when resized. That size must not follow
      its content, or each plan would resize it and plan again. A new parent clears the host's space, so a host calls
      `set_fit_space` again after adding the panel.
    - `set_orientation` arranges it for an orientation, vertical for a side panel. Subclasses extend it for their own
      sections.
    """

    def __init__(self, block: StrokeBlock, sections: Optional[list[QWidget]] = None) -> None:
        super().__init__()
        self._block = block
        self._orientation = Qt.Orientation.Vertical
        self._space: Optional[QSize] = None
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.addWidget(block)
        for section in sections or []:
            self._layout.addWidget(section)
        self._planner = FitPlanner(block.fit_items, block.apply_fit, lambda: fresh_minimum_size(self))

    @property
    def stroke_block(self) -> StrokeBlock:
        """The panel's stroke controls."""
        return self._block

    def fit_base_size(self, orientation: Orientation) -> QSize:
        """Returns the minimum size with the block's required items in their smallest forms and no preview, and
        keeps that arrangement until the next `set_fit_space`."""
        self._follow_orientation(orientation)
        return self._planner.base_size(orientation)

    def set_fit_space(self, orientation: Orientation, size: QSize) -> None:
        """Plans the block for the space the Tools panel gives the panel."""
        self._follow_orientation(orientation)
        self._space = QSize(size)
        self._planner.update(orientation, size)

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
        if self._space is None:
            self._planner.update(self._fit_orientation(), self.size())

    def show_pressure_checkboxes(self) -> None:
        """After receiving a tablet event, call this to reveal the pen pressure links."""
        self._block.show_pressure_links()
        Cache().set(Cache.EXPECT_TABLET_INPUT, True)
        self._planner.update(self._fit_orientation(), self._space if self._space is not None else self.size(),
                             force=True)

    def _fit_orientation(self) -> Orientation:
        return Orientation.SIDE if self._orientation == Qt.Orientation.Vertical else Orientation.STRIP

    def _follow_orientation(self, orientation: Orientation) -> None:
        qt_orientation = Qt.Orientation.Vertical if orientation == Orientation.SIDE else Qt.Orientation.Horizontal
        if qt_orientation != self._orientation:
            self.set_orientation(qt_orientation)
