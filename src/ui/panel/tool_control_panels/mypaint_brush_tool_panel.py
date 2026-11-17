"""Control panel widget for the MyPaint Brush tool: Size and the color pair, the brush picker, and brush dynamics.

The stroke block holds Size only. The brush file defines opacity and hardness, and the Brush section's summary says so.

The Brush and Brush dynamics sections are planned with the block (`StrokeToolPanel.add_tool_section`):
- Brush is required. Its full form is the grid, with the active brush and the category combo box in the section header
  while it shows, and at the top of the picker otherwise. Its compact form is the brush chip with a row of favorites,
  under the chip in a side panel and beside it in a strip. The grid takes the height the other sections leave, and in
  a strip, the width too.
- Brush dynamics is optional. A side panel shows it open once the grid keeps `SIDE_ROWS_WITH_DYNAMICS` rows of
  minimum-size tiles, or else collapsed to its summary. A strip shows it open, in the Stroke and Color column while it
  fits there and in its own column otherwise. Where it doesn't fit, its editor moves to the Tools panel's More popover.
- The category list is optional, after Brush dynamics. In a strip it replaces the combo box with a list beside the full
  grid, while the grid keeps `STRIP_LIST_MIN_COLUMNS` minimum-size tiles across. A side panel never shows it.
"""
from typing import Optional

from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from src.config.cache import Cache
from src.image.mypaint.mypaint_brush import MyPaintBrush
from src.ui.layout.panel_fit import REQUIRED, strip_section_min_width, FitItem, Orientation
from src.ui.panel.mypaint_brush_dynamics import BrushDynamicsWidget
from src.ui.panel.mypaint_brush_grid import MAX_CELL_SIZE, MIN_COLUMNS, MIN_ROWS, brush_name
from src.ui.panel.mypaint_brush_panel import MypaintBrushPanel
from src.ui.panel.tool_control_panels.stroke_block import FIELD_COLUMN_MAX_WIDTH, StrokeBlock, StrokeToolPanel
from src.ui.widget.panel_section import PanelSection
from src.util.shared_constants import MAX_WIDGET_SIZE

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.mypaint_brush_tool_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


SIZE_LABEL = _tr('Size')
BRUSH_SECTION_TITLE = _tr('Brush')
DYNAMICS_SECTION_TITLE = _tr('Brush dynamics')
FILE_DEFINED_HINT = _tr('Opacity and hardness come from the brush file.')
BRUSH_SUMMARY = _tr('{brush}. {hint}')

# The widest Brush dynamics grows in a side panel, as wide as this many of the largest brush tiles:
DYNAMICS_WIDEST_TILE_COLUMNS = 5
DYNAMICS_MAX_WIDTH = DYNAMICS_WIDEST_TILE_COLUMNS * MAX_CELL_SIZE + 24
# Minimum-size tile columns the grid keeps beside the category list in a strip:
STRIP_LIST_MIN_COLUMNS = 6
# Minimum-size tile rows the grid keeps in a side panel before Brush dynamics opens:
SIDE_ROWS_WITH_DYNAMICS = 3

# The planner items' forms:
BRUSH_FULL = 0
BRUSH_COMPACT = 1
DYNAMICS_OPEN = 0
DYNAMICS_COLLAPSED = 1
DYNAMICS_PRIORITY = 2
CATEGORY_LIST_PRIORITY = 3


class MyPaintBrushToolPanel(StrokeToolPanel):
    """Control panel widget for the MyPaint Brush tool."""

    def __init__(self, brush: MyPaintBrush) -> None:
        super().__init__(StrokeBlock(size_key=Cache.PAINT_TOOL_BRUSH_SIZE, size_label=SIZE_LABEL,
                                     color_key=Cache.LAST_BRUSH_COLOR))
        self._brush_picker = MypaintBrushPanel()
        self._brush_section = PanelSection(BRUSH_SECTION_TITLE, self._brush_picker)
        self._brush_section.setToolTip(FILE_DEFINED_HINT)

        self._dynamics = BrushDynamicsWidget(brush)
        dynamics_body = QWidget()
        self._dynamics_body_layout = QVBoxLayout(dynamics_body)
        self._dynamics_body_layout.setContentsMargins(0, 0, 0, 0)
        self._dynamics_body_layout.addWidget(self._dynamics)
        self._dynamics_section = PanelSection(DYNAMICS_SECTION_TITLE, dynamics_body)
        self._overflow_title = QLabel(DYNAMICS_SECTION_TITLE)
        self.overflow_layout.addWidget(self._overflow_title)
        self._overflow_title.hide()

        self.add_tool_section(self._brush_section, FitItem(REQUIRED, 2), self._apply_brush_form, stretch=True)
        self.add_tool_section(self._dynamics_section, FitItem(DYNAMICS_PRIORITY, 2), self._apply_dynamics_form)
        self.add_fit_item(FitItem(CATEGORY_LIST_PRIORITY), self._apply_category_list_form)

        self._dynamics.setting_combo.currentIndexChanged.connect(self._update_summaries)
        self._dynamics.value_field.valueChanged.connect(self._update_summaries)
        Cache().connect(self, Cache.MYPAINT_BRUSH, self._update_summaries)
        self._update_summaries()

    def _update_summaries(self, *_args) -> None:
        path = self._brush_picker.active_brush_path
        self._brush_section.set_summary(FILE_DEFINED_HINT if path is None
                                        else BRUSH_SUMMARY.format(brush=brush_name(path), hint=FILE_DEFINED_HINT))
        self._dynamics_section.set_summary(self._dynamics.summary())

    @property
    def brush_panel(self) -> MypaintBrushPanel:
        """The brush picker."""
        return self._brush_picker

    @property
    def brush_section(self) -> PanelSection:
        """The section holding the brush picker."""
        return self._brush_section

    @property
    def dynamics(self) -> BrushDynamicsWidget:
        """The brush dynamics editor."""
        return self._dynamics

    @property
    def dynamics_section(self) -> PanelSection:
        """The section holding the brush dynamics editor while it fits in the panel."""
        return self._dynamics_section

    def refresh_dynamics(self) -> None:
        """Re-reads brush dynamics from the brush, after the brush loaded a file."""
        self._dynamics.refresh()
        self._update_summaries()

    def _apply_brush_form(self, orientation: Orientation, form: Optional[int]) -> None:
        compact = form == BRUSH_COMPACT
        strip = orientation == Orientation.STRIP
        picker = self._brush_picker
        picker.set_compact(compact, beside=strip)
        # The block placed the sections first, so the header's visibility is current:
        picker.set_header_host(self._brush_section if self.stroke_block.arrangement.headers else None)
        self.stroke_block.set_tool_section_stretch(self._brush_section, not compact)
        section = self._brush_section
        section.setMinimumWidth(0)
        if strip and compact:
            # Wide enough for every favorite beside the chip, and no wider:
            section.setMaximumWidth(picker.sizeHint().width())
            return
        section.setMaximumWidth(MAX_WIDGET_SIZE)

    def _apply_category_list_form(self, orientation: Orientation, form: Optional[int]) -> None:
        # Brush's form was applied first, so the picker's compact state is current:
        picker = self._brush_picker
        shown = form is not None and orientation == Orientation.STRIP and not picker.compact
        picker.set_category_list(shown)
        grid = picker.grid
        grid.set_minimum_tiles(STRIP_LIST_MIN_COLUMNS if shown else MIN_COLUMNS, grid.minimum_rows)

    def _apply_dynamics_form(self, orientation: Orientation, form: Optional[int]) -> None:
        # A strip has no room for a column holding only a collapsed header:
        shown = form == DYNAMICS_OPEN or (form == DYNAMICS_COLLAPSED and orientation == Orientation.SIDE)
        side = orientation == Orientation.SIDE
        grid = self._brush_picker.grid
        grid.set_minimum_tiles(grid.minimum_columns,
                               SIDE_ROWS_WITH_DYNAMICS if side and form == DYNAMICS_OPEN else MIN_ROWS)
        self._dynamics_section.setVisible(shown)
        self._dynamics_section.set_forced_collapsed(form == DYNAMICS_COLLAPSED)
        # Its description reads better on fewer, longer lines, so it grows past the field cap in a side panel. In a
        # strip it shares the Stroke and Color column:
        self._dynamics_section.setMinimumWidth(0 if side else strip_section_min_width())
        self._dynamics_section.setMaximumWidth(DYNAMICS_MAX_WIDTH if side else FIELD_COLUMN_MAX_WIDTH)
        # A side panel's sections span its width, so the description can be measured at the width it will get before
        # the panel is resized:
        space = self.fit_space
        if side and space is not None:
            margins = self._layout.contentsMargins()
            self._dynamics.set_planned_width(min(space.width() - margins.left() - margins.right(), DYNAMICS_MAX_WIDTH))
        else:
            self._dynamics.set_planned_width(None)
        if shown:
            self._overflow_title.hide()
            self._dynamics_body_layout.addWidget(self._dynamics)
        else:
            self.overflow_layout.addWidget(self._overflow_title)
            self.overflow_layout.addWidget(self._dynamics)
            self._overflow_title.show()
        self._dynamics.show()
