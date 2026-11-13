"""The color picker as a panel that edits a config color: the header, then Wheel, Sliders, Recent and Saved sections.

The panel is a `src.ui.panel.tool_control_panels.fit_tool_panel.FitToolPanel`, planned by fit like the tool panels:
- The header (swatch widget, hex field, screen pick button) always shows. A side panel puts it across the top, and a
  strip stacks it in the first column.
- Each section is optional. A plan opens each section that fits, in the order Wheel, Sliders, Recent, Saved, and
  collapses the rest to their summaries. A click on a collapsed section's header opens its body in a popover.
- A side panel stacks the sections. A strip packs them into columns (`src.ui.layout.column_packing`).
- Plans measure the ring at its minimum size. Once a plan is applied, the ring grows to the largest size that still
  fits, up to a strip column's width (`strip_section_max_width`), and the saved colors take the height left after that.
  The sliders are no wider than a strip column either, so their tracks don't stretch across a wide side panel.

The Tools panel hosts the panel as `FitContent`. The Color dock hosts it directly: the dock's area sets the orientation
through `set_orientation`, the panel plans for its own size, and its minimum size is the smallest plan's for that
orientation, whatever it shows.
"""
from functools import partial
from typing import Optional

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QBoxLayout, QHBoxLayout, QLayout, QSizePolicy, QWidget

from src.config.cache import Cache
from src.config.config_from_key import get_config_from_key
from src.controller import color_controller
from src.ui.layout.dock_panel import QWIDGETSIZE_MAX, host_dock_panel
from src.ui.layout.panel_fit import (FitItem, FitPlanner, Orientation, Placement, fresh_minimum_size,
                                     strip_section_max_width)
from src.ui.panel.tool_control_panels.fit_tool_panel import FitToolPanel
from src.ui.widget.color_pair_widget import ColorPairWidget
from src.ui.widget.color_picker.color_picker_parts import ColorPickerParts
from src.ui.widget.color_picker.okhsv_ring_square import MIN_SIZE as RING_MIN_SIZE
from src.ui.widget.panel_section import PanelSection
from src.ui.widget.section_popover import SectionPopover

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.color_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


WHEEL_SECTION_TITLE = _tr('Wheel')
SLIDERS_SECTION_TITLE = _tr('Sliders')
RECENT_SECTION_TITLE = _tr('Recent')
SAVED_SECTION_TITLE = _tr('Saved')
WHEEL_SUMMARY = _tr('H {hue}, S {saturation}%, V {value}%')

# Each section's planner item, in fill order. A section left out of a plan collapses to its summary:
WHEEL_PRIORITY = 1
SLIDERS_PRIORITY = 2
RECENT_PRIORITY = 3
SAVED_PRIORITY = 4


class _PanelLayout(QBoxLayout):
    """The panel's top layout. It reports no height-for-width, which a scroll area asks the layout for, not the panel
    (see `ColorControlPanel.hasHeightForWidth`)."""

    def hasHeightForWidth(self) -> bool:  # pylint: disable=invalid-name
        """The panel plans for the height it gets."""
        return False


class ColorControlPanel(FitToolPanel):
    """The color picker as a panel that edits a config color, planned by fit.

    Committed colors go to `color_controller.commit_color`. A panel editing the foreground color shows the
    foreground/background color pair in its header. No control is optional, so `overflow_content` stays empty.
    """

    def __init__(self, config_key: Optional[str] = 'last_brush_color') -> None:
        super().__init__()
        swatch_widget = ColorPairWidget() if config_key == Cache.LAST_BRUSH_COLOR else None
        self._parts = ColorPickerParts(swatch_widget, section_controls=True, parent=self)
        parts = self._parts
        # The orientation the Color dock's area sets, or None to follow the panel's shape:
        self._dock_orientation: Optional[Orientation] = None
        # The ring's planned side, or None while plans measure it at its minimum:
        self._ring_side: Optional[int] = None
        # Minimum sizes of the smallest plan, by orientation, for a host that isn't a `DockPanel`:
        self._base_sizes: dict[Orientation, QSize] = {}
        self._base_sizes_stale = True
        self._section_popover: Optional[SectionPopover] = None
        self._measuring = False

        self._layout = _PanelLayout(QBoxLayout.Direction.TopToBottom, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        # A window's layout would set its minimum size to the arrangement's, in place of `minimumSizeHint`:
        self._layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self._layout.addWidget(parts.header)
        section_holder = QWidget()
        self._section_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, section_holder)
        self._section_layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(section_holder, stretch=1)

        wheel_body = QWidget()
        wheel_layout = QHBoxLayout(wheel_body)
        wheel_layout.setContentsMargins(0, 0, 0, 0)
        wheel_layout.addWidget(parts.ring_square, alignment=Qt.AlignmentFlag.AlignLeft)
        self._wheel_section = PanelSection(WHEEL_SECTION_TITLE, wheel_body)
        self._sliders_section = PanelSection(SLIDERS_SECTION_TITLE, parts.slider_block)
        parts.slider_block.setMaximumWidth(strip_section_max_width())
        self._recent_section = PanelSection(RECENT_SECTION_TITLE, parts.recent_colors_row)
        self._saved_section = PanelSection(SAVED_SECTION_TITLE, parts.saved_colors_panel)
        self._saved_section.add_header_widget(parts.saved_colors_panel.save_button)
        self._saved_section.add_header_widget(parts.saved_colors_panel.remove_button)
        self._sections = (self._wheel_section, self._sliders_section, self._recent_section, self._saved_section)
        for section in self._sections:
            self._section_layout.addWidget(section)
            self._packer.watch(section)
            section.forced_header_clicked.connect(partial(self._open_section_popover, section))
        self._section_layout.addStretch(1)

        parts.color_selected.connect(self._update_summaries)
        parts.slider_block.mode_changed.connect(self._update_summaries)
        parts.recent_colors_row.summary_changed.connect(self._recent_section.set_summary)
        parts.saved_colors_panel.summary_changed.connect(self._saved_section.set_summary)
        self._recent_section.set_summary(parts.recent_colors_row.summary())
        self._saved_section.set_summary(parts.saved_colors_panel.summary())
        self._update_summaries()

        items = [FitItem(priority) for priority in (WHEEL_PRIORITY, SLIDERS_PRIORITY, RECENT_PRIORITY, SAVED_PRIORITY)]
        self._planner = FitPlanner(items, self._apply_fit, self._measure_fit, prepare=self._prepare_fit,
                                   finish=self._plan_finished)
        self._measure_base_sizes()

        self._config_key = config_key
        if config_key is not None:
            config = get_config_from_key(config_key)
            parts.set_current_color(config.get_color(config_key, Qt.GlobalColor.black))
            config.connect(self, config_key, self._apply_config_color)
            parts.color_selected.connect(self._update_config_color)
            parts.color_committed.connect(color_controller.commit_color)

    @property
    def parts(self) -> ColorPickerParts:
        """The picker's parts, kept on one color."""
        return self._parts

    @property
    def sections(self) -> tuple[PanelSection, ...]:
        """The Wheel, Sliders, Recent and Saved sections, in order."""
        return self._sections

    @property
    def orientation(self) -> Orientation:
        """The orientation of the latest plan."""
        return self._orientation

    def selected_color(self) -> QColor:
        """Gets the current selected color."""
        return self._parts.selected_color()

    def set_current_color(self, color: QColor) -> None:
        """Sets the current selected color."""
        self._parts.set_current_color(color)

    # Planning:

    def set_orientation(self, orientation: Optional[Qt.Orientation]) -> None:
        """Arranges the panel for a dock area: vertical for a side panel, horizontal for a strip, or None to follow the
        panel's shape."""
        self._dock_orientation = None if orientation is None else (
            Orientation.SIDE if orientation == Qt.Orientation.Vertical else Orientation.STRIP)
        self.updateGeometry()
        self._plan_own_size(force=True)

    def fit_base_size(self, orientation: Orientation) -> QSize:
        """Returns the minimum size with every section collapsed and the ring at its smallest, and keeps that
        arrangement until the next `set_fit_space`."""
        self._ring_side = None
        return super().fit_base_size(orientation)

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the smallest plan's minimum size outside a `DockPanel`, so a dock never shrinks the panel below
        what some plan fits, and the hint doesn't depend on what the panel shows. Inside one, the host plans from
        `fit_base_size`, and the hint is the arrangement's own.

        A plan's trial arrangements activate the layouts of shown ancestors, and a window's layout keeps the minimum it
        reads then, so the hint stays the smallest plan's while a plan runs too.
        """
        if not self._measuring and host_dock_panel(self) is None:
            if self._base_sizes_stale and not self._planning:
                self._measure_base_sizes()
                self._plan_own_size(force=True)
            return QSize(self._base_sizes[self._orientation])
        return super().minimumSizeHint()

    def hasHeightForWidth(self) -> bool:  # pylint: disable=invalid-name
        """The panel plans for the height it gets, so it doesn't ask for one through its swatch grids."""
        return False

    def heightForWidth(self, unused_width: int) -> int:  # pylint: disable=invalid-name
        """The panel has no height-for-width; see `hasHeightForWidth`."""
        return -1

    def changeEvent(self, event: Optional[QEvent]) -> None:  # pylint: disable=invalid-name
        """Forgets the smallest plans' sizes when a change to the style, font or language would change them.

        The panel gets the change before its children do, so `minimumSizeHint` measures them again when next read
        outside a plan, and reports the old sizes until then.
        """
        super().changeEvent(event)
        if event is not None and event.type() in (QEvent.Type.StyleChange, QEvent.Type.FontChange,
                                                  QEvent.Type.LanguageChange):
            self._base_sizes_stale = True
            self.updateGeometry()

    def _measure_base_sizes(self) -> None:
        """Measures the smallest plan in each orientation. The next plan rearranges the panel."""
        assert self._planner is not None
        orientation_in_use = self._orientation
        self._planning = True
        try:
            for orientation in Orientation:
                self._ring_side = None
                self._base_sizes[orientation] = self._planner.base_size(orientation)
        finally:
            self._planning = False
            self._orientation = orientation_in_use
        self._base_sizes_stale = False

    def _plan_own_size(self, force: bool = False) -> None:
        """Plans for the space the host gave the panel, or for its own size in the dock's orientation without a
        host."""
        if self._planning or self._planner is None:
            return
        if self._space is not None or self._dock_orientation is None:
            super()._plan_own_size(force)
            return
        self._planning = True
        try:
            self._planner.update(self._dock_orientation, self.size(), force)
        finally:
            self._planning = False

    def _prepare_fit(self, _orientation: Orientation) -> None:
        """Measures trial plans with the ring at its smallest."""
        self._ring_side = None

    def _apply_fit(self, orientation: Orientation, placement: Placement) -> None:
        self._orientation = orientation
        strip = orientation == Orientation.STRIP
        self._layout.setDirection(QBoxLayout.Direction.LeftToRight if strip else QBoxLayout.Direction.TopToBottom)
        self._layout.setAlignment(self._parts.header, Qt.AlignmentFlag.AlignTop if strip else Qt.AlignmentFlag(0))
        self._parts.header.set_vertical(strip)
        ring = self._parts.ring_square
        if self._ring_side is None:
            ring.setMinimumSize(RING_MIN_SIZE, RING_MIN_SIZE)
            ring.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
            ring.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        else:
            ring.setFixedSize(self._ring_side, self._ring_side)
        for section, form in zip(self._sections, placement):
            section.set_forced_collapsed(form is None)
        self._arrange_box_sections(self._section_layout, self._sections, orientation)

    def _plan_finished(self, orientation: Orientation) -> None:
        """Grows the ring into the room the plan leaves, and closes the section popover once the plan no longer
        collapses its section."""
        self._grow_ring(orientation)
        popover = self._section_popover
        section = None if popover is None else popover.section
        if section is not None and popover is not None and not section.is_collapsed():
            popover.close_section()

    def _grow_ring(self, orientation: Orientation) -> None:
        """Sets the ring to the largest side, up to `strip_section_max_width()`, at which the plan still fits the space
        it was made for. The content's minimum size grows with the ring, so the largest fitting side is found by
        bisection."""
        assert self._planner is not None
        space = self._planner.available
        placement = self._planner.placement
        if space is None or placement is None or self._wheel_section.is_collapsed():
            return

        def _fits(side: int) -> bool:
            self._ring_side = side
            self._apply_fit(orientation, placement)
            need = self._measure_fit()
            return need.width() <= space.width() and need.height() <= space.height()

        low, high = RING_MIN_SIZE, strip_section_max_width()
        if not _fits(low):
            self._ring_side = None
            self._apply_fit(orientation, placement)
            return
        while low < high:
            middle = (low + high + 1) // 2
            if _fits(middle):
                low = middle
            else:
                high = middle - 1
        if self._ring_side != low:
            _fits(low)

    def _measure_fit(self) -> QSize:
        """Returns the arranged layout's minimum size, not the smallest plan's that `minimumSizeHint` reports."""
        self._measuring = True
        try:
            return fresh_minimum_size(self)
        finally:
            self._measuring = False

    def _open_section_popover(self, section: PanelSection) -> None:
        """Shows a collapsed section's body in a popover under its header."""
        if self._section_popover is None:
            self._section_popover = SectionPopover(self)
        self._section_popover.open_section(section)

    # Color:

    def _update_summaries(self, *_args) -> None:
        ring = self._parts.ring_square
        self._wheel_section.set_summary(WHEEL_SUMMARY.format(hue=round(ring.hue),
                                                             saturation=round(ring.saturation * 100),
                                                             value=round(ring.value * 100)))
        self._sliders_section.set_summary(self._parts.slider_block.summary())

    def _apply_config_color(self, color_str: str) -> None:
        self._parts.set_current_color(QColor(color_str))

    def _update_config_color(self, color: QColor) -> None:
        if self._config_key is not None:
            config = get_config_from_key(self._config_key)
            config.set_color(self._config_key, color)
