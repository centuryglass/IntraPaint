"""Selects between image editing tools, and controls their settings."""
from typing import Optional, Dict, Callable

from PyQt5.QtCore import Qt, pyqtSignal, QRect, QSize, QMargins
from PyQt5.QtGui import QMouseEvent, QPaintEvent, QPainter, QPen, QResizeEvent
from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, QScrollArea, QPushButton, \
    QStackedLayout

from src.config.application_config import AppConfig
from src.image.layer_stack import LayerStack
from src.tools.base_tool import BaseTool
from src.tools.brush_tool import BrushTool
from src.tools.eyedropper_tool import EyedropperTool
from src.tools.layer_transform_tool import LayerTransformTool
from src.tools.mask_tool import MaskTool
from src.tools.selection_tool import SelectionTool
from src.tools.tool_event_handler import ToolEventHandler
from src.ui.image_viewer import ImageViewer
from src.ui.panel.layer_panel import LayerPanel
from src.ui.util.geometry_utils import get_scaled_placement
from src.ui.util.screen_size import get_screen_size
from src.ui.widget.bordered_widget import BorderedWidget
from src.ui.widget.collapsible_box import CollapsibleBox
from src.ui.widget.grid_container import GridContainer
from src.ui.widget.key_hint_label import KeyHintLabel

TOOL_PANEL_TITLE = 'Tools'
LIST_SPACING = 10
TOOL_ICON_SIZE = 40
GENERATE_BUTTON_TEXT = 'Generate'

LAYER_PANEL_MIN_WIDTH = 0
LAYER_PANEL_MIN_HEIGHT = 0

TOOL_LIST_STRETCH = 2
TOOL_PANEL_STRETCH = 30
LAYER_PANEL_STRETCH = 3


class ToolPanel(QWidget):
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
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding))
        self._layer_stack = layer_stack
        self._image_viewer = image_viewer
        self._event_handler = ToolEventHandler(image_viewer)
        self._event_handler.tool_changed.connect(self._setup_active_tool)
        self._layout = QStackedLayout(self)
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
        self._tool_list = GridContainer()

        self._tools: Dict[str, BaseTool] = {}
        self._tool_widgets: Dict[str, '_ToolButton'] = {}
        self._toolbar_tool_widgets: Dict[str, '_ToolButton'] = {}
        self._active_tool: Optional[BaseTool] = None
        self._active_tool_panel: Optional[QWidget] = None

        self._tool_control_box = BorderedWidget()
        self._tool_control_box.contents_margin = 0
        self._tool_control_layout = QVBoxLayout(self._tool_control_box)
        self._tool_control_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tool_control_label = QLabel()
        self._tool_control_label.setStyleSheet("text-decoration: bold;")
        self._tool_control_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._tool_control_layout.addWidget(self._tool_control_label, stretch=0)
        
        self._tool_control_box.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding))

        self._tool_scroll_area = QScrollArea()
        self._tool_scroll_area.setWidgetResizable(True)
        self._tool_scroll_area.setWidget(self._tool_control_box)
        self._tool_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._tool_scroll_area.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Expanding))

        # Create individual tools:

        def add_tool(new_tool: BaseTool):
            """Set up a ToolButton for a new tool, and index the tool by label."""
            self._tools[new_tool.label] = new_tool
            button = _ToolButton(new_tool)
            toolbar_button = _ToolButton(new_tool)
            self._tool_widgets[new_tool.label] = button
            self._toolbar_tool_widgets[new_tool.label] = toolbar_button
            button.tool_selected.connect(self._switch_active_tool)
            toolbar_button.tool_selected.connect(self._switch_active_tool)
            self._event_handler.register_hotkeys(new_tool)
            self._tool_list.add_widget(button)

        brush_tool = BrushTool(layer_stack, image_viewer)
        add_tool(brush_tool)
        eyedropper_tool = EyedropperTool(layer_stack)
        add_tool(eyedropper_tool)
        selection_tool = SelectionTool(layer_stack, image_viewer)
        add_tool(selection_tool)
        mask_tool = MaskTool(layer_stack, image_viewer)
        add_tool(mask_tool)
        transform_tool = LayerTransformTool(layer_stack, image_viewer)
        add_tool(transform_tool)
        self._event_handler.register_tool_delegate(brush_tool, eyedropper_tool, Qt.KeyboardModifier.ControlModifier)
        self._switch_active_tool(config.get(AppConfig.LAST_ACTIVE_TOOL))
        self.resizeEvent(None)
        self.set_orientation(Qt.Orientation.Vertical)

    @property
    def expanded(self) -> bool:
        """Controls whether the contents are expanded or hidden."""
        return self._panel_box.is_expanded()

    @expanded.setter
    def expanded(self, is_expanded: bool) -> None:
        self._panel_box.set_expanded(is_expanded)

    @property
    def orientation(self) -> Qt.Orientation:
        """Gets the current panel orientation."""
        return self._orientation

    def _handle_panel_toggle(self, panel_expanded: bool):
        for tool_widget in self._toolbar_tool_widgets.values():
            tool_widget.setEnabled(not panel_expanded)
            tool_widget.setVisible(not panel_expanded)

    def set_orientation(self, orientation: Qt.Orientation):
        """Sets the panel to a vertical or horizontal Qt.Orientation."""
        if self._orientation == orientation:
            return
        self._orientation = orientation
        prev_panel_box = self._panel_box
        show_generate_button = self._generate_button.isVisible()
        if self._panel_box is not None:
            self._layout.removeWidget(self._panel_box)
        box_orientation = Qt.Orientation.Vertical if orientation == Qt.Orientation.Horizontal \
            else Qt.Orientation.Horizontal
        self._panel_box = CollapsibleBox(TOOL_PANEL_TITLE,
                                         parent=self,
                                         scrolling=False,
                                         orientation=box_orientation)
        for tool_widget in self._toolbar_tool_widgets.values():
            self._panel_box.add_button_bar_widget(tool_widget)
        self._handle_panel_toggle(self._panel_box.is_expanded())
        self._panel_box.box_toggled.connect(self._handle_panel_toggle)
        if prev_panel_box is not None:
            self._panel_box.set_expanded(prev_panel_box.is_expanded())
        self._panel_box_layout = QVBoxLayout() if orientation == Qt.Orientation.Vertical else QHBoxLayout()
        self._panel_box.set_content_layout(self._panel_box_layout)
        self._panel_box_layout.setContentsMargins(QMargins(2, 2, 2, 2))
        self._layout.addWidget(self._panel_box)
        self._layout.setCurrentWidget(self._panel_box)
        self._panel_box_layout.addWidget(self._tool_list, stretch=TOOL_LIST_STRETCH)
        self._panel_box_layout.addWidget(self._tool_scroll_area, stretch=TOOL_PANEL_STRETCH)
        if self._layer_panel is not None:
            self._panel_box_layout.addWidget(self._layer_panel, stretch=LAYER_PANEL_STRETCH)
        self._panel_box_layout.addWidget(self._generate_button)
        self._generate_button.setVisible(show_generate_button)
        if orientation == Qt.Orientation.Horizontal:
            generate_label = "\n".join(GENERATE_BUTTON_TEXT)
            self._tool_list.fill_vertical = True
            self._tool_list.layout().setAlignment(Qt.AlignmentFlag.AlignLeft)
        else:
            generate_label = GENERATE_BUTTON_TEXT
            self._tool_list.fill_horizontal = True
            self._tool_list.layout().setAlignment(Qt.AlignmentFlag.AlignTop)
        self._generate_button.setText(generate_label)
        if prev_panel_box is not None:
            prev_panel_box.setParent(None)
        self.updateGeometry()
        self.resizeEvent(None)

    def show_tab_toggle(self, should_show: bool) -> None:
        """Sets whether the button to show/hide the tool panel should be visible."""
        if self._panel_box is not None:
            self._panel_box.show_button_bar(should_show)

    def show_generate_button(self, should_show: bool) -> None:
        """Shows or hides the image generation button."""
        if not should_show and self._generate_button.isVisible():
            if self._panel_box_layout is not None:
                self._panel_box_layout.removeWidget(self._generate_button)
            self._generate_button.setVisible(False)
        elif should_show and not self._generate_button.isVisible():
            if self._panel_box_layout is not None:
                self._panel_box_layout.addWidget(self._generate_button)
            self._generate_button.show()

    def _switch_active_tool(self, tool_label: Optional[str]) -> None:
        """Sets a new tool as the active tool."""
        active_tool = None if tool_label not in self._tools else self._tools[tool_label]
        if active_tool is not None:
            AppConfig.instance().set(AppConfig.LAST_ACTIVE_TOOL, active_tool.label)
        self._event_handler.active_tool = active_tool
        # Event handler will send a signal to trigger _setup_active_tool

    def _setup_active_tool(self, tool_label: Optional[str]) -> None:
        """Reconfigures the panel for a new active tool."""
        if self._active_tool_panel is not None:
            self._tool_control_layout.removeWidget(self._active_tool_panel)
            self._active_tool_panel.hide()
            self._active_tool_panel.setParent(None)
            self._active_tool_panel = None
        active_tool = None if tool_label not in self._tools else self._tools[tool_label]
        self._active_tool = active_tool
        if active_tool is not None:
            self._tool_control_label.setText(f'{active_tool.label}\n{active_tool.get_tooltip_text()}')
            for label, widget in [*self._tool_widgets.items(), *self._toolbar_tool_widgets.items()]:
                widget.is_active = label == tool_label
            self._update_cursor()
            active_tool.cursor_change.connect(self._update_cursor)
            tool_panel = active_tool.get_control_panel()
            tool_panel.setToolTip(active_tool.get_tooltip_text())
            if tool_panel is not None:
                self._active_tool_panel = tool_panel
                self._tool_control_layout.addWidget(tool_panel, stretch=1)
                tool_panel.show()
        else:
            self._update_cursor()
            self._tool_control_label.setText('')
        self.updateGeometry()

    def _update_cursor(self) -> None:
        """Apply a cursor to the image viewer, or resets to the default."""
        if self._active_tool is None:
            return
        new_cursor = self._active_tool.cursor
        self._image_viewer.set_cursor(new_cursor)

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Keep tool list sized correctly within the panel."""
        self._tool_control_box.setMaximumWidth(self._tool_scroll_area.width()
                                               - self._tool_scroll_area.contentsMargins().left() * 2
                                               - self._tool_scroll_area.verticalScrollBar().sizeHint().width() * 2)
        show_layer_panel = ((self._orientation == Qt.Orientation.Horizontal and self.width() >= LAYER_PANEL_MIN_WIDTH)
                            or (self._orientation == Qt.Orientation.Vertical
                                and self.height() >= LAYER_PANEL_MIN_HEIGHT))
        if show_layer_panel and self._panel_box_layout is not None:
            if self._layer_panel is None:
                self._layer_panel = LayerPanel(self._layer_stack)
            self._panel_box_layout.insertWidget(self._panel_box_layout.count() - 2, self._layer_panel)
        elif self._layer_panel is not None:
            if self._panel_box_layout is not None:
                self._panel_box_layout.removeWidget(self._layer_panel)
            self._layer_panel.hide()
            self._layer_panel.setParent(None)
            self._layer_panel = None


class _ToolButton(QWidget):
    """Displays a tool icon and label, indicates if the tool is selected."""

    tool_selected = pyqtSignal(str)

    def __init__(self, connected_tool: BaseTool) -> None:
        super().__init__()
        self._tool = connected_tool
        self._icon = connected_tool.get_icon()
        self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        label_text = connected_tool.label
        if connected_tool.get_hotkey() is not None:
            self._key_hint = KeyHintLabel(connected_tool.get_hotkey(), self)
            self._key_hint.setAlignment(Qt.AlignmentFlag.AlignRight)
        else:
            self._key_hint = None
        self.setToolTip(label_text)
        self._icon_bounds = QRect()
        self._active = False

    def sizeHint(self) -> QSize():
        """Returns ideal size as TOOL_ICON_SIZExTOOL_ICON_SIZE."""
        screen = get_screen_size(self)
        if screen is None:
            return QSize(TOOL_ICON_SIZE, TOOL_ICON_SIZE)
        size = max(min(screen.width() // 30, screen.height() // 30), TOOL_ICON_SIZE)
        return QSize(int(size * 1.5), size)

    def resizeEvent(self, event: Optional[QResizeEvent]):
        """Recalculate and cache icon bounds on size change."""
        self._icon_bounds = get_scaled_placement(QRect(0, 0, self.width(), self.height()), QSize(10, 10), 8)
        if self._key_hint is not None:
            self._key_hint.setGeometry(QRect(self._icon_bounds.right() + 1,
                                             self._icon_bounds.center().y() - self._icon_bounds.height() // 4,
                                             self._icon_bounds.width() // 2,
                                             self._icon_bounds.height() // 2))

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
        painter.drawRect(self._icon_bounds.adjusted(-4, -4, 4, 4))
        self._icon.paint(painter, self._icon_bounds)

