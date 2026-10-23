"""Control panel widget for the MyPaint Brush tool: Size and the color pair, the brush picker, and brush dynamics.

The stroke block holds Size only. The brush file defines opacity and hardness, and the Brush section's summary says so.

The Brush and Brush dynamics sections are planned with the block (`StrokeToolPanel.add_tool_section`):
- Brush is required. Its full form is the whole picker, and its compact form the brush chip with a row of favorites,
  under the chip in a side panel and beside it in a strip. The full picker takes the height the other sections leave.
- Brush dynamics is optional. A side panel shows it open, or else collapsed to its summary. A strip shows it open in
  its own column. Where it doesn't fit, its editor moves to the Tools panel's More popover.
"""
from typing import Optional

from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from src.config.cache import Cache
from src.image.mypaint.mypaint_brush import MyPaintBrush
from src.ui.layout.panel_fit import REQUIRED, STRIP_SECTION_MIN_WIDTH, FitItem, Orientation
from src.ui.panel.mypaint_brush_dynamics import BrushDynamicsWidget
from src.ui.panel.mypaint_brush_panel import MAX_CELL_SIZE, MypaintBrushPanel, brush_name
from src.ui.panel.tool_control_panels.stroke_block import StrokeBlock, StrokeToolPanel
from src.ui.widget.panel_section import PanelSection

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

# The widest the picker grows, with room for this many of the largest tiles and the grid's scroll bar:
WIDEST_TILE_COLUMNS = 5
BRUSH_MAX_WIDTH = WIDEST_TILE_COLUMNS * MAX_CELL_SIZE + 24
# The full picker's column width in a strip:
STRIP_BRUSH_WIDTH = 420

# The planner items' forms:
BRUSH_FULL = 0
BRUSH_COMPACT = 1
DYNAMICS_OPEN = 0
DYNAMICS_COLLAPSED = 1
DYNAMICS_PRIORITY = 2


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
        # Its description reads better on fewer, longer lines, so the section can grow like the picker:
        self._dynamics_section.setMaximumWidth(BRUSH_MAX_WIDTH)
        self._overflow_title = QLabel(DYNAMICS_SECTION_TITLE)
        self.overflow_layout.addWidget(self._overflow_title)
        self._overflow_title.hide()

        self.add_tool_section(self._brush_section, FitItem(REQUIRED, 2), self._apply_brush_form, stretch=True)
        self.add_tool_section(self._dynamics_section, FitItem(DYNAMICS_PRIORITY, 2), self._apply_dynamics_form)

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
        self._brush_picker.set_compact(compact, beside=strip)
        self.stroke_block.set_tool_section_stretch(self._brush_section, not compact)
        section = self._brush_section
        if strip and not compact:
            section.setFixedWidth(STRIP_BRUSH_WIDTH)
            self._brush_picker.set_layout_width(STRIP_BRUSH_WIDTH)
            return
        section.setMinimumWidth(0)
        if strip:
            # Wide enough for every favorite beside the chip, and no wider:
            section.setMaximumWidth(self._brush_picker.sizeHint().width())
            return
        section.setMaximumWidth(BRUSH_MAX_WIDTH)
        space = self.fit_space
        if space is not None:
            margins = self._layout.contentsMargins()
            self._brush_picker.set_layout_width(min(space.width() - margins.left() - margins.right(),
                                                    BRUSH_MAX_WIDTH))

    def _apply_dynamics_form(self, orientation: Orientation, form: Optional[int]) -> None:
        # A strip has no room for a column holding only a collapsed header:
        shown = form == DYNAMICS_OPEN or (form == DYNAMICS_COLLAPSED and orientation == Orientation.SIDE)
        self._dynamics_section.setVisible(shown)
        self._dynamics_section.set_forced_collapsed(form == DYNAMICS_COLLAPSED)
        self._dynamics_section.setMinimumWidth(STRIP_SECTION_MIN_WIDTH if orientation == Orientation.STRIP else 0)
        if shown:
            self._overflow_title.hide()
            self._dynamics_body_layout.addWidget(self._dynamics)
        else:
            self.overflow_layout.addWidget(self._overflow_title)
            self.overflow_layout.addWidget(self._dynamics)
            self._overflow_title.show()
        self._dynamics.show()
