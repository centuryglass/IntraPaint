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
- A subclass can fill a pinned column (`pinned_layout`) that stays left of content that scrolls sideways. While it
  shows, the footer sits under it.
- Each section is a `src.ui.widget.panel_section.PanelSection`, available as `DockSection.widget` for summaries,
  header actions and remembered expansion. A section with no control left in it hides.
- Side panels stack sections in one column and scroll vertically. Strip panels put sections in fixed-width columns and
  scroll horizontally. Both also scroll along the other axis when content can't shrink to fit, so nothing is cut off
  out of reach.
- Subclasses add their own items with `add_fit_item`, extend `arrange` for structure that depends on the orientation,
  and override `measure_content` if they move the header. `prepare_fit` and `fit_finished` bracket each plan, for nested
  content that plans itself (`src.ui.layout.panel_fit.FitContent`).
- Call `refit` after a change to the content's size that no resize reports, such as a control appearing.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from PySide6.QtCore import QEvent, QMargins, QSize, Qt
from PySide6.QtGui import QIcon, QResizeEvent
from PySide6.QtWidgets import (QApplication, QBoxLayout, QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from src.ui.layout.panel_fit import (REQUIRED, STRIP_SECTION_MAX_WIDTH, STRIP_SECTION_MIN_WIDTH, FitItem, FitPlanner,
                                     Orientation, Placement, fresh_minimum_size, scroll_extent)
from src.ui.widget.panel_header import PanelHeader
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

    `widget` is the `PanelSection` the panel shows, for summaries, header actions and remembered expansion.
    """

    def __init__(self, title: str) -> None:
        self.title = title
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

        Raises ValueError for a negative priority, or for a required control marked decorative.
        """
        if priority < REQUIRED:
            raise ValueError(f'Invalid priority {priority}')
        if decorative and priority == REQUIRED:
            raise ValueError('A required control is always shown, so it cannot be decorative')
        self._controls.append(_Control(widget, priority, tuple(forms), decorative))
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


@dataclass
class PanelLayout:
    """Collects the sections a `DockPanel` declares in `build`."""
    sections: list[DockSection] = field(default_factory=list)

    def section(self, title: str) -> DockSection:
        """Adds and returns a new section."""
        new_section = DockSection(title)
        self.sections.append(new_section)
        return new_section


class DockPanel(QWidget):
    """A panel that shows as much of its content as fits its dock's size, in the orientation that fits it best."""

    def __init__(self, name: str = '', icon: Optional[QIcon] = None, key_text: str = '',
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # The orientation the panel is arranged in:
        self._orientation = Orientation.SIDE
        self._arranged_orientation: Optional[Orientation] = None
        self._layout_model = PanelLayout()
        self._extra_items: list[tuple[FitItem, Callable[[Optional[int]], None]]] = []
        self._planner: Optional[FitPlanner] = None
        self._header_collapsed = False
        self._scrolls = False
        self._overflow: list[QWidget] = []
        self._footer: Optional[QWidget] = None

        self._header = PanelHeader(name, icon, key_text)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._header)
        # The pinned column sits left of the scroll area, and scrolls vertically on its own:
        self._pinned_content = QWidget()
        self._pinned_layout = QVBoxLayout(self._pinned_content)
        self._pinned_layout.setContentsMargins(0, 0, 0, 0)
        self._pinned_scroll = _PinnedScrollArea()
        self._pinned_scroll.setWidgetResizable(True)
        self._pinned_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._pinned_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._pinned_scroll.setWidget(self._pinned_content)
        self._pinned_column = QWidget()
        self._pinned_column_layout = QVBoxLayout(self._pinned_column)
        self._pinned_column_layout.setContentsMargins(0, 0, 0, 0)
        self._pinned_column_layout.addWidget(self._pinned_scroll, stretch=1)
        self._pinned_column.hide()
        self._scroll_row = QHBoxLayout()
        self._scroll_row.setContentsMargins(0, 0, 0, 0)
        self._scroll_row.addWidget(self._pinned_column)
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

    def build(self, ui: PanelLayout) -> None:
        """Declares sections and controls. Subclasses override it. Called once, from the constructor."""

    def set_footer(self, footer: QWidget) -> None:
        """Pins a widget below the scrolled content, such as a panel's main action. Call it once, from `build` or the
        constructor."""
        if self._footer is not None:
            raise RuntimeError('Tried to set a footer twice')
        self._footer = footer
        self.layout().addWidget(footer)

    @property
    def pinned_layout(self) -> QVBoxLayout:
        """The layout of a column left of the scrolled content, which stays in place while the content scrolls
        sideways. Subclasses fill it in `arrange`, and show it with `set_pinned_visible`.

        The column takes its content's minimum width, and grows toward the content's maximum width while that leaves
        room for one strip column beside it.
        """
        return self._pinned_layout

    def set_pinned_visible(self, visible: bool) -> None:
        """Shows or hides the pinned column. While it shows, the footer sits under it instead of under the scrolled
        content, and the pinned content scrolls vertically above the footer when the panel is too short for it."""
        if self._footer is not None:
            if visible:
                self._pinned_column_layout.addWidget(self._footer)
            else:
                self.layout().addWidget(self._footer)
            self._footer.show()
        self._pinned_column.setVisible(visible)

    @property
    def section_layout(self) -> QBoxLayout:
        """The layout that holds the sections' widgets in order, for `arrange` overrides that move a section out and
        back."""
        return self._section_layout

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

        Items added here fill after the header and before section controls of the same priority, in the order added.
        """
        self._extra_items.append((item, apply))
        self._planner = None

    def set_host_facts(self, size: QSize) -> None:
        """Called by the host when the size the panel fills changes. Plans again if it changed, picking the
        orientation with `src.ui.layout.panel_fit.plan_orientation`."""
        self._fit_planner().update(None, size)

    def plan_in(self, orientation: Orientation, size: QSize) -> None:
        """Plans for `size` in `orientation` alone. Later plans treat it as the arrangement in use, so it holds while
        it fits as well as the other orientation and `size` is within `HYSTERESIS` of a square."""
        self._fit_planner().update(orientation, size)

    def refit(self) -> None:
        """Plans again for the latest size, after the content's own size changed."""
        planner = self._fit_planner()
        available = planner.available
        planner.update(None, available if available is not None else self.size(), force=True)

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:  # pylint: disable=invalid-name
        """Plans for the new size."""
        super().resizeEvent(event)
        self._fit_planner().update(None, self.size())

    def arrange(self, orientation: Orientation) -> None:
        """Lays out structure that depends only on the orientation. Called when it changes, before any placement.

        Overrides should call this and then adjust. No widget is created or destroyed here.
        """
        horizontal = orientation == Orientation.STRIP
        direction = QBoxLayout.Direction.LeftToRight if horizontal else QBoxLayout.Direction.TopToBottom
        self._section_layout.setDirection(direction)
        self._body_layout.setDirection(direction)
        for section in self._layout_model.sections:
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
        """Returns the content's minimum size as currently arranged, from `measure_content`, with room across for the
        scroll bar when the content overflows along the scroll axis.

        A scroll bar narrows the body, so the header is fit to its `header_width` again when that changes.
        """
        need = self.measure_content()
        available = self.available_size
        scrolls = available is not None and scroll_extent(need, self._orientation) > scroll_extent(available,
                                                                                                  self._orientation)
        if scrolls != self._scrolls:
            self._scrolls = scrolls
            self._fit_header_width()
            need = self.measure_content()
        if not scrolls:
            return need
        if self._orientation == Orientation.SIDE:
            return QSize(need.width() + self.scroll_bar_extent(), need.height())
        return QSize(need.width(), need.height() + self.scroll_bar_extent())

    def measure_content(self) -> QSize:
        """Returns the content's minimum size as currently arranged: the header, if shown above the scroll area, over
        the pinned column and scrolled body, over the footer if it is still below them."""
        content = fresh_minimum_size(self._body)
        spacing = max(self.layout().spacing(), 0)
        if not self._pinned_column.isHidden():
            content = self._measure_with_pinned_column(content)
        if not self._header.isHidden() and self._header.parentWidget() is self:
            header = fresh_minimum_size(self._header)
            content = QSize(max(content.width(), header.width()), content.height() + spacing + header.height())
        if self._footer is not None and not self._footer.isHidden() and self._footer.parentWidget() is self:
            footer = fresh_minimum_size(self._footer)
            content = QSize(max(content.width(), footer.width()), content.height() + spacing + footer.height())
        return content

    def _measure_with_pinned_column(self, body: QSize) -> QSize:
        """Returns the size of the pinned column beside the scrolled body, and sets the pinned scroll area's widths.

        The pinned content scrolls on its own, so it adds only the scroll area's minimum height. It gets a scroll bar
        when it is taller than the room it has under the header and over the footer.
        """
        content = fresh_minimum_size(self._pinned_content)
        column_spacing = max(self._pinned_column_layout.spacing(), 0)
        footer = QSize(0, 0)
        if self._footer is not None and not self._footer.isHidden():
            footer = fresh_minimum_size(self._footer)
        width = content.width() + self._pinned_scroll.frameWidth() * 2
        available = self.available_size
        if available is not None:
            room = available.height() - footer.height() - column_spacing
            if not self._header.isHidden() and self._header.parentWidget() is self:
                room -= fresh_minimum_size(self._header).height() + max(self.layout().spacing(), 0)
            if content.height() > room:
                width += self._pinned_scroll.verticalScrollBar().sizeHint().width()
        self._pinned_scroll.setMinimumWidth(width)
        # It prefers its content's maximum width, less room for one strip column beside it:
        row_spacing = max(self._scroll_row.spacing(), 0)
        preferred = self._pinned_content.maximumWidth()
        if available is not None:
            preferred = min(preferred, available.width() - row_spacing - STRIP_SECTION_MIN_WIDTH)
        self._pinned_scroll.set_preferred_width(preferred + width - content.width())
        column = QSize(max(width, footer.width()),
                       self._pinned_scroll.minimumSizeHint().height() + column_spacing + footer.height())
        return QSize(column.width() + row_spacing + body.width(), max(column.height(), body.height()))

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
        offset = 1 + len(self._extra_items)
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

    def _controls(self) -> list[_Control]:
        return [control for section in self._layout_model.sections for control in section.controls]

    def _fit_planner(self) -> FitPlanner:
        if self._planner is None:
            items = [FitItem(REQUIRED, 2), *(item for item, _ in self._extra_items),
                     *(control.item for control in self._controls())]
            self._planner = FitPlanner(items, self._apply_placement, self.measure, self.prepare_fit,
                                       self._plan_finished)
        return self._planner

    def _plan_finished(self, orientation: Orientation) -> None:
        self.fit_finished(orientation)
        # Refresh the cached sizes trials left behind, then have the scroll area re-fit the body to them at once. Its
        # own update waits on a posted layout request, and planning runs after it sized the body for this resize:
        self.measure()
        QApplication.sendEvent(self._scroll, QEvent(QEvent.Type.LayoutRequest))
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
        for control, form in zip(self._controls(), placement[1 + extra_count:]):
            control.form = form
            if form is not None and len(control.forms) > 0:
                control.forms[form]()
        self._overflow = []
        for section in self._layout_model.sections:
            self._overflow.extend(section.place(self._overflow_layout))
        self.finish_placement()
