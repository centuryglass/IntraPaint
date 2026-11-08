"""Control panel for the fill/paint bucket tool: a Paint section, then a Region section.

The panel is a `FitToolPanel` with one arrangement per orientation. A side panel stacks the sections. A strip packs them
into columns (`src.ui.layout.column_packing`), so a short strip puts them side by side and a tall one stacks them.
"""
from typing import Optional

from PySide6.QtWidgets import QApplication, QBoxLayout, QCheckBox, QWidget

from src.config.cache import Cache
from src.ui.input_fields.number_field import MAX_WIDTH as NUMBER_FIELD_MAX_WIDTH
from src.ui.input_fields.slider_field import SliderField
from src.ui.layout.label_column_layout import normalize_row_label
from src.ui.layout.panel_fit import FitPlanner, Orientation, Placement
from src.ui.panel.tool_control_panels.fit_tool_panel import FitToolPanel
from src.ui.panel.tool_control_panels.stroke_block import (build_paint_row, build_selection_only_checkbox,
                                                           tool_section)
from src.ui.input_fields.field_factory import create_control_widget

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.fill_tool_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


PAINT_SECTION_TITLE = _tr('Paint')
REGION_SECTION_TITLE = _tr('Region')
THRESHOLD_TOOLTIP = _tr('How closely a color must match the clicked color to be filled. 0 fills only exact matches. '
                        'Shared with the magic wand.')
SAMPLE_MERGED_TOOLTIP = _tr('Fill based on the whole image instead of just the active layer. Shared with the '
                            'magic wand.')


def build_threshold_field(parent: Optional[QWidget] = None) -> SliderField:
    """Returns the Color threshold field that the Fill and Magic wand panels share, bound to
    `Cache.FILL_THRESHOLD`."""
    cache = Cache()
    minimum, maximum, step = cache.get_range(Cache.FILL_THRESHOLD)
    assert minimum is not None and maximum is not None and step is not None
    # Whole numbers only; the stored value stays a float:
    field = SliderField(normalize_row_label(cache.get_label(Cache.FILL_THRESHOLD)),
                        int(cache.get(Cache.FILL_THRESHOLD)), int(minimum), int(maximum), step=int(step),
                        parent=parent)
    field.setToolTip(THRESHOLD_TOOLTIP)

    def _field_changed(value: int | float) -> None:
        if cache.get(Cache.FILL_THRESHOLD) != value:
            cache.set(Cache.FILL_THRESHOLD, float(value))

    field.valueChanged.connect(_field_changed)
    cache.connect(field, Cache.FILL_THRESHOLD, lambda value, *_: field.set_value(int(value)))
    return field


def build_sample_merged_checkbox() -> QCheckBox:
    """Returns the Sample merged checkbox that the Fill and Magic wand panels share."""
    checkbox = create_control_widget(Cache(), Cache.SAMPLE_MERGED)
    assert isinstance(checkbox, QCheckBox)
    checkbox.setToolTip(SAMPLE_MERGED_TOOLTIP)
    return checkbox


class FillToolPanel(FitToolPanel):
    """Control panel for the fill/paint bucket tool. Both sections always show, so `overflow_content` stays empty.

    Without a host that calls `set_fit_space`, the panel plans for its own size when resized.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        paint_row = build_paint_row(Cache.LAST_BRUSH_COLOR, Cache.FILL_TOOL_BRUSH_PATTERN, self)
        assert paint_row is not None
        # Keeps the Pattern dropdown's right edge level with the Color threshold slider's:
        paint_row.setMaximumWidth(NUMBER_FIELD_MAX_WIDTH)
        self._threshold_field = build_threshold_field(self)
        sample_merged_checkbox = build_sample_merged_checkbox()
        self._sections = (tool_section(PAINT_SECTION_TITLE, paint_row, build_selection_only_checkbox()),
                          tool_section(REGION_SECTION_TITLE, self._threshold_field, sample_merged_checkbox))
        for section in self._sections:
            self._layout.addWidget(section)
            self._packer.watch(section)
        self._layout.addStretch(1)
        self._planner = FitPlanner([], self._apply_fit, self._measure_fit)

    def _apply_fit(self, orientation: Orientation, _placement: Placement) -> None:
        self._orientation = orientation
        self._arrange_box_sections(self._layout, self._sections, orientation)

    @property
    def threshold_field(self) -> SliderField:
        """The Color threshold field."""
        return self._threshold_field
