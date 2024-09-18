"""Provides buttons to select between tools, renders the active tool's control panel, and renders an extra tabbed
   area with layer, navigation, and color picking interfaces."""
from typing import Optional, Dict, List

from PySide6.QtCore import Qt, Signal, QRect, QSize, QMargins, QObject
from PySide6.QtGui import QMouseEvent, QPaintEvent, QPainter, QPen, QResizeEvent
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, QScrollArea, QGridLayout, QLayout, \
    QApplication, QTabWidget

from src.tools.base_tool import BaseTool
from src.ui.layout.draggable_divider import DraggableDivider
from src.ui.layout.reactive_layout_widget import ReactiveLayoutWidget
from src.ui.widget.key_hint_label import KeyHintLabel
from src.util.visual.display_size import get_window_size
from src.util.visual.geometry_utils import get_scaled_placement

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


TOOL_PANEL_TITLE = _tr('Tools')

TOOL_ICON_SIZE = 48

TOOL_LIST_STRETCH = 0
TOOL_PANEL_STRETCH = 50
LAYER_PANEL_STRETCH = 30

MIN_SIZE_FOR_TOOL_LABEL = QSize(300, 300)


class ToolPanel(QWidget):
    """Provides buttons to select between tools, renders the active tool's control panel, and renders an extra tabbed
       area with where additional small panels can be added."""

    panel_toggled = Signal(bool)
    tool_selected = Signal(QObject)

    def __init__(self) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        self._orientation = Qt.Orientation.Vertical
        self._layout = QVBoxLayout(self)
        self._divider = DraggableDivider()

        self._utility_tab_panel = QTabWidget()
        self._utility_tab_panels: List[QWidget] = []

        # Setup tool list:
        self._tool_button_layout = QGridLayout()
        self._tool_button_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self._tool_button_layout.setSpacing(2)
        self._row_count = 0
        self._column_count = 0

        self._tool_widgets: Dict[str, '_ToolButton'] = {}
        self._toolbar_tool_widgets: Dict[str, '_ToolButton'] = {}
        self._active_tool_panel: Optional[QWidget] = None

        self._tool_control_box = ReactiveLayoutWidget()
        self._tool_control_box.contents_margin = 0
        self._tool_control_layout = QVBoxLayout(self._tool_control_box)
        self._tool_control_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tool_control_label = QLabel()
        self._tool_control_label.setWordWrap(True)
        self._tool_control_label.setStyleSheet('text-decoration: bold;')
        self._tool_control_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignTop)
        self._tool_control_layout.addWidget(self._tool_control_label, stretch=2)
        self._tool_control_layout.addStretch(2)
        self._tool_control_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self._tool_control_box.add_visibility_limit(self._tool_control_label, MIN_SIZE_FOR_TOOL_LABEL)
        self._tool_control_box.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding,
                                                         QSizePolicy.Policy.Expanding))

        self._tool_scroll_area = QScrollArea()
        self._tool_scroll_area.setWidgetResizable(True)
        self._tool_scroll_area.setWidget(self._tool_control_box)
        self._tool_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._tool_scroll_area.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding,
                                                         QSizePolicy.Policy.Expanding))
        self._build_layout()

    def add_tool_button(self, tool: BaseTool) -> None:
        """Creates and shows a new tool button for a given tool object."""
        if tool.label in self._tool_widgets:
            return
        primary_button = _ToolButton(tool)
        toolbar_button = _ToolButton(tool)
        self._tool_widgets[tool.label] = primary_button
        self._toolbar_tool_widgets[tool.label] = toolbar_button
        primary_button.tool_selected.connect(self.tool_selected)
        toolbar_button.tool_selected.connect(self.tool_selected)
        self._build_tool_button_layout()

    def remove_tool_button(self, tool: BaseTool) -> None:
        """Removes a tool button from the panel."""
        tool_name = tool.label
        buttons = []
        if tool_name in self._tool_widgets:
            buttons.append(self._tool_widgets[tool_name])
            del self._tool_widgets[tool_name]
        if tool_name in self._toolbar_tool_widgets:
            buttons.append(self._toolbar_tool_widgets[tool_name])
            del self._toolbar_tool_widgets[tool_name]
        for button in buttons:
            button.tool_selected.disconnect(self.tool_selected)
            button.setVisible(False)
            button.setEnabled(False)
            parent = button.parentWidget()
            if parent is not None:
                layout = parent.layout()
                if layout is not None:
                    idx = layout.indexOf(button)
                    if idx >= 0:
                        layout.takeAt(idx)
            button.setParent(None)
        self._build_tool_button_layout()

    def add_utility_widget_tab(self, widget: QWidget, tab_name: str) -> None:
        """Adds a tabbed utility widget to the tabs at the end of the panel."""
        self._utility_tab_panels.append(widget)
        self._utility_tab_panel.addTab(widget, tab_name)

    @property
    def orientation(self) -> Qt.Orientation:
        """Gets the current panel orientation."""
        return self._orientation

    def _build_layout(self):
        """Ensure the layout is fully populated and configured for the current orientation."""

        # Save widget states in case they need to move:

        def _get_stretch(widget, default):
            idx = self._layout.indexOf(widget)
            if idx < 0:
                return default
            return self._layout.stretch(idx)
        tool_list_stretch = _get_stretch(self._tool_button_layout, TOOL_LIST_STRETCH)
        tool_panel_stretch = _get_stretch(self._tool_scroll_area, TOOL_PANEL_STRETCH)
        layer_panel_stretch = _get_stretch(self._utility_tab_panel, LAYER_PANEL_STRETCH)

        # Replace layout if orientation changed:
        layout_class = QHBoxLayout if self._orientation == Qt.Orientation.Horizontal else QVBoxLayout
        if not isinstance(self._layout, layout_class):
            while self._layout.count() > 0:
                self._layout.takeAt(0)
            temp_widget = QWidget()
            temp_widget.setLayout(self._layout)
            self._layout = layout_class(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._layout.setContentsMargins(QMargins(2, 2, 2, 2))
        if self._layout.count() == 0:
            self._layout.addLayout(self._tool_button_layout, stretch=tool_list_stretch)
            self._layout.addWidget(self._tool_scroll_area, stretch=tool_panel_stretch)
            self._layout.addWidget(self._divider)
            self._layout.addWidget(self._utility_tab_panel, stretch=layer_panel_stretch)
            if self._active_tool_panel is not None and hasattr(self._active_tool_panel, 'set_orientation'):
                self._active_tool_panel.set_orientation(self._orientation)
        self._build_tool_button_layout()
        self.updateGeometry()
        self.resizeEvent(None)

    def set_orientation(self, orientation: Qt.Orientation):
        """Sets the panel to a vertical or horizontal Qt.Orientation."""
        if self._orientation == orientation:
            return
        self._orientation = orientation
        for tab in self._utility_tab_panels:
            if hasattr(tab, 'set_orientation'):
                tab.set_orientation(orientation)
        self._build_layout()

    def setup_active_tool(self, active_tool: Optional[QObject]) -> None:
        """Reconfigures the panel for a new active tool."""
        assert active_tool is None or isinstance(active_tool, BaseTool)
        if self._active_tool_panel is not None:
            while self._tool_control_layout.count() > 2:
                self._tool_control_layout.takeAt(2)
            self._active_tool_panel.hide()
            self._active_tool_panel.setParent(None)
            self._active_tool_panel = None
        if active_tool is not None:
            self._tool_control_label.setText(f'{active_tool.label} - {active_tool.get_tooltip_text()}')
            self._tool_control_box.setToolTip(active_tool.get_tooltip_text())
            for label, widget in [*self._tool_widgets.items(), *self._toolbar_tool_widgets.items()]:
                widget.is_active = label == active_tool.label
            tool_panel = active_tool.get_control_panel()
            if tool_panel is not None:
                tool_panel.setToolTip(active_tool.get_tooltip_text())
                self._active_tool_panel = tool_panel
                self._tool_control_layout.insertWidget(1, tool_panel, stretch=100)
                if hasattr(tool_panel, 'set_orientation'):
                    tool_panel.set_orientation(self._orientation)
                tool_panel.show()
        else:
            self._tool_control_label.setText('')
            self._tool_control_box.setToolTip('')
        self.updateGeometry()

    def _build_tool_button_layout(self) -> None:
        button_list = list(self._tool_widgets.values())
        if len(button_list) == 0:
            return
        button_size = button_list[0].sizeHint()
        if self._orientation == Qt.Orientation.Vertical:
            num_cols = 5
            num_rows = 3
            self._tool_button_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        else:  # Horizontal
            num_rows = 5
            num_cols = 3
            self.setMinimumHeight(0)
            self._tool_button_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        if self._row_count == num_rows and self._column_count == num_cols \
                and self._tool_button_layout.count() == len(self._tool_widgets):
            return
        for column in range(self._tool_button_layout.columnCount()):
            self._tool_button_layout.setColumnMinimumWidth(column, 0)
        for row in range(self._tool_button_layout.rowCount()):
            self._tool_button_layout.setRowMinimumHeight(row, 0)
        self._row_count = num_rows
        self._column_count = num_cols
        while self._tool_button_layout.count() > 0:
            self._tool_button_layout.takeAt(0)
        button_idx = 0
        for row in range(num_rows):
            self._tool_button_layout.setRowMinimumHeight(row, button_size.height())
            for column in range(num_cols):
                self._tool_button_layout.setColumnMinimumWidth(column, button_size.width())
                if button_idx >= len(button_list):
                    break
                button = button_list[button_idx]
                self._tool_button_layout.addWidget(button, row, column)
                button_idx += 1

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Keep tool list sized correctly within the panel."""
        max_width = self._tool_scroll_area.width() - self._tool_scroll_area.contentsMargins().left() * 2
        scroll_bar = self._tool_scroll_area.verticalScrollBar()
        if scroll_bar is not None:
            max_width -= scroll_bar.sizeHint().width()
        if max_width > 0:
            self._tool_control_box.setMaximumWidth(max_width)
        if self._active_tool_panel is not None and hasattr(self._active_tool_panel, 'set_orientation'):
            self._active_tool_panel.set_orientation(self._orientation)
        self._build_tool_button_layout()


class _ToolButton(QWidget):
    """Displays a tool icon and label, indicates if the tool is selected."""

    tool_selected = Signal(QObject)

    def __init__(self, connected_tool: BaseTool) -> None:
        super().__init__()
        self._tool = connected_tool
        self._icon = connected_tool.get_icon()
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed))
        label_text = connected_tool.label
        if connected_tool.get_hotkey() is not None:
            self._key_hint: Optional[KeyHintLabel] = KeyHintLabel(connected_tool.get_hotkey(), parent=self)
            self._key_hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._key_hint.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
            self._key_hint.setMinimumSize(self._key_hint.sizeHint())

        else:
            self._key_hint = None
        self.setToolTip(label_text)
        self._icon_bounds = QRect()
        self._active = False

    def sizeHint(self) -> QSize:
        """Returns ideal size as TOOL_ICON_SIZExTOOL_ICON_SIZE."""
        window_size = get_window_size()
        if window_size.isEmpty():
            return QSize(TOOL_ICON_SIZE, TOOL_ICON_SIZE)
        size = max(min(window_size.width() // 40, window_size.height() // 40), TOOL_ICON_SIZE)
        if self._key_hint is not None:
            hint_size = self._key_hint.sizeHint()
            return QSize(max(int(size * 1.5), size + hint_size.width() + 2), size)
        return QSize(int(size * 1.5), size)

    def minimumSizeHint(self) -> QSize:
        """Returns ideal size as TOOL_ICON_SIZExTOOL_ICON_SIZE."""
        return self.sizeHint()

    def resizeEvent(self, unused_event: Optional[QResizeEvent]):
        """Recalculate and cache icon bounds on size change."""
        self._icon_bounds = get_scaled_placement(self.size(), QSize(10, 10), 8)
        if self._key_hint is not None:
            hint_size = self._key_hint.sizeHint()
            self._key_hint.setGeometry(QRect(self._icon_bounds.right() + 2,
                                             self._icon_bounds.center().y() - hint_size.height() // 2,
                                             hint_size.width(),
                                             hint_size.height()))

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
            self.tool_selected.emit(self._tool)

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
