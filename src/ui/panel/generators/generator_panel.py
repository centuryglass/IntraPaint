"""Base classes for image generator panels: `GeneratorPanel` marks a widget as a generator control panel, and
`GenerateFooterPanel` is the `DockPanel` with a pinned Generate button that the GLID and test panels share."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from src.ui.ink_style import set_primary_button
from src.ui.layout.bordered_widget import BorderedWidget
from src.ui.layout.dock_panel import DockPanel
from src.ui.layout.panel_fit import Orientation
from src.util.shared_constants import BUTTON_TEXT_GENERATE, BUTTON_TOOLTIP_GENERATE

# The widest the Generate column of a strip grows:
TRAILING_COLUMN_MAX_WIDTH = 240


class GeneratorPanel(BorderedWidget):
    """Parent class of all image generator panel widgets. Provides no functionality, its only purpose is to provide an
       easy way to identify a widget as a generator control panel."""


class GenerateFooterPanel(DockPanel):
    """A `DockPanel` whose primary Generate button stays pinned: in the footer of a side panel, and as the trailing
    column of a strip, so it never scrolls.

    Subclasses declare their sections in `build`. The button emits `generate_signal`.
    """

    generate_signal = Signal()

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self._generate_button = QPushButton(BUTTON_TEXT_GENERATE)
        self._generate_button.setToolTip(BUTTON_TOOLTIP_GENERATE)
        set_primary_button(self._generate_button)
        self._generate_button.clicked.connect(self.generate_signal)
        self._footer_holder = QWidget()
        footer_layout = QVBoxLayout(self._footer_holder)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.addWidget(self._generate_button)
        self.set_footer(self._footer_holder)
        self.set_trailing_scrolls(False)

    def arrange(self, orientation: Orientation) -> None:
        """Moves Generate between the footer and the strip's trailing column."""
        super().arrange(orientation)
        strip = orientation == Orientation.STRIP
        if strip:
            self.trailing_layout.addWidget(self._generate_button)
            self.trailing_layout.parentWidget().setMaximumWidth(TRAILING_COLUMN_MAX_WIDTH)
        else:
            self._footer_holder.layout().addWidget(self._generate_button)
        # Reparenting hides a widget:
        self._generate_button.show()
        self._footer_holder.setVisible(not strip)
        self.set_trailing_visible(strip)

    @property
    def generate_button(self) -> QPushButton:
        """The Generate button."""
        return self._generate_button
