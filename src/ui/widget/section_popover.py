"""A popover that shows a collapsed `PanelSection`'s body under its header, for panels with no room to expand it.

`DockPanel` and `StrokeToolPanel` each own one. The body returns to its section when the popover hides, so closing it
by any route restores the section.
"""
from typing import Optional

from PySide6.QtWidgets import QWidget

from src.ui.widget.panel_header import PanelPopover
from src.ui.widget.panel_section import PanelSection


class SectionPopover(PanelPopover):
    """A `PanelPopover` hosting one section's detached body at a time."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._section: Optional[PanelSection] = None
        self.closed.connect(self._restore_section)

    @property
    def section(self) -> Optional[PanelSection]:
        """Returns the section whose body the popover holds, if any."""
        return self._section

    def open_section(self, section: PanelSection) -> None:
        """Shows the section's body under its header, after returning any other section's body."""
        self.close_section()
        self._section = section
        self.set_content(section.detach_body())
        self.reposition()

    def reposition(self) -> None:
        """Resizes and moves the popover under its section's header, and shows it. The body can change size while the
        popover is open."""
        if self._section is not None:
            self.popup_below(self._section.header_button, align_left=True)

    def close_section(self) -> None:
        """Hides the popover and returns the body to its section."""
        self.hide()
        self._restore_section()

    def _restore_section(self) -> None:
        section = self._section
        if section is None:
            return
        self._section = None
        self.set_content(None)
        section.restore_body()
