"""The stroke controls shared by the brush-like tool panels, and the panel that hosts them.

`StrokeBlock` is a view over `Cache` values, in a fixed order so Size never moves between tools:

1. Size, Opacity and Hardness as `SliderField`s, with pen pressure links inside the fields. The links appear once a
   tablet has been seen and add no row. Key hints are in the field tooltips.
2. The color pair and Pattern, if the tool paints a color.
3. Antialiasing and "Only inside selection".

Tool-specific sections go after the block, in `StrokeToolPanel`.

Layout follows the orientation and width the block is given:
- Side: one column. Below `STACK_CHECKBOXES_WIDTH` the checkboxes stack. From `PREVIEW_MIN_WIDTH` the fields stop at
  `FIELD_COLUMN_MAX_WIDTH` and a `StrokePreview` fills the space beside them.
- Strip: the fields in column 1, the color pair and checkboxes in column 2.
"""
import math
from typing import Optional

from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPalette, QRadialGradient, QResizeEvent
from PySide6.QtWidgets import (QApplication, QBoxLayout, QCheckBox, QGridLayout, QLabel, QSizePolicy,
                               QVBoxLayout, QWidget)

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.ui.ink_style import set_signal
from src.ui.input_fields.fill_style_combo_box import FillStyleComboBox
from src.ui.input_fields.number_field import NumberField
from src.ui.input_fields.slider_field import SliderField
from src.ui.layout.label_column_layout import normalize_row_label
from src.ui.widget.color_pair_widget import ColorPairWidget

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.stroke_block'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


ONLY_INSIDE_SELECTION_LABEL = _tr('Only inside selection')
PIXEL_SUFFIX = _tr(' px')
PERCENT_SUFFIX = _tr('%')
KEYS_TOOLTIP = _tr('{description}\nKeys: {decrease} / {increase}')

STACK_CHECKBOXES_WIDTH = 260
PREVIEW_MIN_WIDTH = 420
FIELD_COLUMN_MAX_WIDTH = 290
PREVIEW_MIN_HEIGHT = 72
COLUMN_SPACING = 10
MIN_PATTERN_CHARACTERS = 6
PREVIEW_STAMP_SPACING = 0.2


class StrokePreview(QWidget):
    """Draws a sample stroke with the current size, hardness and opacity, for the Qt brush tools."""

    def __init__(self, size_key: str, opacity_key: Optional[str], hardness_key: Optional[str],
                 color_key: Optional[str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._size_key = size_key
        self._opacity_key = opacity_key
        self._hardness_key = hardness_key
        self._color_key = color_key
        self.setMinimumHeight(PREVIEW_MIN_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        cache = Cache()
        for key in (size_key, opacity_key, hardness_key, color_key):
            if key is not None:
                cache.connect(self, key, lambda *_: self.update())

    def sizeHint(self) -> QSize:
        """Returns a short, wide area."""
        return QSize(120, PREVIEW_MIN_HEIGHT)

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


class StrokeBlock(QWidget):
    """Size, Opacity and Hardness fields, the color pair and Pattern, and the shared checkboxes."""

    def __init__(self, size_key: str, opacity_key: Optional[str] = None, hardness_key: Optional[str] = None,
                 pressure_size_key: Optional[str] = None, pressure_opacity_key: Optional[str] = None,
                 pressure_hardness_key: Optional[str] = None, color_key: Optional[str] = None,
                 pattern_key: Optional[str] = None, antialias_key: Optional[str] = None,
                 show_preview: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        cache = Cache()
        self._fields: dict[str, NumberField] = {}
        self._pressure_fields: list[NumberField] = []
        self._orientation = Qt.Orientation.Vertical
        self._arrangement: Optional[tuple[Qt.Orientation, bool, bool]] = None

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

        self._paint_widget: Optional[QWidget] = None
        self._paint_layout = None
        if color_key is not None or pattern_key is not None:
            self._paint_widget = QWidget(self)
            paint_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self._paint_widget)
            self._paint_layout: Optional[QBoxLayout] = paint_layout
            paint_layout.setContentsMargins(0, 0, 0, 0)
            if color_key == Cache.LAST_BRUSH_COLOR:
                paint_layout.addWidget(ColorPairWidget(self._paint_widget))
            if pattern_key is not None:
                pattern_label = QLabel(normalize_row_label(cache.get_label(pattern_key)))
                pattern_dropdown = FillStyleComboBox(pattern_key)
                pattern_label.setBuddy(pattern_dropdown)
                pattern_dropdown.setSizeAdjustPolicy(
                    pattern_dropdown.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
                pattern_dropdown.setMinimumContentsLength(MIN_PATTERN_CHARACTERS)
                paint_layout.addWidget(pattern_label)
                paint_layout.addWidget(pattern_dropdown, stretch=1)
                if color_key is not None:
                    def _pattern_color_update(color_str: str, *_) -> None:
                        if QColor(color_str).isValid():
                            pattern_dropdown.set_icon_colors(QColor(color_str))

                    cache.connect(self, color_key, _pattern_color_update)
                    pattern_dropdown.set_icon_colors(cache.get_color(color_key, Qt.GlobalColor.black))
            paint_layout.addStretch(1)

        self._checks_widget = QWidget(self)
        self._checks_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self._checks_widget)
        self._checks_layout.setContentsMargins(0, 0, 0, 0)
        self._checks_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        if antialias_key is not None:
            antialias_checkbox = cache.get_control_widget(antialias_key)
            if isinstance(antialias_checkbox, QCheckBox):
                antialias_checkbox.setText(normalize_row_label(cache.get_label(antialias_key)))
            self._checks_layout.addWidget(antialias_checkbox)
        selection_only_checkbox = cache.get_control_widget(Cache.PAINT_SELECTION_ONLY)
        set_signal(selection_only_checkbox)
        if isinstance(selection_only_checkbox, QCheckBox):
            selection_only_checkbox.setText(ONLY_INSIDE_SELECTION_LABEL)
        self._checks_layout.addWidget(selection_only_checkbox)

        self._preview: Optional[StrokePreview] = None
        if show_preview:
            self._preview = StrokePreview(size_key, opacity_key, hardness_key, color_key, self)

        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(COLUMN_SPACING)
        self._grid.setVerticalSpacing(6)
        self._arrange(force=True)

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
        label = normalize_row_label(cache.get_label(key))
        if minimum is None or maximum is None or step is None:
            raise ValueError(f'Cache key {key} needs a numeric range')
        field = SliderField(label, cache.get(key), minimum, maximum, step=step, suffix=suffix,
                            display_scale=display_scale, parent=self)
        description = cache.get_tooltip(key)
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

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Vertical is a side panel, horizontal a strip."""
        if orientation != self._orientation:
            self._orientation = orientation
            self._arrange()

    def resizeEvent(self, event: QResizeEvent) -> None:  # pylint: disable=invalid-name
        """Re-arranges when the width crosses a threshold."""
        super().resizeEvent(event)
        self._arrange()

    def arrange_for_width(self, width: int) -> None:
        """Arranges the block as if it were `width` pixels wide."""
        self._arrange(width=width)

    def _arrange(self, force: bool = False, width: Optional[int] = None) -> None:
        if width is None:
            width = self.width()
        strip = self._orientation == Qt.Orientation.Horizontal
        stacked = (not strip) and 0 < width < STACK_CHECKBOXES_WIDTH
        preview = (not strip) and self._preview is not None and width >= PREVIEW_MIN_WIDTH
        arrangement = (self._orientation, stacked, preview)
        if arrangement == self._arrangement and not force:
            return
        self._arrangement = arrangement
        for widget in (self._fields_widget, self._paint_widget, self._checks_widget, self._preview):
            if widget is not None:
                self._grid.removeWidget(widget)
        for index in range(3):
            self._grid.setColumnStretch(index, 0)
        self._checks_layout.setDirection(QBoxLayout.Direction.TopToBottom if stacked
                                         else QBoxLayout.Direction.LeftToRight)
        if self._preview is not None:
            self._preview.setVisible(preview)
        if self._paint_layout is not None:
            self._paint_layout.setDirection(QBoxLayout.Direction.TopToBottom if stacked
                                            else QBoxLayout.Direction.LeftToRight)
        self._fields_widget.setMaximumWidth(FIELD_COLUMN_MAX_WIDTH if preview else 16777215)
        if strip:
            self._grid.addWidget(self._fields_widget, 0, 0, 3, 1)
            row = 0
            for widget in (self._paint_widget, self._checks_widget):
                if widget is not None:
                    self._grid.addWidget(widget, row, 1)
                    row += 1
            self._grid.setColumnStretch(0, 1)
            self._grid.setColumnStretch(1, 1)
            return
        self._grid.addWidget(self._fields_widget, 0, 0)
        if preview:
            assert self._preview is not None
            self._grid.addWidget(self._preview, 0, 1)
            self._grid.setColumnStretch(1, 1)
        else:
            self._grid.setColumnStretch(0, 1)
        row = 1
        for widget in (self._paint_widget, self._checks_widget):
            if widget is not None:
                self._grid.addWidget(widget, row, 0, 1, 2)
                row += 1


class StrokeToolPanel(QWidget):
    """A tool control panel with a `StrokeBlock` first, and the tool's own sections after it."""

    def __init__(self, block: StrokeBlock, sections: Optional[list[QWidget]] = None) -> None:
        super().__init__()
        self._block = block
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.addWidget(block)
        for section in sections or []:
            self._layout.addWidget(section)

    @property
    def stroke_block(self) -> StrokeBlock:
        """The panel's stroke controls."""
        return self._block

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Passes the dock's orientation to the block."""
        self._block.set_orientation(orientation)

    def show_pressure_checkboxes(self) -> None:
        """After receiving a tablet event, call this to reveal the pen pressure links."""
        self._block.show_pressure_links()
        Cache().set(Cache.EXPECT_TABLET_INPUT, True)
