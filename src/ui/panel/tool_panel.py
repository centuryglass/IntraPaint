"""The Tools dock's panel: a grid of tool buttons, a header naming the active tool, and the tool's controls.

- Orientation and size come from the dock (`DockPanel.set_host_facts`), and the panel shows as much as fits
  (`src.ui.layout.panel_fit`). Side panels show rows of eight buttons with the header under them, then the controls.
  Strip panels put the header across the top, with the grid left of the controls.
- The buttons take the largest of `SIDE_BUTTON_FORMS` or `STRIP_BUTTON_FORMS` that fits across the panel. The largest
  strip form is a grid of `STRIP_MAX_COLUMNS` columns, with buttons as tall as the height allows
  (`strip_button_layout`). It uses `STRIP_NARROW_COLUMNS` columns when the height holds them at the same button size.
- Buttons are ordered by `BaseTool.TOOL_GROUP`, keeping the order tools were added within a group, and always line up
  in columns.
- The header names the active tool with its icon, key and description, and its icon is centered over the first
  button column. The description shows when it fits. A strip too short for the header hides it, a dim line under the
  buttons names the tool, and the More button moves to the end of the buttons' column.
- The More popover holds reset and shortcuts to the settings tabs for the tool's key bindings and, once a tablet has
  been seen, the pen pressure curve. `settings_requested` carries the tab name for the controller to show. Controls a
  `FitContent` tool control panel leaves out go above them.
- Reset restores the active tool's `BaseTool.get_reset_config_keys`, and is hidden for a tool that declares none.
- A tool control panel that is a `FitContent` is measured at its base size while the panel plans, then gets the space
  beside the buttons and under the header. Other tool control panels are left out of planning, and get a
  `Qt.Orientation` through their `set_orientation`.
"""
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QGridLayout, QVBoxLayout, QSizePolicy, QPushButton

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.tools.base_tool import BaseTool
from src.ui.layout.dock_panel import DockPanel
from src.ui.layout.panel_fit import REQUIRED, FitContent, FitItem, Orientation, fresh_minimum_size
from src.ui.panel.panel_reset import reset_config_keys
from src.ui.widget.panel_header import RESET_TOOLTIP
from src.ui.widget.shortcut_tooltip import shortcut_tooltip_text
from src.ui.widget.tool_button import ToolButton
from src.util.visual.text_drawing_utils import get_key_display_string

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


KEY_BINDINGS_LABEL = _tr('Key bindings...')
PRESSURE_CURVE_LABEL = _tr('Pressure curve...')

BUTTON_SPACING = 2


@dataclass(frozen=True)
class ButtonLayout:
    """How the tool buttons are laid out: their size, the number of columns, and whether key hints show."""
    edge_length: int
    columns: int
    key_hints: bool = False


# The button forms, largest first:
SIDE_BUTTON_FORMS = (ButtonLayout(40, 8, key_hints=True), ButtonLayout(28, 8), ButtonLayout(22, 8))
STRIP_BUTTON_FORMS = (ButtonLayout(28, 4), ButtonLayout(28, 4), ButtonLayout(22, 8))
# The largest strip form fits buttons of at least its `STRIP_BUTTON_FORMS` size into `STRIP_MAX_COLUMNS` columns, or
# into `STRIP_NARROW_COLUMNS` if the buttons stay the same size:
STRIP_NARROW_COLUMNS = 2
STRIP_MAX_COLUMNS = 3
MAX_STRIP_EDGE_LENGTH = 40
# Strip buttons this large or larger show key hints:
KEY_HINT_MIN_EDGE_LENGTH = 40
# The header description is optional, placed before any later optional item:
DESCRIPTION_PRIORITY = 1


def strip_button_layout(button_count: int, grid_height: int, default: ButtonLayout) -> ButtonLayout:
    """Returns the strip grid for a height: `STRIP_MAX_COLUMNS` columns of buttons as large as fit, up to
    `MAX_STRIP_EDGE_LENGTH`, or `default` if buttons that size would be smaller than the default's. Uses
    `STRIP_NARROW_COLUMNS` columns instead when the height holds them at that same button size."""
    def fitted_edge(columns: int) -> int:
        rows = max(1, -(-button_count // columns))
        return min(MAX_STRIP_EDGE_LENGTH, (grid_height - BUTTON_SPACING * (rows - 1)) // rows)

    edge = fitted_edge(STRIP_MAX_COLUMNS)
    if edge < default.edge_length:
        return default
    columns = STRIP_NARROW_COLUMNS if fitted_edge(STRIP_NARROW_COLUMNS) >= edge else STRIP_MAX_COLUMNS
    return ButtonLayout(edge, columns, key_hints=edge >= KEY_HINT_MIN_EDGE_LENGTH)


def button_grid_size(button_count: int, layout: ButtonLayout) -> QSize:
    """Returns the size of a grid of `button_count` buttons in `layout`."""
    if button_count == 0:
        return QSize(0, 0)
    columns = min(layout.columns, button_count)
    rows = -(-button_count // layout.columns)
    return QSize(columns * layout.edge_length + (columns - 1) * BUTTON_SPACING,
                 rows * layout.edge_length + (rows - 1) * BUTTON_SPACING)


class ToolPanel(DockPanel):
    """Provides buttons to select between tools and shows the active tool's control panel."""

    tool_selected = Signal(QObject)
    # The name of the settings tab to show:
    settings_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._tool_widgets: dict[str, ToolButton] = {}
        self._active_tool: Optional[BaseTool] = None
        self._active_tool_panel: Optional[QWidget] = None
        self._button_form = 1
        self._button_layout = SIDE_BUTTON_FORMS[self._button_form]
        # The layout the buttons were last placed in:
        self._built_layout: Optional[ButtonLayout] = None
        self._show_description = True

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
        # Names the active tool while the header is collapsed:
        self._short_label = QLabel()
        self._short_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self._short_label.hide()
        strip_column_layout.addWidget(self._short_label)
        strip_column_layout.addStretch()

        self._tool_control_box = QWidget()
        self._tool_control_layout = QVBoxLayout(self._tool_control_box)
        self._tool_control_layout.setContentsMargins(0, 0, 0, 0)
        self._update_tool_control_policy()

        # The header moves into the scrolled body, so it shares the button grid's margins:
        self.layout().removeWidget(self.header)
        self._content = QWidget()
        self._content_layout = QGridLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.insertWidget(0, self._content, stretch=1)

        # The More popover holds reset and shortcuts to the settings that affect the active tool:
        self._more_content = QWidget()
        more_layout = QVBoxLayout(self._more_content)
        more_layout.setContentsMargins(0, 0, 0, 0)
        self._more_layout = more_layout
        self._more_reset_button = self._add_more_button(RESET_TOOLTIP, more_layout)
        self._more_keys_button = self._add_more_button(KEY_BINDINGS_LABEL, more_layout)
        self._more_pressure_button = self._add_more_button(PRESSURE_CURVE_LABEL, more_layout)

        self.header.reset_requested.connect(self.reset_active_tool)
        self.header.more_requested.connect(self._refresh_more_content)
        self._more_reset_button.clicked.connect(self._reset_from_popover)
        self._more_keys_button.clicked.connect(self._show_key_settings)
        self._more_pressure_button.clicked.connect(self._show_pressure_settings)
        self.add_fit_item(FitItem(REQUIRED, len(SIDE_BUTTON_FORMS)), self._apply_button_form)
        self.add_fit_item(FitItem(DESCRIPTION_PRIORITY), self._apply_description_form)
        self.arrange(Orientation.SIDE)

    @property
    def active_tool(self) -> Optional[BaseTool]:
        """The tool shown in the header, or None if no tool is active."""
        return self._active_tool

    @property
    def tool_buttons(self) -> list[ToolButton]:
        """The tool buttons, in the order the panel shows them."""
        return sorted(self._tool_widgets.values(), key=lambda button: button.connected_tool.TOOL_GROUP)

    @property
    def button_layout(self) -> ButtonLayout:
        """The tool buttons' current layout."""
        return self._button_layout

    def add_tool_button(self, tool: BaseTool) -> None:
        """Creates and shows a new tool button for a given tool object."""
        if tool.label in self._tool_widgets:
            return
        button = ToolButton(tool)
        self._tool_widgets[tool.label] = button
        button.tool_selected.connect(self.tool_selected)
        button.is_active = tool is self._active_tool
        self._build_button_rows()
        self.refit()

    def remove_tool_button(self, tool: BaseTool) -> None:
        """Removes a tool button from the panel."""
        button = self._tool_widgets.pop(tool.label, None)
        if button is None:
            return
        button.hide()
        button.setParent(None)
        self._build_button_rows()
        self.refit()

    def setup_active_tool(self, active_tool: Optional[QObject]) -> None:
        """Shows a new active tool's name, key and control panel."""
        assert active_tool is None or isinstance(active_tool, BaseTool)
        if self._active_tool is not None:
            KeyConfig().disconnect(self, self._active_tool.get_activation_config_key())
        if self._active_tool_panel is not None:
            if isinstance(self._active_tool_panel, FitContent):
                overflow = self._active_tool_panel.overflow_content()
                self._more_layout.removeWidget(overflow)
                overflow.hide()
                overflow.setParent(None)
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
                if isinstance(tool_panel, FitContent):
                    self._more_layout.insertWidget(0, tool_panel.overflow_content())
                self._update_tool_control_policy()
                self._forward_orientation()
                tool_panel.show()
        self._update_tool_text()
        # Before the plan, so it measures the header with the More button the plan will leave:
        self._update_reset_controls()
        self.refit()
        self.updateGeometry()

    def reset_active_tool(self) -> bool:
        """Restores the active tool's reset keys to their defaults, returning whether any value changed."""
        if self._active_tool is None:
            return False
        return reset_config_keys(Cache(), self._active_tool.get_reset_config_keys())

    def arrange(self, orientation: Orientation) -> None:
        """Places the buttons, header and controls for the orientation."""
        super().arrange(orientation)
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
        self._forward_orientation()

    def header_width(self, available: QSize) -> int:
        """Returns the available width less the body's margins, which the header spans in both orientations, and less
        the scroll bar while a side panel scrolls."""
        margins = self._body_layout.contentsMargins()
        width = available.width() - margins.left() - margins.right()
        if self.content_scrolls and self.orientation == Orientation.SIDE:
            width -= self.scroll_bar_extent()
        return width

    def apply_header_form(self, collapsed: bool) -> None:
        """Shows the header, or a dim line under the buttons naming the tool while it is collapsed."""
        super().apply_header_form(collapsed)
        self._update_tool_text()

    def finish_placement(self) -> None:
        """Puts reset in the header, or in the More popover while the header is collapsed."""
        super().finish_placement()
        self._update_reset_controls()

    def prepare_fit(self, orientation: Orientation) -> None:
        """Measures a `FitContent` tool control panel at its base size while the panel plans, and leaves any other
        tool control panel out of the measurements."""
        if isinstance(self._active_tool_panel, FitContent):
            self._active_tool_panel.fit_base_size(orientation)
        else:
            self._tool_control_box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

    def _update_tool_control_policy(self) -> None:
        """Lets a `FitContent` tool control panel's planned width count, so the panel scrolls or changes orientation
        when it doesn't fit. Other tool control panels don't widen the panel, so they squeeze to fit it."""
        width_policy = QSizePolicy.Policy.Preferred if isinstance(self._active_tool_panel, FitContent) \
            else QSizePolicy.Policy.Ignored
        self._tool_control_box.setSizePolicy(width_policy, QSizePolicy.Policy.Expanding)

    def fit_finished(self, orientation: Orientation) -> None:
        """Lays out the buttons for the chosen form, and gives a `FitContent` tool control panel the space beside the
        buttons and under the header."""
        if self._built_layout != self._button_layout:
            self._build_button_rows()
        self._update_tool_control_policy()
        if isinstance(self._active_tool_panel, FitContent):
            self._active_tool_panel.set_fit_space(orientation, self.tool_control_space())

    def tool_control_space(self) -> QSize:
        """Returns the space the tool control panel gets in the latest plan: the available size less the margins, any
        scroll bar, the button column and the header."""
        available = self.available_size if self.available_size is not None else self.size()
        fresh_minimum_size(self._content)
        margins = self._body_layout.contentsMargins()
        width = available.width() - margins.left() - margins.right()
        height = available.height() - margins.top() - margins.bottom()
        if self.content_scrolls:
            if self.orientation == Orientation.SIDE:
                width -= self.scroll_bar_extent()
            else:
                height -= self.scroll_bar_extent()
        header_height = 0 if self.header.isHidden() \
            else self.header.minimumSizeHint().height() + self._content_layout.verticalSpacing()
        column = self._strip_column.sizeHint()
        if self.orientation == Orientation.SIDE:
            height -= column.height() + self._content_layout.verticalSpacing() + header_height
        else:
            width -= column.width() + self._content_layout.horizontalSpacing()
            height -= header_height
        return QSize(max(width, 0), max(height, 0))

    def _apply_button_form(self, form: Optional[int]) -> None:
        """Sizes the button grid for a form. Resizing every button for each trial is slow, so `fit_finished` lays the
        buttons out once planning is done."""
        assert form is not None
        self._button_form = form
        self._button_layout = self._current_button_layout()
        self._button_grid.setFixedSize(button_grid_size(len(self._tool_widgets), self._button_layout))
        self.header.set_icon_width(self._button_layout.edge_length)

    def _apply_description_form(self, form: Optional[int]) -> None:
        self._show_description = form is not None
        self._update_tool_text()

    def _current_button_layout(self) -> ButtonLayout:
        """Returns the layout for the button form, with the largest strip form fitted to the available height."""
        if self.orientation == Orientation.SIDE:
            return SIDE_BUTTON_FORMS[self._button_form]
        default = STRIP_BUTTON_FORMS[self._button_form]
        if self._button_form != 0:
            return default
        available = self.available_size if self.available_size is not None else self.size()
        margins = self._body_layout.contentsMargins()
        grid_height = available.height() - margins.top() - margins.bottom()
        if not self.header.isHidden():
            grid_height -= self.header.minimumSizeHint().height() + self._content_layout.verticalSpacing()
        return strip_button_layout(len(self._tool_widgets), grid_height, default)

    def _forward_orientation(self) -> None:
        """Passes the orientation to an active tool panel that doesn't plan its own layout."""
        panel = self._active_tool_panel
        if panel is not None and not isinstance(panel, FitContent) and hasattr(panel, 'set_orientation'):
            panel.set_orientation(Qt.Orientation.Vertical if self.orientation == Orientation.SIDE
                                  else Qt.Orientation.Horizontal)

    def _update_tool_text(self) -> None:
        """Shows the active tool's name and key in the header, or in the dim line while the header is collapsed."""
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
        self.header.set_description(tool.get_tooltip_text() if self._show_description else '')
        self._short_label.setText(shortcut_tooltip_text(tool.label, keys))
        self._short_label.setVisible(self.header_collapsed)

    def more_content(self) -> Optional[QWidget]:
        """Returns the popover content while a tool is active."""
        return self._more_content if self._active_tool is not None else None

    def _update_reset_controls(self) -> None:
        """Shows reset in the header if the active tool has reset keys, and the More button while a tool is active."""
        can_reset = self._active_tool is not None and len(self._active_tool.get_reset_config_keys()) > 0
        self.header.reset_button.setVisible(can_reset)
        content = self.more_content()
        self.header.set_popover_content(content)
        # Reparenting hides a widget:
        self.header.more_button.setVisible(content is not None)

    @staticmethod
    def _add_more_button(text: str, layout: QVBoxLayout) -> QPushButton:
        button = QPushButton(text)
        button.setFlat(True)
        layout.addWidget(button)
        return button

    def _refresh_more_content(self) -> None:
        """Shows the popover entries that apply to the active tool now, with any controls its panel left out first."""
        tool = self._active_tool
        if isinstance(self._active_tool_panel, FitContent):
            overflow = self._active_tool_panel.overflow_content()
            overflow.setVisible(any(not child.isHidden() for child in overflow.findChildren(
                QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly)))
        self._more_reset_button.setVisible(tool is not None and len(tool.get_reset_config_keys()) > 0)
        self._more_keys_button.setVisible(tool is not None)
        self._more_pressure_button.setVisible(bool(Cache().get(Cache.EXPECT_TABLET_INPUT)))

    def _show_key_settings(self) -> None:
        self.header.popover.hide()
        if self._active_tool is not None:
            self.settings_requested.emit(KeyConfig().get_category(self._active_tool.get_activation_config_key()))

    def _show_pressure_settings(self) -> None:
        self.header.popover.hide()
        self.settings_requested.emit(AppConfig().get_category(AppConfig.TABLET_PRESSURE_CURVE))

    def _reset_from_popover(self) -> None:
        self.header.popover.hide()
        self.reset_active_tool()

    def _build_button_rows(self) -> None:
        """Places the buttons in a grid for the current layout, starting a new row every `ButtonLayout.columns`."""
        layout = self._button_layout
        self._built_layout = layout
        self._button_grid.setFixedSize(button_grid_size(len(self._tool_widgets), layout))
        while self._button_grid_layout.count() > 0:
            self._button_grid_layout.takeAt(0)
        for index, button in enumerate(self.tool_buttons):
            button.set_edge_length(layout.edge_length, layout.key_hints)
            self._button_grid_layout.addWidget(button, index // layout.columns, index % layout.columns)
            button.show()
        self.header.set_icon_width(layout.edge_length)
