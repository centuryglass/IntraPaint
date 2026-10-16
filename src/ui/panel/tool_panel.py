"""The Tools dock's panel: a grid of tool buttons, a header naming the active tool, and the tool's controls.

- Orientation and size class come from the dock (`DockPanel.set_host_facts`). They pick the button size and grid from
  `BUTTON_LAYOUTS`. Side panels show rows of eight with the header under them, then the controls. Strip panels put
  the header across the top, with the grid left of the controls. A strip grid has three columns when the panel is tall
  enough for them (`strip_button_layout`), and four otherwise.
- Buttons are ordered by `BaseTool.TOOL_GROUP`, keeping the order tools were added within a group, and always line up
  in columns.
- The header names the active tool with its icon, key and description, and its icon is centered over the first
  button column. Side Compact leaves out the description. In Strip Short the header is hidden, a dim line under the
  buttons names the tool, and reset moves into the More popover.
- Reset restores the active tool's `BaseTool.get_reset_config_keys`, and is hidden for a tool that declares none.
- Tool control panels that haven't migrated to `DockPanel` get a `Qt.Orientation` through their `set_orientation`.
"""
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QPalette, QResizeEvent
from PySide6.QtWidgets import QWidget, QLabel, QGridLayout, QVBoxLayout, QSizePolicy, QPushButton

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.tools.base_tool import BaseTool
from src.ui.layout.dock_panel import DockPanel
from src.ui.layout.panel_size_class import Orientation, SizeClass
from src.ui.panel.panel_reset import reset_config_keys
from src.ui.widget.panel_header import RESET_TOOLTIP
from src.ui.widget.shortcut_tooltip import shortcut_tooltip_text
from src.ui.widget.tool_button import ToolButton
from src.util.visual.text_drawing_utils import get_key_display_string

BUTTON_SPACING = 2


@dataclass(frozen=True)
class ButtonLayout:
    """How the tool buttons are laid out: their size, the number of columns, and whether key hints show."""
    edge_length: int
    columns: int
    key_hints: bool = False


BUTTON_LAYOUTS = {
    (Orientation.SIDE, SizeClass.COMPACT): ButtonLayout(22, 8),
    (Orientation.SIDE, SizeClass.REGULAR): ButtonLayout(28, 8),
    (Orientation.SIDE, SizeClass.WIDE): ButtonLayout(40, 8, key_hints=True),
    (Orientation.STRIP, SizeClass.COMPACT): ButtonLayout(22, 8),
    (Orientation.STRIP, SizeClass.REGULAR): ButtonLayout(28, 4),
    (Orientation.STRIP, SizeClass.WIDE): ButtonLayout(28, 4),
}

# Strip grids switch to this many columns when buttons of at least `BUTTON_LAYOUTS`' size fit the height:
STRIP_NARROW_COLUMNS = 3
MAX_STRIP_EDGE_LENGTH = 40
# Strip buttons this large or larger show key hints:
KEY_HINT_MIN_EDGE_LENGTH = 40


def strip_button_layout(button_count: int, grid_height: int, default: ButtonLayout) -> ButtonLayout:
    """Returns the strip grid for a height: `STRIP_NARROW_COLUMNS` columns of buttons as large as fit, up to
    `MAX_STRIP_EDGE_LENGTH`, or `default` if buttons that size would be smaller than the default's."""
    rows = max(1, -(-button_count // STRIP_NARROW_COLUMNS))
    edge = min(MAX_STRIP_EDGE_LENGTH, (grid_height - BUTTON_SPACING * (rows - 1)) // rows)
    if edge < default.edge_length:
        return default
    return ButtonLayout(edge, STRIP_NARROW_COLUMNS, key_hints=edge >= KEY_HINT_MIN_EDGE_LENGTH)


class ToolPanel(DockPanel):
    """Provides buttons to select between tools and shows the active tool's control panel."""

    tool_selected = Signal(QObject)

    def __init__(self) -> None:
        super().__init__()
        self._tool_widgets: dict[str, ToolButton] = {}
        self._active_tool: Optional[BaseTool] = None
        self._active_tool_panel: Optional[QWidget] = None
        self._layout_key = (Orientation.SIDE, SizeClass.REGULAR)

        self._button_layout = BUTTON_LAYOUTS[self._layout_key]

        self._strip_column = QWidget()
        strip_column_layout = QVBoxLayout(self._strip_column)
        strip_column_layout.setContentsMargins(0, 0, 0, 0)
        strip_column_layout.setSpacing(BUTTON_SPACING)
        self._button_grid = QWidget()
        self._button_grid_layout = QGridLayout(self._button_grid)
        self._button_grid_layout.setContentsMargins(0, 0, 0, 0)
        self._button_grid_layout.setSpacing(BUTTON_SPACING)
        self._button_grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        strip_column_layout.addWidget(self._button_grid)
        # Names the active tool in Strip Short, where the header is hidden:
        self._short_label = QLabel()
        self._short_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self._short_label.hide()
        strip_column_layout.addWidget(self._short_label)
        strip_column_layout.addStretch()

        self._tool_control_box = QWidget()
        self._tool_control_layout = QVBoxLayout(self._tool_control_box)
        self._tool_control_layout.setContentsMargins(0, 0, 0, 0)
        # Tool control panels that haven't migrated to `DockPanel` don't widen the panel, so they squeeze to fit it:
        self._tool_control_box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)

        # The header moves into the scrolled body, so it shares the button grid's margins:
        self.layout().removeWidget(self.header)
        self._content = QWidget()
        self._content_layout = QGridLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.insertWidget(0, self._content, stretch=1)

        # In Strip Short, the More popover holds the reset button:
        self._short_popover_content = QWidget()
        short_popover_layout = QVBoxLayout(self._short_popover_content)
        short_popover_layout.setContentsMargins(0, 0, 0, 0)
        self._short_reset_button = QPushButton(RESET_TOOLTIP)
        self._short_reset_button.setFlat(True)
        short_popover_layout.addWidget(self._short_reset_button)

        self.header.reset_requested.connect(self.reset_active_tool)
        self._short_reset_button.clicked.connect(self._reset_from_popover)
        self.arrange(*self._layout_key)

    @property
    def active_tool(self) -> Optional[BaseTool]:
        """The tool shown in the header, or None if no tool is active."""
        return self._active_tool

    @property
    def tool_buttons(self) -> list[ToolButton]:
        """The tool buttons, in the order the panel shows them."""
        return sorted(self._tool_widgets.values(), key=lambda button: button.connected_tool.TOOL_GROUP)

    def add_tool_button(self, tool: BaseTool) -> None:
        """Creates and shows a new tool button for a given tool object."""
        if tool.label in self._tool_widgets:
            return
        button = ToolButton(tool)
        self._tool_widgets[tool.label] = button
        button.tool_selected.connect(self.tool_selected)
        button.is_active = tool is self._active_tool
        self._build_button_rows()

    def remove_tool_button(self, tool: BaseTool) -> None:
        """Removes a tool button from the panel."""
        button = self._tool_widgets.pop(tool.label, None)
        if button is None:
            return
        button.hide()
        button.setParent(None)
        self._build_button_rows()

    def setup_active_tool(self, active_tool: Optional[QObject]) -> None:
        """Shows a new active tool's name, key and control panel."""
        assert active_tool is None or isinstance(active_tool, BaseTool)
        if self._active_tool is not None:
            KeyConfig().disconnect(self, self._active_tool.get_activation_config_key())
        if self._active_tool_panel is not None:
            self._tool_control_layout.removeWidget(self._active_tool_panel)
            self._active_tool_panel.hide()
            self._active_tool_panel.setParent(None)
            self._active_tool_panel = None
        self._active_tool = active_tool
        for label, button in self._tool_widgets.items():
            button.is_active = active_tool is not None and label == active_tool.label
        if active_tool is not None:
            KeyConfig().connect(self, active_tool.get_activation_config_key(), lambda _keys: self._update_tool_text())
            tool_panel = active_tool.get_control_panel()
            if tool_panel is not None:
                tool_panel.setToolTip(active_tool.get_tooltip_text())
                self._active_tool_panel = tool_panel
                self._tool_control_layout.addWidget(tool_panel)
                self._forward_orientation()
                tool_panel.show()
        self._update_tool_text()
        self._update_reset_controls()
        self.updateGeometry()

    def reset_active_tool(self) -> bool:
        """Restores the active tool's reset keys to their defaults, returning whether any value changed."""
        if self._active_tool is None:
            return False
        return reset_config_keys(Cache(), self._active_tool.get_reset_config_keys())

    def arrange(self, orientation: Orientation, size_class: SizeClass) -> None:
        """Lays out the buttons, header and controls for the orientation and size class."""
        super().arrange(orientation, size_class)
        self._layout_key = (orientation, size_class)
        for widget in (self._strip_column, self.header, self._tool_control_box):
            self._content_layout.removeWidget(widget)
        for index in range(3):
            self._content_layout.setRowStretch(index, 0)
            self._content_layout.setColumnStretch(index, 0)
        if orientation == Orientation.SIDE:
            self._strip_column.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            self._content_layout.addWidget(self._strip_column, 0, 0)
            self._content_layout.addWidget(self.header, 1, 0)
            self._content_layout.addWidget(self._tool_control_box, 2, 0)
            self._content_layout.setRowStretch(2, 1)
        else:
            self._strip_column.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            self._content_layout.addWidget(self.header, 0, 0, 1, 2)
            self._content_layout.addWidget(self._strip_column, 1, 0)
            self._content_layout.addWidget(self._tool_control_box, 1, 1)
            self._content_layout.setRowStretch(1, 1)
            self._content_layout.setColumnStretch(1, 1)
        self._button_layout = self._current_button_layout()
        self._build_button_rows()
        self._forward_orientation()
        self._update_tool_text()
        self._update_reset_controls()

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Re-fits a strip's button grid to the new height."""
        super().resizeEvent(event)
        button_layout = self._current_button_layout()
        if button_layout != self._button_layout:
            self._button_layout = button_layout
            self._build_button_rows()

    def _current_button_layout(self) -> ButtonLayout:
        """Returns the button layout for the size class, fitted to the height in Strip Regular and Strip Tall."""
        default = BUTTON_LAYOUTS[self._layout_key]
        if self._layout_key[0] == Orientation.SIDE or self._is_strip_short():
            return default
        margins = self._body_layout.contentsMargins()
        grid_height = (self.height() - margins.top() - margins.bottom() - self.header.sizeHint().height()
                       - self._content_layout.verticalSpacing())
        return strip_button_layout(len(self._tool_widgets), grid_height, default)

    def _is_strip_short(self) -> bool:
        return self._layout_key == (Orientation.STRIP, SizeClass.COMPACT)

    def _forward_orientation(self) -> None:
        """Passes the orientation to an active tool panel that hasn't migrated to `DockPanel`."""
        if self._active_tool_panel is not None and hasattr(self._active_tool_panel, 'set_orientation'):
            orientation = self._layout_key[0]
            self._active_tool_panel.set_orientation(Qt.Orientation.Vertical if orientation == Orientation.SIDE
                                                    else Qt.Orientation.Horizontal)

    def _update_tool_text(self) -> None:
        """Shows the active tool's name and key in the header, or in the dim line in Strip Short."""
        tool = self._active_tool
        if tool is None:
            self.header.set_name('')
            self.header.set_key_text('')
            self.header.set_description('')
            self._short_label.setText('')
            self._short_label.hide()
            return
        keys = KeyConfig().get(tool.get_activation_config_key())
        self.header.set_name(tool.label, tool.get_icon())
        self.header.set_key_text(get_key_display_string(keys, rich_text=False) if keys != '' else '')
        show_description = self._layout_key != (Orientation.SIDE, SizeClass.COMPACT) and not self._is_strip_short()
        self.header.set_description(tool.get_tooltip_text() if show_description else '')
        self._short_label.setText(shortcut_tooltip_text(tool.label, keys))
        self._short_label.setVisible(self._is_strip_short())

    def _update_reset_controls(self) -> None:
        """Shows reset in the header, or in the More popover in Strip Short, if the active tool has reset keys."""
        can_reset = self._active_tool is not None and len(self._active_tool.get_reset_config_keys()) > 0
        self.header.reset_button.setVisible(can_reset)
        if self._is_strip_short():
            self.header.set_popover_content(self._short_popover_content if can_reset else None)
            # Reparenting hides a widget:
            self.header.more_button.setVisible(can_reset)

    def _reset_from_popover(self) -> None:
        self.header.popover.hide()
        self.reset_active_tool()

    def _build_button_rows(self) -> None:
        """Places the buttons in a grid for the current layout, starting a new row every `ButtonLayout.columns`."""
        layout = self._button_layout
        while self._button_grid_layout.count() > 0:
            self._button_grid_layout.takeAt(0)
        for index, button in enumerate(self.tool_buttons):
            button.set_edge_length(layout.edge_length, layout.key_hints)
            self._button_grid_layout.addWidget(button, index // layout.columns, index % layout.columns)
            button.show()
        self.header.set_icon_width(layout.edge_length)
