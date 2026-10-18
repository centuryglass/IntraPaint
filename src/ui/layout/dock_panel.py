"""Base class for panels that show as much as fits in the space their host reports.

A `DockPanel` subclass declares sections and a priority for each control in `build`. The host calls `set_host_facts`
when the dock's orientation or size changes, and the panel plans again whenever it is resized. The host's orientation
is a preference: the panel takes whichever orientation its content fits best. Planning
(`src.ui.layout.panel_fit`) moves controls between their sections and the overflow area without rebuilding them, so
their state survives.

- `REQUIRED` controls always stay in their section. An optional control stays while it fits without scrolling, and
  otherwise moves into the popover of the header's "More" button (`PanelHeader`). A `decorative` optional control
  hides instead.
- A control with several forms gets a callback per form, largest first. Planning calls the one for the form that fits.
- The header is a required item. A strip too short for it hides it and moves its More button to the end of the row.
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

from PySide6.QtCore import QEvent, QSize
from PySide6.QtGui import QIcon, QResizeEvent
from PySide6.QtWidgets import (QApplication, QBoxLayout, QFrame, QLabel, QScrollArea, QSizePolicy, QVBoxLayout,
                               QWidget)

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
    """A panel that shows as much of its content as fits its dock's orientation and size."""

    def __init__(self, name: str = '', icon: Optional[QIcon] = None, key_text: str = '',
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # The orientation the host prefers, and the one the panel is arranged in:
        self._preferred_orientation = Orientation.SIDE
        self._orientation = Orientation.SIDE
        self._arranged_orientation: Optional[Orientation] = None
        self._layout_model = PanelLayout()
        self._extra_items: list[tuple[FitItem, Callable[[Optional[int]], None]]] = []
        self._planner: Optional[FitPlanner] = None
        self._header_collapsed = False
        self._scrolls = False
        self._overflow: list[QWidget] = []

        self._header = PanelHeader(name, icon, key_text)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._header)
        outer.addWidget(self._scroll)

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

    @property
    def header(self) -> PanelHeader:
        """The panel's header, which hosts the More button."""
        return self._header

    @property
    def orientation(self) -> Orientation:
        """The orientation the panel is arranged in, which planning picks with the host's as a preference."""
        return self._orientation

    @property
    def preferred_orientation(self) -> Orientation:
        """The orientation from the latest host update."""
        return self._preferred_orientation

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

    def set_host_facts(self, orientation: Orientation, size: QSize) -> None:
        """Called by the host when the dock's orientation or size changes, with the size the panel fills. Plans again
        if either changed. The orientation is a preference: `src.ui.layout.panel_fit.plan_orientation` picks the one
        the content fits best."""
        self._preferred_orientation = orientation
        self._fit_planner().update(orientation, size, flexible=True)

    def refit(self) -> None:
        """Plans again for the latest size, after the content's own size changed."""
        planner = self._fit_planner()
        available = planner.available
        planner.update(self._preferred_orientation, available if available is not None else self.size(), force=True,
                       flexible=True)

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:  # pylint: disable=invalid-name
        """Plans for the new size."""
        super().resizeEvent(event)
        self._fit_planner().update(self._preferred_orientation, self.size(), flexible=True)

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
        the scrolled body."""
        body = fresh_minimum_size(self._body)
        if self._header.isHidden() or self._header.parentWidget() is not self:
            return body
        header = fresh_minimum_size(self._header)
        spacing = max(self.layout().spacing(), 0)
        return QSize(max(body.width(), header.width()), body.height() + spacing + header.height())

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
