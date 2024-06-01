"""Selects between image editing tools, and controls their settings."""
from typing import Optional, Dict, Callable

from PyQt5.QtCore import Qt, pyqtSignal, QRect, QSize
from PyQt5.QtGui import QMouseEvent, QPaintEvent, QPainter, QPen, QResizeEvent, QKeySequence
from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, QStackedLayout, QPushButton

from src.config.application_config import AppConfig
from src.image.layer_stack import LayerStack
from src.tools.base_tool import BaseTool
from src.tools.brush_tool import BrushTool
from src.tools.eyedropper_tool import EyedropperTool
from src.tools.mask_tool import MaskTool
from src.tools.selection_tool import SelectionTool
from src.tools.tool_event_handler import ToolEventHandler
from src.ui.image_viewer import ImageViewer
from src.ui.panel.layer_panel import LayerPanel
from src.ui.util.get_scaled_placement import get_scaled_placement
from src.ui.widget.bordered_widget import BorderedWidget
from src.ui.widget.collapsible_box import CollapsibleBox

TOOL_PANEL_TITLE = "Tools"
LIST_SPACING = 10
GENERATE_BUTTON_TEXT = 'Generate'


class ToolPanel(BorderedWidget):
    """Selects between image editing tools, and controls their settings."""

    def __init__(self, layer_stack: LayerStack, image_viewer: ImageViewer, config: AppConfig,
                 generate_fn: Callable[[], None]) -> None:
        """Initializes instances of all Tool classes, connects them to image data, and sets up the tool interface.

        Parameters:
        -----------
        layer_stack: LayerStack
            Used by tools that need to view or modify the edited image.
        image_viewer: ImageViewer
            Used by tools that interact with the way image data is displayed.
        config: AppConfig
            Used by tools to save and load configurable properties.
        generate_fn: Callable
            Connected to the "Generate" button, if one is enabled.
        """
        super().__init__()
        self.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Maximum))
        self._layer_stack = layer_stack
        self._image_viewer = image_viewer
        self._config = config
        self._event_handler = ToolEventHandler(image_viewer)
        self._event_handler.tool_changed.connect(self._setup_active_tool)
        self._layout = QVBoxLayout(self)
        self._orientation = None
        self._panel_box_layout = None
        self._panel_box = CollapsibleBox(TOOL_PANEL_TITLE,
                                         parent=self,
                                         scrolling=False,
                                         orientation=Qt.Orientation.Horizontal)
        self._panel_box.set_expanded_size_policy(QSizePolicy.Ignored)
        self._panel_box.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._layer_panel = LayerPanel(layer_stack)

        self._generate_button = QPushButton(GENERATE_BUTTON_TEXT)
        self._generate_button.clicked.connect(generate_fn)

        # Setup tool list:
        self._tool_list = QWidget()
        self._tool_list_layout = QVBoxLayout(self._tool_list)
        self._tool_list_layout.setAlignment(Qt.AlignTop | Qt.AlignVCenter)
        self._tool_list_layout.setSpacing(LIST_SPACING)

        class ToolButton(QWidget):
            """Displays a tool icon and label, indicates if the tool is selected."""

            tool_selected = pyqtSignal(str)

            def __init__(self, connected_tool: BaseTool) -> None:
                super().__init__()
                self._layout = QHBoxLayout(self)
                self._tool = connected_tool
                self._icon = connected_tool.get_icon()
                label_text = connected_tool.label
                if connected_tool.get_hotkey() is not None:
                    key_sequence = QKeySequence(connected_tool.get_hotkey())
                    label_text += f' [{key_sequence.toString()}]'
                self._label = QLabel(label_text)
                self._layout.addStretch(30)
                self._layout.addWidget(self._label, stretch=100)
                self._icon_bounds = QRect()
                self.setToolTip(connected_tool.get_tooltip_text())
                self._active = False
                self.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Maximum))

            def sizeHint(self) -> QSize:
                """Set expected size based on the label's expected size."""
                label_hint = self._label.sizeHint()
                return QSize(label_hint.width(), label_hint.height())

            def resizeEvent(self, event: Optional[QResizeEvent]):
                """Recalculate and cache icon bounds on size change."""
                self._icon_bounds = get_scaled_placement(QRect(0, 0, self._label.x(), self.height()), QSize(10, 10), 8)

            @property
            def is_active(self) -> bool:
                """Checks whether the associated tool is shown as active."""
                return self._active

            @is_active.setter
            def is_active(self, active: bool) -> None:
                """Sets whether the associated tool is shown as active."""
                self._active = active
                self.update()

            def mousePressEvent(self, unused_event: Optional[QMouseEvent]) -> None:
                """Trigger tool change if clicked when not selected."""
                if not self.is_active:
                    self.tool_selected.emit(self._tool.label)

            def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
                """Highlight when selected."""
                painter = QPainter(self)
                if self.is_active:
                    pen = QPen(self.palette().color(self.foregroundRole()), 2)
                else:
                    pen = QPen(self.palette().color(self.backgroundRole()).lighter(), 2)

                painter.setPen(pen)
                painter.drawRect(QRect(0, 0, self.width(), self.height()).adjusted(4, 4, -4, -4))
                self._icon.paint(painter, self._icon_bounds)

        self._tools: Dict[str, BaseTool] = {}
        self._tool_widgets: Dict[str, ToolButton] = {}
        self._active_tool: Optional[BaseTool] = None
        self._active_tool_panel: Optional[QWidget] = None

        self._tool_control_box = CollapsibleBox()
        self._tool_control_layout = QStackedLayout()
        self._tool_control_box.set_content_layout(self._tool_control_layout)

        # Create individual tools:
        def add_tool(new_tool: BaseTool):
            """Set up a ToolButton for a new tool, and index the tool by label."""
            self._tools[new_tool.label] = new_tool
            button = ToolButton(new_tool)
            self._tool_widgets[new_tool.label] = button
            button.tool_selected.connect(self._switch_active_tool)
            self._event_handler.register_hotkey(new_tool.get_hotkey(), new_tool)
            self._tool_list_layout.addWidget(button)

        selection_tool = SelectionTool(layer_stack, image_viewer, config)
        add_tool(selection_tool)
        self._switch_active_tool(selection_tool.label)
        brush_tool = BrushTool(layer_stack, image_viewer, config)
        add_tool(brush_tool)
        mask_tool = MaskTool(layer_stack, image_viewer, config)
        add_tool(mask_tool)
        eyedropper_tool = EyedropperTool(layer_stack, config)
        add_tool(eyedropper_tool)
        for tool in brush_tool, mask_tool:
            self._event_handler.register_tool_delegate(tool, selection_tool, Qt.KeyboardModifier.AltModifier)
        self._event_handler.register_tool_delegate(brush_tool, eyedropper_tool, Qt.KeyboardModifier.ControlModifier)
        self.resizeEvent(None)
        self.set_orientation(Qt.Orientation.Vertical)

    def set_orientation(self, orientation: Qt.Orientation):
        """Sets the panel to a vertical or horizontal Qt.Orientation."""
        if self._orientation == orientation:
            return
        self._orientation = orientation
        prev_panel_box = self._panel_box
        show_generate_button = self._generate_button.isVisible()
        if self._panel_box is not None:
            self._layout.removeWidget(self._panel_box)
        self._panel_box = CollapsibleBox(TOOL_PANEL_TITLE,
                                         parent=self,
                                         scrolling=False,
                                         orientation=orientation)
        self._panel_box_layout = QHBoxLayout() if orientation == Qt.Orientation.Vertical else QVBoxLayout()
        self._panel_box.set_content_layout(self._panel_box_layout)
        self._layout.addWidget(self._panel_box)
        for widget, stretch in (
                (self._tool_list, 30),
                (self._tool_control_box, 30),
                # (self._layer_panel, 30)
        ):
            if widget is None:
                continue
            self._panel_box_layout.addWidget(widget, stretch=stretch)
        if show_generate_button:
            self._panel_box_layout.addWidget(self._generate_button)
        if prev_panel_box is not None:
            prev_panel_box.setParent(None)
        self.update()

    def show_tab_toggle(self, should_show: bool) -> None:
        """Sets whether the button to show/hide the tool panel should be visible."""
        if self._panel_box is not None:
            self._panel_box.show_button_bar(should_show)

    def show_generate_button(self, should_show: bool) -> None:
        """Shows or hides the image generation button."""
        if not should_show and self._generate_button.isVisible():
            if self._panel_box_layout is not None:
                self._panel_box_layout.removeWidget(self._generate_button)
            self._generate_button.setParent(None)
        elif should_show and not self._generate_button.isVisible():
            self._panel_box_layout.addWidget(self._generate_button)
            self._generate_button.show()

    def _switch_active_tool(self, tool_label: Optional[str]) -> None:
        """Sets a new tool as the active tool."""
        active_tool = None if tool_label not in self._tools else self._tools[tool_label]
        self._event_handler.active_tool = active_tool
        # Event handler will send a signal to trigger _setup_active_tool

    def _setup_active_tool(self, tool_label: Optional[str]) -> None:
        """Reconfigures the panel for a new active tool."""
        if self._active_tool_panel is not None:
            self._tool_control_layout.removeWidget(self._active_tool_panel)
            self._active_tool_panel.setParent(None)
            self._active_tool_panel = None
        active_tool = None if tool_label not in self._tools else self._tools[tool_label]
        self._active_tool = active_tool
        if active_tool is not None:
            for label, widget in self._tool_widgets.items():
                widget.is_active = label == tool_label
            self._update_cursor()
            active_tool.cursor_change.connect(self._update_cursor)
            tool_panel = active_tool.get_control_panel()
            self._tool_control_box.set_title_label(self._active_tool.label + " Tool Settings")
            if tool_panel is not None:
                self._active_tool_panel = tool_panel
                self._tool_control_layout.addWidget(tool_panel)
        else:
            self._update_cursor()

    def _update_cursor(self) -> None:
        """Apply a cursor to the image viewer, or resets to the default."""
        if self._active_tool is None:
            return
        new_cursor = self._active_tool.cursor
        self._image_viewer.set_cursor(new_cursor)

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Keep tool list sized correctly within the panel."""
        self._tool_list.setMaximumWidth(self.width())
