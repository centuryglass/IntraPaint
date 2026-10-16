"""Base class for panels that arrange themselves from the host's orientation and grid size.

A `DockPanel` subclass declares sections and a priority for each control in `build`. The host calls `set_host_facts`
whenever the dock's orientation or size changes. The panel then moves controls between its sections and the overflow
area without rebuilding them, so their state survives.

- Priority `P1` controls are always shown, `P2` from 2 cells along the constrained axis (`GridSize.constrained`), and
  `P3` only at 3.
- A control that doesn't fit moves into the popover of the header's "More" button (`PanelHeader`). It is never removed
  or hidden outright. In a strip one row tall ("Short") the header is hidden and its More button moves to the end of
  the row.
- Each section is a `src.ui.widget.panel_section.PanelSection`, available as `DockSection.widget` for summaries,
  header actions and remembered expansion.
- Side panels stack sections in one column and scroll vertically. Strip panels put sections in fixed-width columns and
  scroll horizontally. Both also scroll along the other axis when content can't shrink to fit, so nothing is cut off
  out of reach.
- Subclasses override `arrange` for a different arrangement. Call `super().arrange` to keep the default placement.
"""
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QBoxLayout, QFrame, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from src.ui.layout.panel_size_class import (GridSize, GridSizeTracker, Orientation, STRIP_SECTION_MAX_WIDTH,
                                            STRIP_SECTION_MIN_WIDTH)
from src.ui.widget.panel_header import PanelHeader
from src.ui.widget.panel_section import PanelSection

P1 = 1
P2 = 2
P3 = 3

QWIDGETSIZE_MAX = 16777215


def is_shown(priority: int, constrained_cells: int) -> bool:
    """Returns whether a control with the given priority stays in its section with this many cells along the panel's
    constrained axis."""
    return priority <= constrained_cells


def is_strip_short(orientation: Orientation, grid_size: GridSize) -> bool:
    """Returns whether a panel is a strip one row tall, where headers give their room to content."""
    return orientation == Orientation.STRIP and grid_size.rows == 1


@dataclass
class _Entry:
    widget: QWidget
    priority: int


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
        self._entries: list[_Entry] = []

    @property
    def widgets(self) -> list[QWidget]:
        """All controls added to the section, in order."""
        return [entry.widget for entry in self._entries]

    def add(self, widget: QWidget, priority: int = P1) -> None:
        """Adds a control. Raises ValueError for a priority other than `P1`, `P2` or `P3`."""
        if priority not in (P1, P2, P3):
            raise ValueError(f'Invalid priority {priority}')
        self._entries.append(_Entry(widget, priority))
        self._layout.addWidget(widget)

    def arrange(self, constrained_cells: int, overflow_layout: QBoxLayout) -> list[QWidget]:
        """Places each control in the section or in the overflow layout by priority, returning the overflowed ones."""
        overflowed = False
        moved: list[QWidget] = []
        for entry in self._entries:
            if is_shown(entry.priority, constrained_cells):
                self._layout.addWidget(entry.widget)
            else:
                if not overflowed:
                    overflow_layout.addWidget(self.overflow_title)
                    self.overflow_title.show()
                    overflowed = True
                overflow_layout.addWidget(entry.widget)
                moved.append(entry.widget)
            entry.widget.show()
        if not overflowed:
            self.overflow_title.hide()
        self.widget.setVisible(any(is_shown(e.priority, constrained_cells) for e in self._entries))
        return moved


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
    """A panel that arranges its sections for a dock's orientation and grid size."""

    def __init__(self, name: str = '', icon: Optional[QIcon] = None, key_text: str = '',
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._orientation = Orientation.SIDE
        self._tracker = GridSizeTracker()
        self._layout_model = PanelLayout()
        self._arranged = False
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
        """The orientation from the latest host update."""
        return self._orientation

    @property
    def grid_size(self) -> Optional[GridSize]:
        """The grid size from the latest host update, or None before the first one."""
        return self._tracker.grid_size

    @property
    def sections(self) -> list[DockSection]:
        """The sections declared in `build`."""
        return list(self._layout_model.sections)

    @property
    def overflow_widgets(self) -> list[QWidget]:
        """The controls currently in the More popover's content."""
        return list(self._overflow)

    def set_host_facts(self, orientation: Orientation, size: QSize) -> None:
        """Called by the host when the dock's orientation or size changes. Re-arranges only if the orientation or grid
        size changed."""
        changed = self._tracker.update(size) or orientation != self._orientation
        self._orientation = orientation
        if changed or not self._arranged:
            self._arranged = True
            grid_size = self._tracker.grid_size
            assert grid_size is not None
            self.arrange(orientation, grid_size)

    def arrange(self, orientation: Orientation, grid_size: GridSize) -> None:
        """Moves controls between sections and the More popover, and lays sections out for the orientation.

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
        self._overflow = []
        for section in self._layout_model.sections:
            self._overflow.extend(section.arrange(grid_size.constrained(orientation), self._overflow_layout))
        self._header.set_popover_content(self._overflow_content if self._overflow else None)
        self._place_header(is_strip_short(orientation, grid_size))

    def _place_header(self, strip_short: bool) -> None:
        """In Strip Short, hides the header and moves its More button to the end of the row. Otherwise restores both."""
        more_button = self._header.more_button
        self._header.setVisible(not strip_short)
        if strip_short:
            self._body_layout.addWidget(more_button)
        else:
            self._header.restore_more_button()
        # Reparenting hides a widget:
        more_button.setVisible(bool(self._overflow))
