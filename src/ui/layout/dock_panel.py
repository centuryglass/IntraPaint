"""Base class for panels that arrange themselves from the host's orientation and size class.

A `DockPanel` subclass declares sections and a priority for each control in `build`. The host calls `set_host_facts`
whenever the dock's orientation or size changes. The panel then moves controls between its sections and the overflow
area without rebuilding them, so their state survives.

- Priority `P1` controls are always shown, `P2` from `SizeClass.REGULAR` up, `P3` only at `SizeClass.WIDE`.
- A control that doesn't fit moves into the "More" area. It is never removed or hidden outright.
- Side panels stack sections in one column and scroll vertically. Strip panels put sections in fixed-width columns and
  scroll horizontally.
- Subclasses override `arrange` for a different arrangement. Call `super().arrange` to keep the default placement.
"""
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (QApplication, QBoxLayout, QFrame, QLabel, QScrollArea, QSizePolicy,
                               QToolButton, QVBoxLayout, QWidget)

from src.ui.layout.panel_size_class import (Orientation, SizeClass, SizeClassTracker,
                                            STRIP_SECTION_MAX_WIDTH, STRIP_SECTION_MIN_WIDTH)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.layout.dock_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


MORE_LABEL = _tr('More')

P1 = 1
P2 = 2
P3 = 3

# The highest priority shown in each size class:
_MAX_VISIBLE_PRIORITY = {SizeClass.COMPACT: P1, SizeClass.REGULAR: P2, SizeClass.WIDE: P3}


def is_shown(priority: int, size_class: SizeClass) -> bool:
    """Returns whether a control with the given priority stays in its section at a size class."""
    return priority <= _MAX_VISIBLE_PRIORITY[size_class]


@dataclass
class _Entry:
    widget: QWidget
    priority: int


class PanelSection:
    """A titled group of controls, each with a priority. Created through `PanelLayout.section`."""

    def __init__(self, title: str) -> None:
        self.title = title
        self.frame = QFrame()
        self.frame.setObjectName('panel_section')
        self._layout = QVBoxLayout(self.frame)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._title_label = QLabel(title)
        self._layout.addWidget(self._title_label)
        # Heading shown above this section's controls while they sit in the "More" area:
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

    def arrange(self, size_class: SizeClass, overflow_layout: QBoxLayout) -> list[QWidget]:
        """Places each control in the section or in the overflow layout by priority, returning the overflowed ones."""
        overflowed = False
        moved: list[QWidget] = []
        for entry in self._entries:
            if is_shown(entry.priority, size_class):
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
        self.frame.setVisible(any(is_shown(e.priority, size_class) for e in self._entries))
        return moved


@dataclass
class PanelLayout:
    """Collects the sections a `DockPanel` declares in `build`."""
    sections: list[PanelSection] = field(default_factory=list)

    def section(self, title: str) -> PanelSection:
        """Adds and returns a new section."""
        new_section = PanelSection(title)
        self.sections.append(new_section)
        return new_section


class DockPanel(QWidget):
    """A panel that arranges its sections for a dock's orientation and size class."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._tracker = SizeClassTracker()
        self._layout_model = PanelLayout()
        self._arranged = False
        self._overflow: list[QWidget] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(self._scroll)
        self._body = QWidget()
        self._body_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self._body)
        self._scroll.setWidget(self._body)

        self._section_holder = QWidget()
        self._section_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self._section_holder)
        self._section_layout.setContentsMargins(0, 0, 0, 0)

        self._more_button = QToolButton()
        self._more_button.setText(MORE_LABEL)
        self._more_button.setCheckable(True)
        self._more_button.toggled.connect(self._update_overflow_visibility)
        self._overflow_area = QFrame()
        self._overflow_area.setObjectName('panel_overflow')
        self._overflow_layout = QVBoxLayout(self._overflow_area)
        self._overflow_layout.setContentsMargins(0, 0, 0, 0)
        self._overflow_area.hide()

        self.build(self._layout_model)
        for section in self._layout_model.sections:
            self._section_layout.addWidget(section.frame)

    def build(self, ui: PanelLayout) -> None:
        """Declares sections and controls. Subclasses override it. Called once, from the constructor."""

    @property
    def orientation(self) -> Orientation:
        """The orientation from the latest host update."""
        return self._tracker.orientation

    @property
    def size_class(self) -> Optional[SizeClass]:
        """The size class from the latest host update, or None before the first one."""
        return self._tracker.size_class

    @property
    def sections(self) -> list[PanelSection]:
        """The sections declared in `build`."""
        return list(self._layout_model.sections)

    @property
    def more_button(self) -> QToolButton:
        """The button that reveals the controls moved out of their sections. Hidden when nothing overflowed."""
        return self._more_button

    @property
    def overflow_widgets(self) -> list[QWidget]:
        """The controls currently in the "More" area."""
        return list(self._overflow)

    def set_host_facts(self, orientation: Orientation, size: QSize) -> None:
        """Called by the host when the dock's orientation or size changes. Re-arranges only if the class changed."""
        changed = self._tracker.update(orientation, size)
        if changed or not self._arranged:
            self._arranged = True
            size_class = self._tracker.size_class
            assert size_class is not None
            self.arrange(orientation, size_class)

    def arrange(self, orientation: Orientation, size_class: SizeClass) -> None:
        """Moves controls between sections and the "More" area, and lays sections out for the orientation.

        Overrides should call this and then adjust. No widget is created or destroyed here.
        """
        horizontal = orientation == Orientation.STRIP
        direction = QBoxLayout.Direction.LeftToRight if horizontal else QBoxLayout.Direction.TopToBottom
        self._section_layout.setDirection(direction)
        self._body_layout.setDirection(direction)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded if horizontal
                                                  else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff if horizontal
                                                else Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        for section in self._layout_model.sections:
            if horizontal:
                section.frame.setMinimumWidth(STRIP_SECTION_MIN_WIDTH)
                section.frame.setMaximumWidth(STRIP_SECTION_MAX_WIDTH)
                section.frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            else:
                section.frame.setMinimumWidth(0)
                section.frame.setMaximumWidth(16777215)
                section.frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        # Re-add the holder, the More button and the overflow area in order:
        for widget in (self._section_holder, self._more_button, self._overflow_area):
            self._body_layout.addWidget(widget)
        self._overflow = []
        for section in self._layout_model.sections:
            self._overflow.extend(section.arrange(size_class, self._overflow_layout))
        self._update_overflow_visibility()

    def _update_overflow_visibility(self) -> None:
        has_overflow = bool(self.overflow_widgets)
        self._more_button.setVisible(has_overflow)
        self._overflow_area.setVisible(has_overflow and self._more_button.isChecked())
