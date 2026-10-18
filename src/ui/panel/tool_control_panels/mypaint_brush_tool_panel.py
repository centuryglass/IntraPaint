"""Control panel widget for the MyPaint Brush tool: Size and the color pair, the brush picker, and brush dynamics.

The stroke block holds Size only. The brush file defines opacity and hardness, and the Brush section says so.

Section forms follow the space the Tools panel gives the panel (`apply_fit_space`):
- Side: the picker is compact below `SIDE_COMPACT_WIDTH`. Brush dynamics starts open above `SIDE_WIDE_WIDTH` and
  collapsed otherwise.
- Strip: the picker is compact below `STRIP_SHORT_HEIGHT`. Brush dynamics is a column above `STRIP_TALL_HEIGHT`, and a
  button that opens it in a popover otherwise.
- The compact picker shows `SIDE_FAVORITE_COUNT` favorites in a side panel and `STRIP_FAVORITE_COUNT` in a strip.
"""
from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from src.config.cache import Cache
from src.image.mypaint.mypaint_brush import MyPaintBrush
from src.ui.layout.panel_fit import Orientation
from src.ui.panel.mypaint_brush_dynamics import BrushDynamicsWidget
from src.ui.panel.mypaint_brush_panel import MypaintBrushPanel, brush_name
from src.ui.panel.tool_control_panels.stroke_block import StrokeBlock, StrokeToolPanel
from src.ui.widget.panel_header import PanelPopover
from src.ui.widget.panel_section import PanelSection

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.mypaint_brush_tool_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


SIZE_LABEL = _tr('Size')
BRUSH_SECTION_TITLE = _tr('Brush')
DYNAMICS_SECTION_TITLE = _tr('Brush dynamics')
DYNAMICS_BUTTON_LABEL = _tr('Brush dynamics...')
FILE_DEFINED_HINT = _tr('Opacity and hardness come from the brush file.')

SIDE_COMPACT_WIDTH = 260
SIDE_WIDE_WIDTH = 420
STRIP_SHORT_HEIGHT = 170
STRIP_TALL_HEIGHT = 320
SIDE_FAVORITE_COUNT = 4
STRIP_FAVORITE_COUNT = 8
DYNAMICS_POPOVER_WIDTH = 300


class MyPaintBrushToolPanel(StrokeToolPanel):
    """Control panel widget for the MyPaint Brush tool."""

    def __init__(self, brush: MyPaintBrush) -> None:
        self._brush_picker = MypaintBrushPanel()
        brush_body = QWidget()
        brush_layout = QVBoxLayout(brush_body)
        brush_layout.setContentsMargins(0, 0, 0, 0)
        brush_layout.addWidget(self._brush_picker, stretch=1)
        self._hint = QLabel(FILE_DEFINED_HINT)
        self._hint.setWordWrap(True)
        self._hint.setForegroundRole(self._hint.palette().ColorRole.PlaceholderText)
        self._hint.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        brush_layout.addWidget(self._hint)
        self._brush_section = PanelSection(BRUSH_SECTION_TITLE, brush_body)

        self._dynamics = BrushDynamicsWidget(brush)
        self._dynamics_section = PanelSection(DYNAMICS_SECTION_TITLE, self._dynamics, expanded=False)
        self._dynamics_button = QPushButton(DYNAMICS_BUTTON_LABEL)
        self._dynamics_button.setFlat(True)
        self._brush = brush
        self._popover_dynamics: Optional[BrushDynamicsWidget] = None
        self._popover: Optional[PanelPopover] = None
        self._wide = False
        super().__init__(StrokeBlock(size_key=Cache.PAINT_TOOL_BRUSH_SIZE, size_label=SIZE_LABEL,
                                     color_key=Cache.LAST_BRUSH_COLOR),
                         [self._brush_section, self._dynamics_section, self._dynamics_button])
        self._layout.setStretchFactor(self._brush_section, 1)
        self._dynamics_button.hide()
        self._dynamics_button.clicked.connect(self._show_dynamics_popover)

        def _update_summaries(*_args) -> None:
            path = self._brush_picker.active_brush_path
            self._brush_section.set_summary(f'{brush_name(path)}. {FILE_DEFINED_HINT}' if path is not None
                                            else FILE_DEFINED_HINT)
            self._dynamics_section.set_summary(self._dynamics.summary())

        self._update_summaries = _update_summaries
        self._dynamics.setting_combo.currentIndexChanged.connect(_update_summaries)
        self._dynamics.value_field.valueChanged.connect(_update_summaries)
        Cache().connect(self, Cache.MYPAINT_BRUSH, _update_summaries)
        _update_summaries()

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
        """The brush dynamics editor in the panel's own section."""
        return self._dynamics

    @property
    def dynamics_section(self) -> PanelSection:
        """The section holding the brush dynamics editor."""
        return self._dynamics_section

    @property
    def dynamics_button(self) -> QPushButton:
        """The button that opens brush dynamics in a popover while a strip has no column for them."""
        return self._dynamics_button

    def refresh_dynamics(self) -> None:
        """Re-reads brush dynamics from the brush, after the brush loaded a file."""
        self._dynamics.refresh()
        if self._popover_dynamics is not None:
            self._popover_dynamics.refresh()
        self._update_summaries()

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Lays the sections out in a column for a side panel and in a row for a strip."""
        super().set_orientation(orientation)
        horizontal = orientation == Qt.Orientation.Horizontal
        self._layout.setDirection(QBoxLayout.Direction.LeftToRight if horizontal
                                  else QBoxLayout.Direction.TopToBottom)
        alignment = Qt.AlignmentFlag.AlignTop
        self._layout.setAlignment(alignment | Qt.AlignmentFlag.AlignLeft if horizontal else alignment)
        self._hint.setVisible(not horizontal)

    def apply_base_form(self, orientation: Orientation) -> None:
        """Uses the compact picker, with brush dynamics collapsed or out of the strip."""
        self._apply_forms(orientation, compact=True, dynamics_open=False)

    def apply_fit_space(self, orientation: Orientation, size: QSize) -> None:
        """Chooses the picker and brush dynamics forms for the space, as the module docstring describes."""
        if orientation == Orientation.SIDE:
            self._apply_forms(orientation, size.width() < SIDE_COMPACT_WIDTH, size.width() > SIDE_WIDE_WIDTH)
        else:
            self._apply_forms(orientation, size.height() < STRIP_SHORT_HEIGHT, size.height() > STRIP_TALL_HEIGHT)

    def _apply_forms(self, orientation: Orientation, compact: bool, dynamics_open: bool) -> None:
        strip = orientation == Orientation.STRIP
        self._brush_picker.set_compact(compact)
        self._brush_picker.set_favorite_count(STRIP_FAVORITE_COUNT if strip else SIDE_FAVORITE_COUNT)
        if strip:
            self._dynamics_section.setVisible(dynamics_open)
            self._dynamics_button.setVisible(not dynamics_open)
            if dynamics_open:
                self._dynamics_section.set_expanded(True)
        else:
            self._dynamics_section.setVisible(True)
            self._dynamics_button.setVisible(False)
            if dynamics_open != self._wide:
                self._dynamics_section.set_expanded(dynamics_open)
        self._wide = dynamics_open

    def _show_dynamics_popover(self) -> None:
        """Opens brush dynamics under the button."""
        if self._popover is None:
            self._popover = PanelPopover(self)
            self._popover_dynamics = BrushDynamicsWidget(self._brush)
            self._popover_dynamics.setFixedWidth(DYNAMICS_POPOVER_WIDTH)
            self._popover.set_content(self._popover_dynamics)
        elif self._popover_dynamics is not None:
            self._popover_dynamics.refresh()
        self._popover.adjustSize()
        corner = self._dynamics_button.mapToGlobal(self._dynamics_button.rect().bottomLeft())
        self._popover.move(corner.x(), corner.y() + 2)
        self._popover.show()
