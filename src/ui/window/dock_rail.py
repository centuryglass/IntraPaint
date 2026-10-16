"""Icon rails along the main window's edges, with one button per `PanelDock`, the recent tools and Generate.

- Each window edge has a `DockRail`, a non-movable `QToolBar`. A dock's button sits in the rail of the area the dock was
  last docked in, so it follows the dock between edges. A floating dock's button stays where it was.
- Side rails (left and right) are `SIDE_RAIL_WIDTH` wide, with an icon and keycap per button. Strip rails (top and
  bottom) show icon, name and keycap.
- Clicking a button shows and raises its dock, or hides it if it is showing (`PanelDock.toggle_from_key`). A dock with
  no content has no button.
- The recent tools and the Generate button sit in the rail of the Tools dock and of the Image Generation dock. The
  recent tools fill only the space the other buttons leave, so they never raise the window's minimum size. Their
  maximum count is `AppConfig.TOOLBAR_TOOL_BUTTON_COUNT`.
"""
from enum import IntEnum
from typing import Optional

from PySide6.QtCore import QMargins, QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QFont, QFontMetrics, QIcon, QPainter, QPaintEvent, QPalette, QPen, QResizeEvent
from PySide6.QtWidgets import (QApplication, QBoxLayout, QFrame, QHBoxLayout, QMainWindow, QPushButton,
                               QSizePolicy, QToolBar, QToolButton, QVBoxLayout, QWidget)

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.controller.tool_controller import ToolController
from src.tools.base_tool import BaseTool
from src.ui.ink_style import set_primary_button
from src.ui.widget.shortcut_tooltip import set_shortcut_tooltip
from src.ui.widget.tool_button import ToolButton
from src.ui.window.panel_dock import PanelDock
from src.util.application_state import AppStateTracker, APP_STATE_EDITING
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.keycap import KEYCAP_DEPTH, KEYCAP_PADDING, draw_keycap, keycap_colors, keycap_font, keycap_size
from src.util.visual.text_drawing_utils import get_key_display_string

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.window.dock_rail'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


GENERATE_BUTTON_TEXT = _tr('Generate')
GENERATE_BUTTON_TOOLTIP = _tr('Start image generation')

ICON_PATH_GENERATE = f'{PROJECT_DIR}/resources/icons/tabs/sparkle.svg'

SIDE_RAIL_WIDTH = 32
SIDE_ICON_SIZE = 20
STRIP_ICON_SIZE = 18
STRIPE_WIDTH = 3
PLATE_RADIUS = 5.0
BUTTON_MARGIN = 2
# Height of a side rail's button: icon, gap, and the keycap under it:
SIDE_BUTTON_ICON_TOP = 3
SIDE_BUTTON_GAP = 2
STRIP_BUTTON_SPACING = 6
# Space between a strip button's plate edge and its icon, and between its keycap and the opposite edge:
STRIP_BUTTON_PADDING = 6
# Smallest tool button the recent tools strip draws in a side rail:
RECENT_TOOL_SIZE = SIDE_RAIL_WIDTH
RAIL_SPACING = 2


class _GenerateButton(QPushButton):
    """The rail's Generate button. In a side rail it shows only its icon, at the rail's width."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.icon_only = False

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the icon in a square a rail wide while icon-only."""
        if self.icon_only:
            return QSize(SIDE_RAIL_WIDTH - 2 * BUTTON_MARGIN, SIDE_ICON_SIZE + 2 * BUTTON_MARGIN + 2)
        return super().sizeHint()

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns `sizeHint` while icon-only."""
        return self.sizeHint() if self.icon_only else super().minimumSizeHint()


class DockGroup(IntEnum):
    """Which part of a rail a dock's button is in. A rule separates the groups."""
    UPPER = 0
    LOWER = 1


def toolbar_area_for(area: Qt.DockWidgetArea) -> Qt.ToolBarArea:
    """Returns the toolbar area on the same window edge as a dock area."""
    return {
        Qt.DockWidgetArea.LeftDockWidgetArea: Qt.ToolBarArea.LeftToolBarArea,
        Qt.DockWidgetArea.RightDockWidgetArea: Qt.ToolBarArea.RightToolBarArea,
        Qt.DockWidgetArea.TopDockWidgetArea: Qt.ToolBarArea.TopToolBarArea,
        Qt.DockWidgetArea.BottomDockWidgetArea: Qt.ToolBarArea.BottomToolBarArea,
    }[area]


class RailButton(QToolButton):
    """Shows one dock's icon, and its keycap or name, with a plate and a stripe on the canvas side while the dock is
    showing."""

    def __init__(self, dock: PanelDock) -> None:
        super().__init__()
        self._dock = dock
        self._side = True
        self._edge = Qt.Edge.LeftEdge
        self.setAutoRaise(True)
        self.setCheckable(True)
        self.setChecked(dock.is_showing)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setIcon(dock.windowIcon())
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setToolTip('')
        set_shortcut_tooltip(self, dock.windowTitle(), dock.shortcut_config_key)
        dock.visibilityChanged.connect(self.setChecked)
        # A click only runs the dock's toggle, since the checked state follows the dock:
        self.clicked.connect(self._toggle_dock)
        AppConfig().connect(self, AppConfig.TAB_FONT_POINT_SIZE, self._font_changed)
        if dock.shortcut_config_key is not None:
            KeyConfig().connect(self, dock.shortcut_config_key, self._font_changed)
        self.setFont(self._label_font())

    @property
    def dock(self) -> PanelDock:
        """Returns the dock this button toggles."""
        return self._dock

    def set_placement(self, side: bool, edge: Qt.Edge) -> None:
        """Sets whether the button is drawn for a side rail, and the window edge its rail is on."""
        if side != self._side or edge != self._edge:
            self._side = side
            self._edge = edge
            self.updateGeometry()
            self.update()

    def _toggle_dock(self) -> None:
        self._dock.toggle_from_key()
        self.setChecked(self._dock.is_showing)

    def _font_changed(self, *_args) -> None:
        self.setFont(self._label_font())
        self.updateGeometry()
        self.update()

    @staticmethod
    def _label_font() -> QFont:
        font = QFont(QApplication.font())
        font.setPointSize(AppConfig().get(AppConfig.TAB_FONT_POINT_SIZE))
        return font

    def _key_text(self) -> str:
        key = self._dock.shortcut_config_key
        if key is None:
            return ''
        return get_key_display_string(KeyConfig().get(key), rich_text=False)

    def _keycap_size(self) -> QSize:
        metrics = QFontMetrics(keycap_font(QApplication.font()))
        text = self._key_text()
        return keycap_size(QSize(metrics.horizontalAdvance(text), metrics.height()))

    def sizeHint(self) -> QSize:
        """Returns 32 px wide in a side rail, with room for the icon and the keycap under it. In a strip rail, returns
        room for the icon, name and keycap in a row."""
        key_size = self._keycap_size() if self._key_text() != '' else QSize(0, 0)
        if self._side:
            height = SIDE_BUTTON_ICON_TOP + SIDE_ICON_SIZE + SIDE_BUTTON_GAP + key_size.height() + BUTTON_MARGIN
            return QSize(SIDE_RAIL_WIDTH, height)
        metrics = QFontMetrics(self.font())
        width = BUTTON_MARGIN * 2 + STRIP_BUTTON_PADDING * 2 + STRIP_ICON_SIZE + STRIP_BUTTON_SPACING \
            + metrics.horizontalAdvance(self._dock.windowTitle())
        if key_size.width() > 0:
            width += STRIP_BUTTON_SPACING + key_size.width()
        return QSize(width, max(STRIP_ICON_SIZE, metrics.height(), key_size.height()) + 2 * BUTTON_MARGIN + 4)

    def minimumSizeHint(self) -> QSize:
        """Returns `sizeHint`."""
        return self.sizeHint()

    def _stripe_rect(self) -> QRectF:
        bounds = QRectF(self.rect())
        if self._edge == Qt.Edge.LeftEdge:
            return QRectF(bounds.left(), bounds.top() + 2, STRIPE_WIDTH, bounds.height() - 4)
        if self._edge == Qt.Edge.RightEdge:
            return QRectF(bounds.right() - STRIPE_WIDTH + 1, bounds.top() + 2, STRIPE_WIDTH, bounds.height() - 4)
        if self._edge == Qt.Edge.TopEdge:
            return QRectF(bounds.left() + 2, bounds.top(), bounds.width() - 4, STRIPE_WIDTH)
        return QRectF(bounds.left() + 2, bounds.bottom() - STRIPE_WIDTH + 1, bounds.width() - 4, STRIPE_WIDTH)

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the plate and stripe if the dock is showing, then the icon and keycap, or icon, name and keycap."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        highlight = palette.color(QPalette.ColorRole.Highlight)
        plate = QRectF(self.rect()).adjusted(BUTTON_MARGIN, 1, -BUTTON_MARGIN, -1)
        if self.isChecked():
            painter.setPen(QPen(palette.color(QPalette.ColorRole.Shadow), 1))
            painter.setBrush(highlight)
            painter.drawRoundedRect(plate, PLATE_RADIUS, PLATE_RADIUS)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(palette.color(QPalette.ColorRole.Shadow))
            painter.drawRect(self._stripe_rect())
        elif self.isDown():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(palette.color(QPalette.ColorRole.Button))
            painter.drawRoundedRect(plate, PLATE_RADIUS, PLATE_RADIUS)
        elif self.underMouse():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(palette.color(QPalette.ColorRole.Midlight))
            painter.drawRoundedRect(plate, PLATE_RADIUS, PLATE_RADIUS)
        key_text = self._key_text()
        fill, outline, key_color = keycap_colors(palette)
        key_size = self._keycap_size() if key_text != '' else QSize(0, 0)
        if self._side:
            icon_rect = QRect((self.width() - SIDE_ICON_SIZE) // 2, SIDE_BUTTON_ICON_TOP, SIDE_ICON_SIZE,
                              SIDE_ICON_SIZE)
            self.icon().paint(painter, icon_rect)
            if key_text != '':
                key_width = min(key_size.width(), self.width() - 2)
                key_rect = QRectF((self.width() - key_width) / 2, icon_rect.bottom() + SIDE_BUTTON_GAP, key_width,
                                  key_size.height())
                self._draw_keycap(painter, key_rect, key_text, fill, outline, key_color)
        else:
            icon_rect = QRect(BUTTON_MARGIN + STRIP_BUTTON_PADDING, (self.height() - STRIP_ICON_SIZE) // 2,
                              STRIP_ICON_SIZE, STRIP_ICON_SIZE)
            self.icon().paint(painter, icon_rect)
            text_color = palette.color(QPalette.ColorRole.HighlightedText if self.isChecked()
                                       else QPalette.ColorRole.ButtonText)
            painter.setPen(text_color)
            painter.setFont(self.font())
            text_left = icon_rect.right() + STRIP_BUTTON_SPACING
            text_width = QFontMetrics(self.font()).horizontalAdvance(self._dock.windowTitle())
            painter.drawText(QRect(text_left, 0, text_width, self.height()), Qt.AlignmentFlag.AlignVCenter,
                             self._dock.windowTitle())
            if key_text != '':
                key_rect = QRectF(text_left + text_width + STRIP_BUTTON_SPACING,
                                  (self.height() - key_size.height()) / 2, key_size.width(), key_size.height())
                self._draw_keycap(painter, key_rect, key_text, fill, outline, key_color)
        painter.end()

    def _draw_keycap(self, painter: QPainter, bounds: QRectF, text: str, fill, outline, text_color) -> None:
        draw_keycap(painter, bounds, fill, outline)
        painter.setPen(text_color)
        painter.setFont(keycap_font(QApplication.font()))
        painter.drawText(bounds.adjusted(0, KEYCAP_PADDING.top() - 1, 0, -KEYCAP_PADDING.bottom() - KEYCAP_DEPTH),
                         Qt.AlignmentFlag.AlignCenter, text)


class RecentToolStrip(QWidget):
    """Shows as many of the most recently used tools as fit along its length, up to the configured maximum.

    The strip's minimum size is zero, so it never raises the minimum size of the rail or window. The tools' buttons
    are the strip's own.
    """

    def __init__(self, tool_controller: ToolController) -> None:
        super().__init__()
        self._tool_controller = tool_controller
        self._side = True
        self._buttons: dict[BaseTool, ToolButton] = {}
        self._recent: list[BaseTool] = []
        self._max_count = AppConfig().get(AppConfig.TOOLBAR_TOOL_BUTTON_COUNT)
        for tool_name in Cache().get(Cache.RECENT_TOOLS):
            tool = tool_controller.find_tool_by_label(tool_name)
            if tool is not None and tool not in self._recent:
                self._recent.append(tool)
        for tool in tool_controller.tools:
            self._add_tool(tool)
        active = tool_controller.active_tool
        if active is not None:
            self._mark_active(active)
        tool_controller.tool_added.connect(self._add_tool)
        tool_controller.tool_removed.connect(self._remove_tool)
        tool_controller.active_tool_changed.connect(self._mark_active)
        AppConfig().connect(self, AppConfig.TOOLBAR_TOOL_BUTTON_COUNT, self._set_max_count)
        self._apply_side(True)

    @property
    def shown_tools(self) -> list[BaseTool]:
        """Returns the tools whose buttons are currently shown, most recent first."""
        return [tool for tool, button in self._buttons.items() if not button.isHidden()]

    def _button_extent(self) -> int:
        return RECENT_TOOL_SIZE if self._side else RECENT_TOOL_SIZE + 2

    def _apply_side(self, side: bool) -> None:
        self._side = side
        if side:
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        for button in self._buttons.values():
            button.set_edge_length(self._button_extent())
        self._layout_buttons()

    def set_side(self, side: bool) -> None:
        """Sets whether the strip runs top to bottom, in a side rail, or left to right, in a strip rail."""
        if side != self._side:
            self._apply_side(side)

    def sizeHint(self) -> QSize:
        """Returns room for the maximum number of buttons."""
        extent = self._button_extent()
        length = extent * self._max_count
        return QSize(extent, length) if self._side else QSize(length, extent)

    def minimumSizeHint(self) -> QSize:
        """Returns an empty size, so the strip takes only the space the rest of the rail leaves."""
        return QSize(0, 0)

    def _add_tool(self, tool: BaseTool) -> None:
        if tool in self._buttons:
            return
        button = ToolButton(tool)
        button.setParent(self)
        button.set_edge_length(self._button_extent())
        button.tool_selected.connect(self._tool_controller.set_active_tool)
        button.hide()
        self._buttons[tool] = button
        if len(self._recent) < self._max_count and tool not in self._recent:
            self._recent.append(tool)
        self._layout_buttons()

    def _remove_tool(self, tool: BaseTool) -> None:
        button = self._buttons.pop(tool, None)
        if button is not None:
            button.setParent(None)
            button.deleteLater()
        if tool in self._recent:
            self._recent.remove(tool)
        self._layout_buttons()

    def _mark_active(self, active_tool: BaseTool) -> None:
        for tool, button in self._buttons.items():
            button.is_active = tool is active_tool
        if active_tool in self._recent:
            self._recent.remove(active_tool)
        self._recent.insert(0, active_tool)
        self._recent = self._recent[:max(self._max_count, 0)]
        Cache().set(Cache.RECENT_TOOLS, [tool.label for tool in self._recent])
        self._layout_buttons()

    def _set_max_count(self, count: int) -> None:
        self._max_count = count
        self._recent = self._recent[:max(count, 0)]
        for tool in self._tool_controller.tools:
            if len(self._recent) >= count:
                break
            if tool not in self._recent:
                self._recent.append(tool)
        self._layout_buttons()
        self.updateGeometry()

    def _layout_buttons(self) -> None:
        """Places the first recent tools that fit, hiding the others."""
        extent = self._button_extent()
        length = self.height() if self._side else self.width()
        fit = max(0, (length + RAIL_SPACING) // (extent + RAIL_SPACING))
        shown = [tool for tool in self._recent if tool in self._buttons][:fit]
        for tool, button in self._buttons.items():
            if tool not in shown:
                button.hide()
        for idx, tool in enumerate(shown):
            offset = idx * (extent + RAIL_SPACING)
            button = self._buttons[tool]
            button.move(QPoint(0 if self._side else offset, offset if self._side else 0))
            button.show()

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:  # pylint: disable=invalid-name
        """Shows as many buttons as the new size fits."""
        super().resizeEvent(event)
        self._layout_buttons()


class _RailRule(QFrame):
    """The rule between a rail's upper and lower dock groups."""

    def __init__(self) -> None:
        super().__init__()
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)

    def set_side(self, side: bool) -> None:
        """Sets whether the rule is horizontal, between rows of a side rail, or vertical."""
        self.setFrameShape(QFrame.Shape.HLine if side else QFrame.Shape.VLine)


class DockRail(QToolBar):
    """The rail along one window edge. Its content is one widget laid out along the rail."""

    def __init__(self, window: QMainWindow, area: Qt.DockWidgetArea, object_name: str) -> None:
        super().__init__(window)
        self.setObjectName(object_name)
        self._area = area
        self._side = area in (Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea)
        self.setMovable(False)
        self.setFloatable(False)
        self.setAllowedAreas(toolbar_area_for(area))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self._content = QWidget()
        # The toolbar gives a widget more than its size hint only along the rail, and only if it expands there:
        self._content.setSizePolicy(QSizePolicy.Policy.Preferred if self._side else QSizePolicy.Policy.Expanding,
                                    QSizePolicy.Policy.Expanding if self._side else QSizePolicy.Policy.Preferred)
        direction = QBoxLayout.Direction.TopToBottom if self._side else QBoxLayout.Direction.LeftToRight
        self._layout = QVBoxLayout(self._content) if self._side else QHBoxLayout(self._content)
        self._layout.setDirection(direction)
        self._layout.setContentsMargins(QMargins(0, 2, 0, 2) if self._side else QMargins(2, 0, 2, 0))
        self._layout.setSpacing(RAIL_SPACING)
        self._rule = _RailRule()
        self._rule.set_side(self._side)
        self._buttons: list[tuple[DockGroup, RailButton]] = []
        self._recent_strip: Optional[RecentToolStrip] = None
        self._generate_button: Optional[QPushButton] = None
        self._stretch_index = -1
        self.addWidget(self._content)
        self.hide()

    @property
    def area(self) -> Qt.DockWidgetArea:
        """Returns the window edge the rail is on."""
        return self._area

    @property
    def is_side(self) -> bool:
        """Returns whether the rail runs along a left or right edge."""
        return self._side

    @property
    def buttons(self) -> list[RailButton]:
        """Returns the dock buttons in the rail, upper group first."""
        return [button for _group, button in self._buttons]

    @property
    def recent_tools(self) -> Optional[RecentToolStrip]:
        """Returns the recent tools strip if it is in this rail."""
        return self._recent_strip

    @property
    def generate_button(self) -> Optional[QPushButton]:
        """Returns the Generate button if it is in this rail."""
        return self._generate_button

    def _edge(self) -> Qt.Edge:
        return {
            Qt.DockWidgetArea.LeftDockWidgetArea: Qt.Edge.RightEdge,
            Qt.DockWidgetArea.RightDockWidgetArea: Qt.Edge.LeftEdge,
            Qt.DockWidgetArea.TopDockWidgetArea: Qt.Edge.BottomEdge,
            Qt.DockWidgetArea.BottomDockWidgetArea: Qt.Edge.TopEdge,
        }[self._area]

    def set_contents(self, buttons: list[tuple[DockGroup, RailButton]], recent: Optional[RecentToolStrip],
                     generate: Optional[QPushButton]) -> None:
        """Replaces the rail's contents: dock buttons grouped, then the recent tools, then Generate."""
        # Takes every item, including the spacer an earlier call added:
        while self._layout.count() > 0:
            item = self._layout.takeAt(0)
            if item is not None and item.widget() is not None and item.widget() is not self._rule:
                item.widget().hide()
        self._buttons = list(buttons)
        self._recent_strip = recent
        self._generate_button = generate
        for group in DockGroup:
            members = [button for button_group, button in buttons if button_group == group]
            for button in members:
                button.set_placement(self._side, self._edge())
                self._layout.addWidget(button, 0, self._alignment())
                button.setVisible(button.dock.is_available)
            if group == DockGroup.UPPER:
                self._layout.addWidget(self._rule)
        if recent is not None:
            recent.set_side(self._side)
            self._layout.addWidget(recent, 1)
            recent.show()
        else:
            self._layout.addStretch(1)
        if generate is not None:
            self._layout.addWidget(generate, 0, self._alignment())
        self.refresh_visibility()

    def _alignment(self) -> Qt.AlignmentFlag:
        return Qt.AlignmentFlag.AlignHCenter if self._side else Qt.AlignmentFlag.AlignVCenter

    def refresh_visibility(self, suspended: bool = False) -> None:
        """Shows the rule only between two groups that both have a visible button, and the rail only when it has a
        visible button, recent tool or Generate button and is not suspended."""
        visible_groups = {group for group, button in self._buttons if button.dock.is_available}
        self._rule.setVisible(len(visible_groups) == 2)
        has_content = len(visible_groups) > 0 or self._recent_strip is not None \
            or (self._generate_button is not None and not self._generate_button.isHidden())
        self.setVisible(has_content and not suspended)


class DockRails:
    """Owns the four `DockRail`s of a main window and keeps each dock's button in the rail of its area."""

    def __init__(self, window: QMainWindow) -> None:
        self._window = window
        self._rails: dict[Qt.DockWidgetArea, DockRail] = {}
        for area, name in ((Qt.DockWidgetArea.LeftDockWidgetArea, 'left_rail'),
                           (Qt.DockWidgetArea.RightDockWidgetArea, 'right_rail'),
                           (Qt.DockWidgetArea.TopDockWidgetArea, 'top_rail'),
                           (Qt.DockWidgetArea.BottomDockWidgetArea, 'bottom_rail')):
            rail = DockRail(window, area, name)
            self._rails[area] = rail
            window.addToolBar(toolbar_area_for(area), rail)
        self._docks: list[tuple[DockGroup, PanelDock, RailButton]] = []
        self._dock_areas: dict[PanelDock, Qt.DockWidgetArea] = {}
        self._tools_dock: Optional[PanelDock] = None
        self._generation_dock: Optional[PanelDock] = None
        self._recent_strip: Optional[RecentToolStrip] = None
        self._suspended = False
        self._generate_button = _GenerateButton(GENERATE_BUTTON_TEXT)
        self._generate_button.setIcon(QIcon(ICON_PATH_GENERATE))
        self._generate_button.setIconSize(QSize(SIDE_ICON_SIZE, SIDE_ICON_SIZE))
        set_primary_button(self._generate_button)
        set_shortcut_tooltip(self._generate_button, GENERATE_BUTTON_TOOLTIP, KeyConfig.GENERATE_SHORTCUT)
        self._generate_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._generate_button.hide()
        AppStateTracker.set_enabled_states(self._generate_button, [APP_STATE_EDITING])

    @property
    def generate_button(self) -> QPushButton:
        """Returns the Generate button."""
        return self._generate_button

    @property
    def recent_tools(self) -> Optional[RecentToolStrip]:
        """Returns the recent tools strip, or None before a tool controller is set."""
        return self._recent_strip

    def rail(self, area: Qt.DockWidgetArea) -> DockRail:
        """Returns the rail on one window edge."""
        return self._rails[area]

    def rail_for(self, dock: PanelDock) -> DockRail:
        """Returns the rail holding a registered dock's button."""
        return self._rails[self._dock_areas[dock]]

    def add_dock(self, dock: PanelDock, group: DockGroup,
                 default_area: Qt.DockWidgetArea = Qt.DockWidgetArea.RightDockWidgetArea) -> RailButton:
        """Adds a button for a dock, in the rail of the dock's area."""
        button = RailButton(dock)
        self._docks.append((group, dock, button))
        self._dock_areas[dock] = default_area
        dock.dockLocationChanged.connect(lambda area, moved=dock: self._dock_moved(moved, area))
        dock.toggleViewAction().changed.connect(self._refresh)
        self.sync()
        return button

    def set_tools_dock(self, dock: PanelDock) -> None:
        """Puts the recent tools in the rail of this dock."""
        self._tools_dock = dock
        self.sync()

    def set_generation_dock(self, dock: PanelDock) -> None:
        """Puts the Generate button in the rail of this dock, shown while the dock is not showing."""
        self._generation_dock = dock
        dock.visibilityChanged.connect(self._refresh)
        dock.toggleViewAction().changed.connect(self._refresh)
        self.sync()

    def set_tool_controller(self, tool_controller: ToolController) -> None:
        """Creates the recent tools strip for a tool controller, replacing any earlier one."""
        if self._recent_strip is not None:
            self._recent_strip.setParent(None)
            self._recent_strip.deleteLater()
        self._recent_strip = RecentToolStrip(tool_controller)
        self.sync()

    def _dock_moved(self, dock: PanelDock, area: Qt.DockWidgetArea) -> None:
        if area in self._rails and area != self._dock_areas[dock]:
            self._dock_areas[dock] = area
            self.sync()

    def sync(self) -> None:
        """Moves each button to the rail of its dock's current area. Call after a layout change Qt doesn't report with
        `dockLocationChanged`, such as `restoreState`."""
        for _group, dock, _button in self._docks:
            area = self._window.dockWidgetArea(dock)
            if area in self._rails:
                self._dock_areas[dock] = area
        for area, rail in self._rails.items():
            buttons = [(group, button) for group, dock, button in self._docks if self._dock_areas[dock] == area]
            recent = self._recent_strip if self._tools_dock is not None \
                and self._dock_areas.get(self._tools_dock) == area else None
            generate = self._generate_button if self._generation_dock is not None \
                and self._dock_areas.get(self._generation_dock) == area else None
            rail.set_contents(buttons, recent, generate)
        self._refresh()

    def _refresh(self, *_args) -> None:
        """Updates which buttons, rules and rails are visible."""
        for _group, dock, button in self._docks:
            button.setVisible(dock.is_available)
        if self._generation_dock is not None:
            dock = self._generation_dock
            self._generate_button.setVisible(dock.is_available and not dock.is_showing)
            icon_only = self.rail_for(dock).is_side
            self._generate_button.icon_only = icon_only
            self._generate_button.setText('' if icon_only else GENERATE_BUTTON_TEXT)
            self._generate_button.updateGeometry()
        for rail in self._rails.values():
            rail.refresh_visibility(self._suspended)

    def set_suspended(self, suspended: bool) -> None:
        """Hides every rail while true, as when the generated image selector fills the window."""
        self._suspended = suspended
        self._refresh()
