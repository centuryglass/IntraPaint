"""Base class for panels that show as much as fits in the space their host reports.

A `DockPanel` subclass declares sections and a priority for each control in `build`. The host calls `set_host_facts`
when the size the panel fills changes, and the panel plans again whenever it is resized. The panel picks its own
orientation from that size and its content's fit (`src.ui.layout.panel_fit.plan_orientation`). Planning
(`src.ui.layout.panel_fit`) moves controls between their sections and the overflow area without rebuilding them, so
their state survives.

- `REQUIRED` controls always stay in their section. An optional control stays while it fits without scrolling, and
  otherwise moves into the popover of the header's "More" button (`PanelHeader`). A `decorative` optional control
  hides instead.
- A control with several forms gets a callback per form, largest first. Planning calls the one for the form that fits.
- The header is a required item. A strip too short for it hides it and moves its More button to the end of the row.
- A footer set with `set_footer` stays below the scrolled content, and counts toward the panel's minimum size.
- A subclass can fill a pinned column (`pinned_layout`) that stays left of content that scrolls sideways, and a
  trailing column (`trailing_layout`) that stays right of it. While the pinned column shows, the footer sits under it.
  Each column scrolls vertically when the panel is too short for it, except a trailing column set not to with
  `set_trailing_scrolls`, which counts toward the panel's minimum height like the footer.
- A panel opts in to column packing with `set_column_packing`. Its strip stacks sections top to bottom in a column
  while they fit the strip's height, instead of giving each its own column.
- Each section is a `src.ui.widget.panel_section.PanelSection`, available as `DockSection.widget` for summaries,
  header actions and remembered expansion. A section with no control left in it hides.
- A section made with `collapsible=True` has a planner item of its own with one form, expanded. Leaving it out collapses
  the section to its header and summary (`PanelSection.set_forced_collapsed`), and a click on that header opens the
  section's body in a popover. The item fills by the section's `priority`, among the controls' priorities, so the
  section collapses after the optional controls it outranks have moved to More. Controls in a collapsed section cost no
  room and stay placed. A section whose controls are all required collapses only if declared `collapsible`.
- Side panels stack sections in one column and scroll vertically. Strip panels put sections in fixed-width columns and
  scroll horizontally. Both also scroll along the other axis when content can't shrink to fit, so nothing is cut off
  out of reach.
- Subclasses add their own items with `add_fit_item`, extend `arrange` for structure that depends on the orientation,
  and override `measure_content` if they move the header. `prepare_fit` and `fit_finished` bracket each plan, for nested
  content that plans itself (`src.ui.layout.panel_fit.FitContent`).
- The host calls `host_floating_changed` when the panel's dock starts or stops floating.
- A title note (`set_title_note`) is short text a floating dock's title bar shows beside the dock's name.
- Call `refit` after a change to the content's size that no resize reports, such as a control appearing.
"""
from dataclasses import dataclass, field
from functools import partial
from typing import Callable, Optional, Sequence

from PySide6.QtCore import QEvent, QMargins, QObject, QPointF, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPaintEvent, QPainter, QPalette, QPen, QResizeEvent
from PySide6.QtWidgets import (QApplication, QBoxLayout, QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QStyle,
                               QVBoxLayout, QWidget)

from src.ui.ink_style import InkStyle
from src.ui.layout.bordered_widget import DEFAULT_LINE_WIDTH
from src.ui.layout.column_packing import PackedColumns, pack_columns
from src.ui.layout.flow_layout import FlowWidget
from src.ui.layout.panel_fit import (REQUIRED, STRIP_SECTION_MAX_WIDTH, STRIP_SECTION_MIN_WIDTH, FitItem, FitPlanner,
                                     Orientation, Placement, cross_extent, fresh_minimum_size,
                                     held_weakly, scroll_extent)
from src.ui.widget.panel_header import PanelHeader, PanelPopover
from src.ui.widget.panel_section import PanelSection

QWIDGETSIZE_MAX = 16777215

# The header's forms:
HEADER_SHOWN = 0
HEADER_COLLAPSED = 1


@dataclass
class _Control:
    widget: QWidget
    priority: int
    forms: tuple[Callable[[], None], ...]
    decorative: bool
    # The placed form, or None while the control is in the More popover or hidden:
    form: Optional[int] = 0

    @property
    def item(self) -> FitItem:
        """The planner item for this control."""
        return FitItem(self.priority, max(len(self.forms), 1))


class DockSection:
    """A titled group of controls, each with a priority. Created through `PanelLayout.section`.

    `widget` is the `PanelSection` the panel shows, for summaries, header actions and remembered expansion. A
    `collapsible` section gets a planner item with the given `priority`, which must be above `REQUIRED`.
    """

    def __init__(self, title: str, collapsible: bool = False, priority: int = 1) -> None:
        if collapsible and priority <= REQUIRED:
            raise ValueError(f'Invalid priority {priority}')
        self.title = title
        # Whether planning may collapse the section, and its place in the fill order if so:
        self.collapsible = collapsible
        self.priority = priority
        # Whether the latest plan collapsed the section:
        self.collapsed_by_fit = False
        self._body = QWidget()
        self._layout = QVBoxLayout(self._body)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.widget = PanelSection(title, self._body)
        # Heading shown above this section's controls while they sit in the More popover:
        self.overflow_title = QLabel(title)
        self.overflow_title.hide()
        self._controls: list[_Control] = []

    @property
    def widgets(self) -> list[QWidget]:
        """All controls added to the section, in order."""
        return [control.widget for control in self._controls]

    @property
    def controls(self) -> list[_Control]:
        """The section's controls with their planning state, in order."""
        return list(self._controls)

    def add(self, widget: QWidget, priority: int = REQUIRED, forms: Sequence[Callable[[], None]] = (),
            decorative: bool = False) -> None:
        """Adds a control. `forms` are callbacks that put it in each of its forms, largest first.

        The section holds bound-method forms weakly, since its panel owns the section. A lambda that captures the panel
        still makes a reference cycle (see `FitPlanner`).

        Raises ValueError for a negative priority, or for a required control marked decorative.
        """
        if priority < REQUIRED:
            raise ValueError(f'Invalid priority {priority}')
        if decorative and priority == REQUIRED:
            raise ValueError('A required control is always shown, so it cannot be decorative')
        self._controls.append(_Control(widget, priority, tuple(held_weakly(form) for form in forms), decorative))
        self._layout.addWidget(widget)

    def place(self, overflow_layout: QBoxLayout) -> list[QWidget]:
        """Moves each control into the section, the overflow layout or out of view by its placed form, returning the
        controls moved to the overflow layout."""
        overflowed: list[QWidget] = []
        for control in self._controls:
            if control.form is None and not control.decorative:
                if len(overflowed) == 0:
                    overflow_layout.addWidget(self.overflow_title)
                    self.overflow_title.show()
                overflow_layout.addWidget(control.widget)
                overflowed.append(control.widget)
                control.widget.show()
            else:
                self._layout.addWidget(control.widget)
                control.widget.setVisible(control.form is not None)
        if len(overflowed) == 0:
            self.overflow_title.hide()
        self.widget.setVisible(any(control.form is not None for control in self._controls))
        return overflowed


class _PinnedScrollArea(QScrollArea):
    """A scroll area for the pinned column. The panel sets its minimum and preferred widths while planning."""

    def __init__(self) -> None:
        super().__init__()
        self._preferred_width = 0

    def set_preferred_width(self, width: int) -> None:
        """Sets the width the scroll area prefers. It is never less than its minimum width."""
        if width != self._preferred_width:
            self._preferred_width = width
            self.updateGeometry()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the preferred width, and never less than the minimum width."""
        return QSize(max(self._preferred_width, self.minimumWidth()), super().sizeHint().height())


class _PinnedColumn:
    """A column beside the scrolled content that scrolls vertically on its own: the scroll area, the content it scrolls
    and the layout of that content."""

    def __init__(self) -> None:
        self.content = QWidget()
        self.layout = QVBoxLayout(self.content)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = _PinnedScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.content)
        self.column = QWidget()
        self.column_layout = QVBoxLayout(self.column)
        self.column_layout.setContentsMargins(0, 0, 0, 0)
        self.column_layout.addWidget(self.scroll, stretch=1)
        self.column.hide()

    @property
    def shown(self) -> bool:
        """Whether the column is shown."""
        return not self.column.isHidden()


class PanelDivider(QWidget):
    """A line between a pinned or trailing column, or a footer, and the content beside or above it. Drawn in the
    Ink theme's `InkColors.panel_edge` (the color panel outlines use), inset from its ends so it doesn't read as a
    panel of its own."""

    def __init__(self, orientation: Qt.Orientation = Qt.Orientation.Vertical) -> None:
        super().__init__()
        self._orientation = orientation
        if orientation == Qt.Orientation.Vertical:
            self.setFixedWidth(DEFAULT_LINE_WIDTH)
        else:
            self.setFixedHeight(DEFAULT_LINE_WIDTH)

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draws the inset line."""
        gap = self.style().pixelMetric(QStyle.PixelMetric.PM_LayoutLeftMargin, None, self)
        style = self.style()
        color = style.colors.panel_edge if isinstance(style, InkStyle) else self.palette().color(
            QPalette.ColorRole.Shadow)
        painter = QPainter(self)
        painter.setPen(QPen(color, DEFAULT_LINE_WIDTH))
        if self._orientation == Qt.Orientation.Vertical:
            x = DEFAULT_LINE_WIDTH / 2
            painter.drawLine(QPointF(x, gap), QPointF(x, self.height() - gap))
        else:
            y = DEFAULT_LINE_WIDTH / 2
            painter.drawLine(QPointF(gap, y), QPointF(self.width() - gap, y))
        painter.end()


@dataclass
class PanelLayout:
    """Collects the sections a `DockPanel` declares in `build`."""
    sections: list[DockSection] = field(default_factory=list)

    def section(self, title: str, collapsible: bool = False, priority: int = 1) -> DockSection:
        """Adds and returns a new section. With `collapsible`, planning collapses it to its summary when it doesn't fit,
        after optional controls with a lower priority number have been placed."""
        new_section = DockSection(title, collapsible, priority)
        self.sections.append(new_section)
        return new_section


class DockPanel(QWidget):
    """A panel that shows as much of its content as fits its dock's size, in the orientation that fits it best."""

    title_note_changed = Signal()

    def __init__(self, name: str = '', icon: Optional[QIcon] = None, key_text: str = '',
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # The orientation the panel is arranged in:
        self._orientation = Orientation.SIDE
        self._arranged_orientation: Optional[Orientation] = None
        # The orientation, scroll-axis size and cross extent (with the inset) the content last overflowed to, if it
        # still applies:
        self._cross_floor: Optional[tuple[Orientation, int, int]] = None
        # The inputs of the latest plan that checked for overflow, so repeated ones don't measure again:
        self._floor_inputs: Optional[tuple[Optional[Orientation], QSize]] = None
        # The minimum and preferred size hints the panel last reported outside a plan, which it reports during one:
        self._reported_minimum: Optional[QSize] = None
        self._reported_preferred: Optional[QSize] = None
        self._planning = False
        # Whether anything read a size hint during the running plan:
        self._hints_read_while_planning = False
        self._layout_model = PanelLayout()
        self._extra_items: list[tuple[FitItem, Callable[[Optional[int]], None]]] = []
        self._planner: Optional[FitPlanner] = None
        self._strip_scroll_limit: Optional[float] = None
        self._fresh_sizes: Optional[dict[QWidget, QSize]] = None
        self._header_collapsed = False
        self._title_note = ''
        self._scrolls = False
        self._overflow: list[QWidget] = []
        self._footer: Optional[QWidget] = None
        self._packs_columns = False
        self._packed = False
        # The room the horizontal scroll bar takes from column packing's height, while the content scrolls:
        self._pack_reserve = 0
        # The room the scroll bar takes across the scrolled body, while the content scrolls:
        self._scroll_bar_room = 0
        self._packed_columns = PackedColumns()
        # Shows a collapsed section's body when its header is clicked, and the section it shows:
        self._section_popover: Optional[PanelPopover] = None
        self._popover_section: Optional[DockSection] = None

        self._header = PanelHeader(name, icon, key_text)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer = QVBoxLayout(self)
        # The inset keeps content off the window edge. The style supplies it, so it follows the font size and DPI:
        self._inset = self.style().pixelMetric(QStyle.PixelMetric.PM_LayoutLeftMargin, None, self)
        outer.setContentsMargins(self._inset, self._inset, self._inset, self._inset)
        outer.addWidget(self._header)
        # The pinned column sits left of the scroll area and the trailing column right of it:
        self._pinned = _PinnedColumn()
        self._pinned_divider = PanelDivider()
        self._pinned_divider.hide()
        # Created by the first use of `trailing_layout`, so panels without one have no widget for it:
        self._trailing: Optional[_PinnedColumn] = None
        self._trailing_divider: Optional[PanelDivider] = None
        # Created by `set_footer`, so panels without one have no widget for it:
        self._footer_divider: Optional[PanelDivider] = None
        self._trailing_scrolls = True
        self._scroll_row = QHBoxLayout()
        self._scroll_row.setContentsMargins(0, 0, 0, 0)
        self._scroll_row.addWidget(self._pinned.column)
        self._scroll_row.addWidget(self._pinned_divider)
        self._scroll_row.addWidget(self._scroll, stretch=1)
        outer.addLayout(self._scroll_row)

        self._body = QWidget()
        self._body_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self._body)
        self._scroll.setWidget(self._body)
        self._section_holder = QWidget()
        self._section_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self._section_holder)
        self._section_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.addWidget(self._section_holder)
        self._body_layout.addStretch()

        self._overflow_content = QWidget()
        self._overflow_layout = QVBoxLayout(self._overflow_content)
        self._overflow_layout.setContentsMargins(0, 0, 0, 0)

        self.build(self._layout_model)
        for section in self._layout_model.sections:
            self._section_layout.addWidget(section.widget)
            section.widget.expanded_changed.connect(self._on_section_toggled)
            if section.collapsible:
                section.widget.forced_header_clicked.connect(partial(self._open_section_popover, section))

    def build(self, ui: PanelLayout) -> None:
        """Declares sections and controls. Subclasses override it. Called once, from the constructor."""

    def set_footer(self, footer: QWidget) -> None:
        """Pins a widget below the scrolled content, such as a panel's main action. Call it once, from `build` or the
        constructor."""
        if self._footer is not None:
            raise RuntimeError('Tried to set a footer twice')
        self._footer = footer
        self._footer_divider = PanelDivider(Qt.Orientation.Horizontal)
        self.layout().addWidget(self._footer_divider)
        self.layout().addWidget(footer)
        self._footer_divider.setHidden(footer.isHidden())
        footer.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # pylint: disable=invalid-name
        """Keeps the footer's divider hidden exactly while the footer itself is hidden, however that changes.

        It follows `isHidden`, not visibility, so the divider counts toward the minimum size before the panel is first
        shown and while it is out of view."""
        if watched is self._footer and self._footer_divider is not None \
                and event.type() in (QEvent.Type.Show, QEvent.Type.Hide):
            self._footer_divider.setHidden(self._footer.isHidden())
        return super().eventFilter(watched, event)

    @property
    def pinned_layout(self) -> QVBoxLayout:
        """The layout of a column left of the scrolled content, which stays in place while the content scrolls
        sideways. Subclasses fill it in `arrange`, and show it with `set_pinned_visible`.

        The column takes its content's minimum width, and grows toward the content's preferred width, capped by its
        maximum width, while that leaves room for the scrolled content's minimum width beside it. Scrolled content that
        doesn't fit beside the column's minimum scrolls anyway, and the column then leaves room for one strip column.
        """
        return self._pinned.layout

    def set_pinned_visible(self, visible: bool) -> None:
        """Shows or hides the pinned column. While it shows, the footer sits under it instead of under the scrolled
        content, and the pinned content scrolls vertically above the footer when the panel is too short for it."""
        if self._footer is not None:
            assert self._footer_divider is not None
            if visible:
                self._pinned.column_layout.addWidget(self._footer_divider)
                self._pinned.column_layout.addWidget(self._footer)
            else:
                self.layout().addWidget(self._footer_divider)
                self.layout().addWidget(self._footer)
            self._footer.show()
        self._pinned.column.setVisible(visible)
        self._pinned_divider.setVisible(visible)

    @property
    def trailing_layout(self) -> QVBoxLayout:
        """The layout of a column right of the scrolled content, which stays in place while the content scrolls
        sideways. Subclasses fill it in `arrange`, and show it with `set_trailing_visible`.

        It follows the pinned column's rules for width and vertical scrolling. The footer never moves into it, so
        content that is a side panel's footer and a strip's trailing column moves between them in `arrange`.
        """
        return self._trailing_column().layout

    def _trailing_column(self) -> _PinnedColumn:
        if self._trailing is None:
            self._trailing = _PinnedColumn()
            self._trailing_divider = PanelDivider()
            self._trailing_divider.hide()
            self._scroll_row.addWidget(self._trailing_divider)
            self._scroll_row.addWidget(self._trailing.column)
        return self._trailing

    def set_trailing_visible(self, visible: bool) -> None:
        """Shows or hides the trailing column."""
        self._trailing_column().column.setVisible(visible)
        assert self._trailing_divider is not None
        self._trailing_divider.setVisible(visible)

    def set_trailing_scrolls(self, scrolls: bool) -> None:
        """Sets whether the trailing column scrolls vertically when the panel is too short for it, the default. A
        column that doesn't scroll counts its content's minimum height toward the panel's minimum, so content such as a
        panel's main action stays in view."""
        self._trailing_scrolls = scrolls
        self._trailing_column().scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded if scrolls
                                                                   else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def set_column_packing(self, enabled: bool) -> None:
        """Opts the panel in or out of column packing. Call it once, from `build` or the constructor.

        A packing strip fills columns top to bottom: a section goes under the previous one in its column when both fit
        the strip's height, and starts a new column otherwise. A section never splits across columns. Collapsed
        sections are short, so they stack. Opening or closing a section plans again. In a packing strip a collapsed
        section draws its summary on a second line, since its column is too narrow for one line.

        Sections a subclass moves out of `section_layout`, such as into the pinned column, stay where it put them.
        """
        self._packs_columns = enabled

    def set_strip_scroll_limit(self, limit: Optional[float]) -> None:
        """Sets the largest share of the panel's content a strip may hide sideways before a side panel wins over it,
        or None for no limit (`src.ui.layout.panel_fit.plan_orientation`). Call it once, from `build` or the
        constructor."""
        self._strip_scroll_limit = limit
        if self._planner is not None:
            self._planner.strip_scroll_limit = limit

    @property
    def section_layout(self) -> QBoxLayout:
        """The layout that holds the sections' widgets in order, for `arrange` overrides that move a section out and
        back."""
        return self._section_layout

    @property
    def inset(self) -> int:
        """The margin between the panel's edges and everything in it, taken from the style. `available_size` is the
        panel's size less the inset on each side."""
        return self._inset

    def content_margins(self) -> QMargins:
        """Returns the margins between the panel's edges and its scrolled content."""
        return self._body_layout.contentsMargins()

    @property
    def header(self) -> PanelHeader:
        """The panel's header, which hosts the More button."""
        return self._header

    @property
    def orientation(self) -> Orientation:
        """The orientation the panel is arranged in, which planning picks from the size and the content's fit."""
        return self._orientation

    @property
    def available_size(self) -> Optional[QSize]:
        """The size being planned for, or the latest plan's, or None before the first plan."""
        return self._planner.available if self._planner is not None else None

    @property
    def header_collapsed(self) -> bool:
        """Whether the header is hidden, with its More button at the end of the row."""
        return self._header_collapsed

    @property
    def sections(self) -> list[DockSection]:
        """The sections declared in `build`."""
        return list(self._layout_model.sections)

    @property
    def overflow_widgets(self) -> list[QWidget]:
        """The controls currently in the More popover's content."""
        return list(self._overflow)

    def add_fit_item(self, item: FitItem, apply: Callable[[Optional[int]], None]) -> None:
        """Adds an item for planning beside the sections' controls. `apply` puts it in a form by index, or with None
        leaves an optional item out.

        Items added here fill after the header and before section controls of the same priority, in the order added. A
        bound-method `apply` is held weakly (see `DockSection.add`).
        """
        self._extra_items.append((item, held_weakly(apply)))
        self._planner = None

    def host_floating_changed(self, floating: bool) -> None:
        """Called by the host when the panel starts or stops floating in its own window. Subclasses override it, for
        example to drop header content that the floating window's title bar repeats."""

    @property
    def title_note(self) -> str:
        """Short text a floating dock's title bar shows beside the dock's name, or '' for none."""
        return self._title_note

    def set_title_note(self, note: str) -> None:
        """Sets the title note, and emits `title_note_changed` if it changed."""
        if note != self._title_note:
            self._title_note = note
            self.title_note_changed.emit()

    def set_host_facts(self, size: QSize) -> None:
        """Called by the host when the size the panel fills changes. Plans again if it changed, picking the
        orientation with `src.ui.layout.panel_fit.plan_orientation`."""
        self._update_plan(None, self._inside_inset(size))

    def _inside_inset(self, size: QSize) -> QSize:
        """Returns the size left for planning once the inset around the panel's content is removed."""
        return QSize(max(size.width() - 2 * self._inset, 0), max(size.height() - 2 * self._inset, 0))

    def plan_in(self, orientation: Orientation, size: QSize) -> None:
        """Plans for `size` in `orientation` alone. Later plans treat it as the arrangement in use, so it holds while
        it fits as well as the other orientation and `size` is within `HYSTERESIS` of a square."""
        self._update_plan(orientation, self._inside_inset(size))

    def refit(self) -> None:
        """Plans again for the latest size, after the content's own size changed."""
        planner = self._fit_planner()
        available = planner.available
        self._update_plan(None, available if available is not None else self._inside_inset(self.size()), force=True)

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:  # pylint: disable=invalid-name
        """Plans for the new size."""
        super().resizeEvent(event)
        self._update_plan(None, self._inside_inset(self.size()))

    def _update_plan(self, orientation: Optional[Orientation], available: QSize, force: bool = False) -> None:
        """Plans for an available size, then records the cross extent the content overflows to, if it overflows.

        While the plan runs, the panel's size hints are the ones it last reported (see `minimumSizeHint`). Anything that
        read them then is told to read them again afterwards.
        """
        if self._planning:
            self._plan(orientation, available, force)
            return
        self._planning = True
        self._hints_read_while_planning = False
        try:
            self._plan(orientation, available, force)
        finally:
            self._planning = False
        if self._hints_read_while_planning:
            self.updateGeometry()

    def _plan(self, orientation: Optional[Orientation], available: QSize, force: bool) -> None:
        planner = self._fit_planner()
        planner.update(orientation, available, force)
        if not force and self._floor_inputs == (orientation, available):
            return
        self._floor_inputs = (orientation, QSize(available))
        plan_orientation = self._orientation
        scroll = scroll_extent(available, plan_orientation)
        need = cross_extent(self.measure(), plan_orientation)
        if need > cross_extent(available, plan_orientation):
            floor = (plan_orientation, scroll, need + 2 * self._inset)
        elif self._cross_floor is not None and self._cross_floor[:2] == (plan_orientation, scroll):
            floor = self._cross_floor
        else:
            floor = None
        if floor != self._cross_floor:
            self._cross_floor = floor
            self.updateGeometry()

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the layout's minimum size, with the cross axis raised to the extent the content overflowed to, so a
        dock stops shrinking the panel where its content would escape the panel.

        The floor is learned when the content overflows and applies while the orientation and the scroll-axis size stay
        the same, since the smallest placement's cross extent depends on both.

        While a plan runs, it returns the hint it last returned outside one, as `sizeHint` does. Showing a widget
        activates the layouts of every shown ancestor, so a trial arrangement's hints would otherwise reach the dock's
        main window, which resizes the dock to fit an arrangement the plan may not keep.
        """
        if self._planning and self._reported_minimum is not None:
            self._hints_read_while_planning = True
            return QSize(self._reported_minimum)
        hint = super().minimumSizeHint()
        if self._cross_floor is not None:
            orientation, _, floor = self._cross_floor
            if orientation == Orientation.SIDE:
                hint = QSize(max(hint.width(), floor), hint.height())
            else:
                hint = QSize(hint.width(), max(hint.height(), floor))
        if not self._planning:
            self._reported_minimum = QSize(hint)
        return hint

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the layout's preferred size, or while a plan runs, the one it last returned outside one (see
        `minimumSizeHint`)."""
        if self._planning and self._reported_preferred is not None:
            self._hints_read_while_planning = True
            return QSize(self._reported_preferred)
        hint = super().sizeHint()
        if not self._planning:
            self._reported_preferred = QSize(hint)
        return hint

    def arrange(self, orientation: Orientation) -> None:
        """Lays out structure that depends only on the orientation. Called when it changes, before any placement.

        Overrides should call this and then adjust. No widget is created or destroyed here.
        """
        horizontal = orientation == Orientation.STRIP
        direction = QBoxLayout.Direction.LeftToRight if horizontal else QBoxLayout.Direction.TopToBottom
        self._section_layout.setDirection(direction)
        self._body_layout.setDirection(direction)
        self._set_packed(horizontal and self._packs_columns)
        for section in self._layout_model.sections:
            section.widget.set_summary_below(horizontal and self._packs_columns)
            if horizontal:
                section.widget.setMinimumWidth(STRIP_SECTION_MIN_WIDTH)
                section.widget.setMaximumWidth(STRIP_SECTION_MAX_WIDTH)
                section.widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            else:
                section.widget.setMinimumWidth(0)
                section.widget.setMaximumWidth(QWIDGETSIZE_MAX)
                section.widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    @property
    def content_scrolls(self) -> bool:
        """Whether the content arranged for the latest measurement overflows along the scroll axis."""
        return self._scrolls

    def scroll_bar_extent(self) -> int:
        """Returns how much room the scroll bar takes across the panel while the content scrolls."""
        if self._orientation == Orientation.SIDE:
            return self._scroll.verticalScrollBar().sizeHint().width()
        return self._scroll.horizontalScrollBar().sizeHint().height()

    def measure(self) -> QSize:
        """Returns the content's minimum size as currently arranged, from `measure_content`, with room across the
        scrolled body for the scroll bar when the content overflows along the scroll axis.

        The scroll bar sits inside the scroll area, so it adds to the body alone, not to the header, footer or columns
        beside it. A scroll bar narrows the body, so the header is fit to its `header_width` again when that changes.
        """
        self._pack_reserve = 0
        self._scroll_bar_room = 0
        need = self.measure_content()
        available = self.available_size
        scrolls = available is not None and scroll_extent(need, self._orientation) > scroll_extent(available,
                                                                                                  self._orientation)
        if not scrolls and scrolls == self._scrolls:
            return need
        if scrolls != self._scrolls:
            self._scrolls = scrolls
            self._fit_header_width()
        if scrolls:
            self._scroll_bar_room = self.scroll_bar_extent()
            if self._packed:
                self._pack_reserve = self._scroll_bar_room
        return self.measure_content()

    def measure_content(self) -> QSize:
        """Returns the content's minimum size as currently arranged: the header, if shown above the scroll area, over
        the pinned, scrolled and trailing columns, over the footer if it is still below them."""
        self._fresh_sizes = {}
        try:
            return self._measure_content()
        finally:
            self._fresh_sizes = None

    def _measure_content(self) -> QSize:
        if self._packed:
            self._pack_sections()
        content = fresh_minimum_size(self._body)
        if self._orientation == Orientation.SIDE:
            content.setWidth(content.width() + self._scroll_bar_room)
        else:
            content.setHeight(content.height() + self._scroll_bar_room)
        spacing = max(self.layout().spacing(), 0)
        if self._pinned.shown or (self._trailing is not None and self._trailing.shown):
            content = self._measure_with_pinned_columns(content)
        if not self._header.isHidden() and self._header.parentWidget() is self:
            header = self._fresh_size(self._header)
            content = QSize(max(content.width(), header.width()), content.height() + spacing + header.height())
        if self._footer is not None and not self._footer.isHidden() and self._footer.parentWidget() is self:
            assert self._footer_divider is not None
            footer = self._fresh_size(self._footer)
            divider_height = self._footer_divider.height() + spacing
            content = QSize(max(content.width(), footer.width()),
                            content.height() + spacing + divider_height + footer.height())
        return content

    def _fresh_size(self, widget: QWidget) -> QSize:
        """Returns `fresh_minimum_size` of a header, footer or column content, measured once per `measure_content`.

        Packing sections and sizing columns never change those widgets' sizes, so the later measurements in one
        `measure_content` repeat the first.
        """
        if self._fresh_sizes is None:
            return fresh_minimum_size(widget)
        if widget not in self._fresh_sizes:
            self._fresh_sizes[widget] = fresh_minimum_size(widget)
        return QSize(self._fresh_sizes[widget])

    def _measure_with_pinned_columns(self, body: QSize) -> QSize:
        """Returns the size of the shown pinned and trailing columns beside the scrolled body, and sets their scroll
        areas' widths.

        Each column's content scrolls on its own, so it adds only its scroll area's minimum height. It gets a scroll bar
        when it is taller than the room it has under the header and over its footer, if it has one. A trailing column
        set not to scroll adds its content's minimum height instead.
        """
        available = self.available_size
        row_spacing = max(self._scroll_row.spacing(), 0)
        header_height = 0
        if not self._header.isHidden() and self._header.parentWidget() is self:
            header_height = self._fresh_size(self._header).height() + max(self.layout().spacing(), 0)
        footer = QSize(0, 0)
        if self._footer is not None and not self._footer.isHidden():
            footer = self._fresh_size(self._footer)
            assert self._footer_divider is not None
            footer = QSize(footer.width(), footer.height() + self._footer_divider.height())
        columns = [column for column in (self._pinned, self._trailing) if column is not None and column.shown]
        widths: list[int] = []
        sizes: list[QSize] = []
        for column in columns:
            column_footer = footer if column is self._pinned else QSize(0, 0)
            column_spacing = (2 * max(column.column_layout.spacing(), 0)) if column_footer.height() > 0 else 0
            content = self._fresh_size(column.content)
            width = content.width() + column.scroll.frameWidth() * 2
            scrolls = column is not self._trailing or self._trailing_scrolls
            if available is not None and scrolls:
                room = available.height() - column_footer.height() - column_spacing - header_height
                if content.height() > room:
                    width += column.scroll.verticalScrollBar().sizeHint().width()
            column.scroll.setMinimumWidth(width)
            widths.append(width)
            column.scroll.setMinimumHeight(0 if scrolls else content.height() + column.scroll.frameWidth() * 2)
            height = column.scroll.minimumSizeHint().height() if scrolls else column.scroll.minimumHeight()
            sizes.append(QSize(max(width, column_footer.width()), height + column_spacing + column_footer.height()))
        # Each prefers its content's preferred width, up to its maximum width, less room for the body beside the
        # minimums of the rest. A body too wide for that room scrolls anyway, so the column leaves room for one strip
        # column:
        for index, column in enumerate(columns):
            preferred = min(column.content.sizeHint().width(), column.content.maximumWidth())
            if available is not None:
                others = sum(size.width() + row_spacing for other, size in zip(columns, sizes) if other is not column)
                room = available.width() - row_spacing - others
                body_room = body.width() if body.width() <= room - widths[index] else STRIP_SECTION_MIN_WIDTH
                preferred = min(preferred, room - body_room)
            column.scroll.set_preferred_width(preferred + widths[index] - self._fresh_size(column.content).width())
        columns_width = sum(size.width() + row_spacing for size in sizes)
        if self._pinned.shown:
            columns_width += self._pinned_divider.width() + row_spacing
        if self._trailing is not None and self._trailing.shown:
            assert self._trailing_divider is not None
            columns_width += self._trailing_divider.width() + row_spacing
        return QSize(columns_width + body.width(), max(max(size.height() for size in sizes), body.height()))

    def measure_with_control(self, control: _Control) -> QSize:
        """Returns the content's minimum size with one more control added in its smallest form, and every control
        already shown in its smallest form. The header, extra items and controls left out stay as placed, and the panel
        is arranged as before afterwards.

        Layout checks use it to ask whether a control left in More or hidden would have fit if the shown controls had
        given it room.
        """
        planner = self._fit_planner()
        placement = planner.placement
        if placement is None:
            return self.measure()
        offset = 1 + len(self._extra_items) + len(self._collapsible_sections())
        trial = list(placement)
        for index, other in enumerate(self._controls()):
            if other is control or other.form is not None:
                trial[offset + index] = max(len(other.forms), 1) - 1
        return planner.measure_placement(tuple(trial))

    def prepare_fit(self, orientation: Orientation) -> None:
        """Called before each plan's trials. Subclasses override it to put nested content in a fixed state."""

    def fit_finished(self, orientation: Orientation) -> None:
        """Called after each plan is applied. Subclasses override it to pass space on to nested content."""

    def header_width(self, available: QSize) -> int:
        """Returns the width the header gets in an available size. Overrides that move the header return its width
        there."""
        return available.width()

    def apply_header_form(self, collapsed: bool) -> None:
        """Shows the header, or hides it in a strip too short for it. Overrides should call this.

        A shown header is sized to its `header_width` first, because whether its key and description wrap to a second
        line depends on its width.
        """
        self._header_collapsed = collapsed
        self._header.setVisible(not collapsed)
        self._fit_header_width()

    def _fit_header_width(self) -> None:
        available = self.available_size
        if not self._header_collapsed and available is not None:
            self._header.resize(self.header_width(available), self._header.height())

    def finish_placement(self) -> None:
        """Updates the More popover and button after every item is placed. Overrides should call this."""
        content = self.more_content()
        self._header.set_popover_content(content)
        more_button = self._header.more_button
        if self._header_collapsed:
            self._body_layout.addWidget(more_button)
        else:
            self._header.restore_more_button()
        # Reparenting hides a widget:
        more_button.setVisible(content is not None)

    def more_content(self) -> Optional[QWidget]:
        """Returns the widget the More popover shows, or None to hide the More button. By default it holds the
        controls that didn't fit. Overrides that always show the button keep the header's width the same before and
        after a plan."""
        return self._overflow_content if self._overflow else None

    def _collapsible_sections(self) -> list[DockSection]:
        return [section for section in self._layout_model.sections if section.collapsible]

    def _controls(self) -> list[_Control]:
        return [control for section in self._layout_model.sections for control in section.controls]

    def _fit_planner(self) -> FitPlanner:
        if self._planner is None:
            items = [FitItem(REQUIRED, 2), *(item for item, _ in self._extra_items),
                     *(FitItem(section.priority) for section in self._collapsible_sections()),
                     *(control.item for control in self._controls())]
            self._planner = FitPlanner(items, self._apply_placement, self.measure, self.prepare_fit,
                                       self._plan_finished)
            self._planner.strip_scroll_limit = self._strip_scroll_limit
        return self._planner

    def _plan_finished(self, orientation: Orientation) -> None:
        self.fit_finished(orientation)
        # Refresh the cached sizes trials left behind, then have the scroll area re-fit the body to them at once. Its
        # own update waits on a posted layout request, and planning runs after it sized the body for this resize:
        self.measure()
        QApplication.sendEvent(self._scroll, QEvent(QEvent.Type.LayoutRequest))
        self._apply_layouts()
        # A planned wrap width is an estimate of the width a flow gets. One that missed leaves the flow's height
        # measured for the wrong width, and a resize event only corrects it when the width changes:
        stale = [flow for flow in self.findChildren(FlowWidget)
                 if not flow.isHidden() and flow.wrap_width != flow.width()]
        if stale:
            for flow in stale:
                flow.set_wrap_width(flow.width())
            self.measure()
            self._apply_layouts()

    def _apply_layouts(self) -> None:
        """Applies the planned layout's geometry now, parents first.

        Qt otherwise applies it on posted layout requests. A window resize paints before those run, so each resize
        would show a half-applied layout and then the finished one, which flickers. A second pass applies size hints
        that changed during the first, such as a header that wrapped to fit its new width.
        """
        for _ in range(2):
            for widget in [self, *self.findChildren(QWidget)]:
                layout = widget.layout()
                if layout is not None and not widget.isHidden() and not widget.isWindow():
                    layout.activate()

    def _apply_placement(self, orientation: Orientation, placement: Placement) -> None:
        self._orientation = orientation
        if orientation != self._arranged_orientation:
            self._arranged_orientation = orientation
            self.arrange(orientation)
        # Only a strip collapses its header, so a side panel's two header forms are the same:
        self.apply_header_form(placement[0] == HEADER_COLLAPSED and orientation == Orientation.STRIP)
        extra_count = len(self._extra_items)
        for (_, apply), form in zip(self._extra_items, placement[1:1 + extra_count]):
            apply(form)
        collapsible = self._collapsible_sections()
        section_count = len(collapsible)
        for section, form in zip(collapsible, placement[1 + extra_count:1 + extra_count + section_count]):
            section.collapsed_by_fit = form is None
            section.widget.set_forced_collapsed(form is None)
            if form is not None and self._popover_section is section:
                self._close_section_popover()
        for control, form in zip(self._controls(), placement[1 + extra_count + section_count:]):
            control.form = form
            if form is not None and len(control.forms) > 0:
                control.forms[form]()
        self._overflow = []
        for section in self._layout_model.sections:
            self._overflow.extend(section.place(self._overflow_layout))
        self.finish_placement()

    def _open_section_popover(self, section: DockSection) -> None:
        """Shows a collapsed section's body in a popover under its header. The body returns to the section when the
        popover closes or planning expands the section."""
        if self._section_popover is None:
            self._section_popover = PanelPopover(self)
            self._section_popover.closed.connect(self._restore_popover_section)
        if self._popover_section is not None:
            self._close_section_popover()
        self._popover_section = section
        self._section_popover.set_content(section.widget.detach_body())
        self._section_popover.popup_below(section.widget.header_button, align_left=True)

    def _close_section_popover(self) -> None:
        if self._section_popover is not None:
            self._section_popover.hide()
        self._restore_popover_section()

    def _restore_popover_section(self) -> None:
        section = self._popover_section
        if section is None:
            return
        self._popover_section = None
        if self._section_popover is not None:
            self._section_popover.set_content(None)
        section.widget.restore_body()

    def _on_section_toggled(self, _expanded: bool) -> None:
        """Plans again when a section opens or closes in a packing strip, since its height decides the columns."""
        if self._packed:
            self.refit()

    def _set_packed(self, packed: bool) -> None:
        """Enters or leaves column packing. Leaving puts every section back in `section_layout` in order."""
        if packed == self._packed:
            return
        self._packed = packed
        if packed:
            return
        sections = [section.widget for section in self._layout_model.sections if self._packable(section.widget)]
        self._packed_columns.release(sections)
        for column in self._packed_columns.columns:
            self._section_layout.removeWidget(column)
        for widget in sections:
            self._section_layout.addWidget(widget)

    def _packable(self, widget: QWidget) -> bool:
        """Whether a section is still where `section_layout` or a packed column holds it."""
        parent = widget.parentWidget()
        return parent is self._section_holder or parent in self._packed_columns.columns

    def _column_budget(self) -> int:
        """Returns the height a packed column has: the strip's, less the header and footer above and below the scrolled
        content, the body's margins and the horizontal scroll bar's room. It is zero before the first plan, which gives
        every section its own column."""
        available = self.available_size
        if available is None:
            return 0
        margins = self._body_layout.contentsMargins()
        budget = available.height() - self._pack_reserve - margins.top() - margins.bottom()
        spacing = max(self.layout().spacing(), 0)
        if not self._header.isHidden() and self._header.parentWidget() is self:
            budget -= self._fresh_size(self._header).height() + spacing
        if self._footer is not None and not self._footer.isHidden() and self._footer.parentWidget() is self:
            assert self._footer_divider is not None
            budget -= self._fresh_size(self._footer).height() + self._footer_divider.height() + 2 * spacing
        return budget

    def _pack_sections(self) -> None:
        """Splits the shown sections into columns by their measured heights, then moves them into the columns."""
        widgets = [section.widget for section in self._layout_model.sections
                   if self._packable(section.widget) and not section.widget.isHidden()]
        spacing = max(self._section_layout.spacing(), 0)
        heights = [fresh_minimum_size(widget).height() for widget in widgets]
        plan = [tuple(widgets[index] for index in column)
                for column in pack_columns(heights, self._column_budget(), spacing)]
        if plan == self._packed_columns.plan:
            return
        for column in self._packed_columns.columns:
            self._section_layout.removeWidget(column)
        self._packed_columns.fill(plan, spacing, self._section_layout.addWidget)
