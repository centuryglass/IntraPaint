"""Icon rails along the main window's edges, with one button per `PanelDock`, the recent tools and Generate.

- Each window edge has a `DockRail`, a non-movable `QToolBar`. A dock's button sits in the rail of the area the dock was
  last docked in, so it follows the dock between edges. An open floating dock's button is in its title bar instead
  (`FloatingTitleBar`), and returns to the rail of its last area when the dock closes.
- Side rails (left and right) are `SIDE_RAIL_WIDTH` wide, with an icon and keycap per button. Strip rails (top and
  bottom) show icon, name and keycap.
- The buttons act as the docks' tabs. Clicking a button opens its dock in place of the open dock of its tab group, or
  closes it if it is showing (`PanelDock.toggle_from_key`). A dock with no content has no button.
- A rail groups its buttons by tab group and lines each group up with its docks (see `DockRail`).
- The recent tools sit after the Tools dock's group, and Generate at the end of the Image Generation dock's rail. The
  recent tools fill only the space the other buttons leave, so they never raise the window's minimum size. Their
  maximum count is `AppConfig.TOOLBAR_TOOL_BUTTON_COUNT`.
"""
from typing import Optional

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPaintEvent, QPalette, QPen, QResizeEvent
from PySide6.QtWidgets import (QApplication, QFrame, QMainWindow, QPushButton, QSizePolicy, QToolBar, QToolButton,
                               QWidget)

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.controller.tool_controller import ToolController
from src.tools.base_tool import BaseTool
from src.ui.ink_style import set_primary_button
from src.ui.widget.shortcut_tooltip import set_shortcut_tooltip
from src.ui.widget.tool_button import ToolButton
from src.ui.window.dock_groups import docked_groups
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
# A dock's badge is a pill this tall that overhangs the icon's upper right corner:
BADGE_SIZE = 12
BADGE_FONT_PIXELS = 9
BADGE_TEXT_PADDING = 3
BADGE_OVERHANG = 4
# Space between a rail's ends and its first and last items:
RAIL_MARGIN = 2
# Space before each dock group after a rail's first, with a rule across its middle:
RULE_SPACE = 7
RULE_WIDTH = 3
# Space between a rule's ends and the rail's sides:
RULE_INSET = 4


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
        self._refresh_tooltip = set_shortcut_tooltip(self, dock.windowTitle(), dock.shortcut_config_key,
                                                     lambda: dock.badge_tooltip if self.badge_text != '' else '')
        dock.visibilityChanged.connect(self.setChecked)
        dock.visibilityChanged.connect(self._badge_changed)
        dock.badge_changed.connect(self._badge_changed)
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

    @property
    def badge_text(self) -> str:
        """The dock's badge text while this button shows it: the dock is not showing and has a badge. Otherwise ''."""
        return '' if self._dock.is_showing else self._dock.badge_text

    def _badge_changed(self, *_args) -> None:
        self._refresh_tooltip()
        self.update()

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
        self._draw_badge(painter, icon_rect, highlight)
        painter.end()

    def _draw_badge(self, painter: QPainter, icon_rect: QRect, accent: QColor) -> None:
        """Draws `badge_text` in an accent pill over the icon's upper right corner, if there is any."""
        text = self.badge_text
        if text == '':
            return
        font = QFont(self.font())
        font.setBold(True)
        font.setPixelSize(BADGE_FONT_PIXELS)
        metrics = QFontMetrics(font)
        width = max(BADGE_SIZE, metrics.horizontalAdvance(text) + 2 * BADGE_TEXT_PADDING)
        right = min(icon_rect.right() + BADGE_OVERHANG, self.width() - 1)
        bounds = QRectF(right - width + 1, max(0, icon_rect.top() - BADGE_OVERHANG), width, BADGE_SIZE)
        palette = self.palette()
        painter.setPen(QPen(palette.color(QPalette.ColorRole.Window), 1))
        painter.setBrush(accent)
        painter.drawRoundedRect(bounds, BADGE_SIZE / 2, BADGE_SIZE / 2)
        painter.setPen(palette.color(QPalette.ColorRole.HighlightedText))
        painter.setFont(font)
        painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter, text)

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
    """The rule at the start of each of a rail's dock groups after the first."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)

    def set_side(self, side: bool) -> None:
        """Sets whether the rule is horizontal, between rows of a side rail, or vertical."""
        self.setFrameShape(QFrame.Shape.HLine if side else QFrame.Shape.VLine)


class _RailContent(QWidget):
    """The widget a rail holds, which its rail lays out along the rail (`DockRail.place`)."""

    def __init__(self, rail: 'DockRail') -> None:
        super().__init__()
        self._rail = rail

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns room for every button, rule and the maximum number of recent tools."""
        return self._rail.content_size(with_recent_tools=True)

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns room for every button and rule, without recent tools."""
        return self._rail.content_size(with_recent_tools=False)

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:  # pylint: disable=invalid-name
        """Places the rail's contents for the new length."""
        super().resizeEvent(event)
        self._rail.place()


class DockRail(QToolBar):
    """The rail along one window edge. It places its dock buttons by tab group, then its recent tools and Generate.

    - Each group's buttons start where the group's open dock starts along the rail, so a split area's groups line up
      with their docks. A rule marks the start of each group after the first.
    - A group with no open dock, or one whose start would overlap the group before it, follows the group before it.
      A group that would run past the rail's end moves back to end there. When the groups still don't fit, they are
      packed from the rail's start.
    - The recent tools fill the space between the Tools dock's group and the next group. Generate is at the rail's end.
    """

    def __init__(self, window: QMainWindow, area: Qt.DockWidgetArea, object_name: str) -> None:
        super().__init__(window)
        self.setObjectName(object_name)
        self._window = window
        self._area = area
        self._side = area in (Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea)
        self.setMovable(False)
        self.setFloatable(False)
        self.setAllowedAreas(toolbar_area_for(area))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self._content = _RailContent(self)
        # The toolbar gives a widget more than its size hint only along the rail, and only if it expands there:
        self._content.setSizePolicy(QSizePolicy.Policy.Preferred if self._side else QSizePolicy.Policy.Expanding,
                                    QSizePolicy.Policy.Expanding if self._side else QSizePolicy.Policy.Preferred)
        self._groups: list[list[RailButton]] = []
        self._rules: list[_RailRule] = []
        self._recent_strip: Optional[RecentToolStrip] = None
        self._recent_group = -1
        self._generate_button: Optional[QPushButton] = None
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
        """Returns the dock buttons in the rail, group by group."""
        return [button for group in self._groups for button in group]

    @property
    def groups(self) -> list[list[RailButton]]:
        """Returns the rail's dock buttons by tab group, in rail order."""
        return [list(group) for group in self._groups]

    @property
    def content(self) -> QWidget:
        """Returns the widget holding the rail's buttons, which positions along the rail are measured in."""
        return self._content

    @property
    def rules(self) -> list[QFrame]:
        """Returns the rules between groups that are showing."""
        return [rule for rule in self._rules if not rule.isHidden()]

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

    def set_contents(self, groups: list[list[RailButton]], recent: Optional[RecentToolStrip],
                     recent_group: int, generate: Optional[QPushButton]) -> None:
        """Replaces the rail's contents: dock buttons by tab group, the recent tools after group `recent_group`, and
        Generate."""
        for widget in (*self.buttons, self._recent_strip, self._generate_button):
            if widget is not None and widget.parentWidget() is self._content:
                widget.hide()
        self._groups = [list(group) for group in groups]
        self._recent_strip = recent
        self._recent_group = recent_group
        self._generate_button = generate
        for button in self.buttons:
            button.setParent(self._content)
            button.set_placement(self._side, self._edge())
        if recent is not None:
            recent.setParent(self._content)
            recent.set_side(self._side)
        if generate is not None:
            generate.setParent(self._content)
        while len(self._rules) < len(self._groups):
            rule = _RailRule(self._content)
            rule.set_side(self._side)
            self._rules.append(rule)
        self._content.updateGeometry()
        self.refresh_visibility()

    def _shown_groups(self) -> list[tuple[int, list[RailButton]]]:
        """Returns each group's index and its buttons with content, leaving out groups with none."""
        groups = [(idx, [button for button in group if button.dock.is_available])
                  for idx, group in enumerate(self._groups)]
        return [(idx, group) for idx, group in groups if len(group) > 0]

    def _length(self, widget: QWidget) -> int:
        hint = widget.sizeHint()
        return hint.height() if self._side else hint.width()

    def _breadth(self, widget: QWidget) -> int:
        hint = widget.sizeHint()
        return hint.width() if self._side else hint.height()

    def _generate_shown(self) -> bool:
        return self._generate_button is not None and not self._generate_button.isHidden()

    def content_size(self, with_recent_tools: bool) -> QSize:
        """Returns the length every button and rule needs, with the recent tools' size hint if requested, and the
        breadth of the widest item."""
        groups = self._shown_groups()
        widgets: list[QWidget] = [button for _idx, group in groups for button in group]
        if self._generate_shown():
            assert self._generate_button is not None
            widgets.append(self._generate_button)
        length = 2 * RAIL_MARGIN + sum(self._length(widget) for widget in widgets) \
            + RAIL_SPACING * max(len(widgets) - 1, 0) + RULE_SPACE * max(len(groups) - 1, 0)
        breadth = max((self._breadth(widget) for widget in widgets), default=0)
        if with_recent_tools and self._recent_strip is not None:
            length += self._length(self._recent_strip) + RAIL_SPACING
            breadth = max(breadth, self._breadth(self._recent_strip))
        if self._side:
            return QSize(max(breadth, SIDE_RAIL_WIDTH), length)
        return QSize(length, breadth)

    def _span_start(self, group: list[RailButton]) -> Optional[int]:
        """Returns where the group's open docked dock starts along the rail, or None if it has none."""
        dock = next((button.dock for button in group if not button.dock.isHidden() and not button.dock.isFloating()),
                    None)
        if dock is None or not dock.isVisible():
            return None
        start = self._content.mapFrom(self._window, dock.geometry().topLeft())
        return start.y() if self._side else start.x()

    def _group_length(self, group: list[RailButton]) -> int:
        return sum(self._length(button) for button in group) + RAIL_SPACING * (len(group) - 1)

    def _group_starts(self, groups: list[list[RailButton]], end: int) -> list[int]:
        """Returns where each group's buttons start: at its dock's start, after the group before it, and pulled back
        from the rail's end as far as that allows. Packs the groups from the rail's start if they still don't fit."""
        starts = []
        cursor = RAIL_MARGIN
        for idx, group in enumerate(groups):
            earliest = cursor if idx == 0 else cursor + RULE_SPACE
            span_start = self._span_start(group)
            start = earliest if span_start is None else max(earliest, span_start)
            starts.append(start)
            cursor = start + self._group_length(group)
        latest = end
        for idx in reversed(range(len(groups))):
            starts[idx] = min(starts[idx], latest - self._group_length(groups[idx]))
            latest = starts[idx] - RULE_SPACE
        cursor = RAIL_MARGIN
        for idx, group in enumerate(groups):
            if starts[idx] < (cursor if idx == 0 else cursor + RULE_SPACE):
                return self._packed_starts(groups)
            cursor = starts[idx] + self._group_length(group)
        return starts

    def _packed_starts(self, groups: list[list[RailButton]]) -> list[int]:
        starts = []
        cursor = RAIL_MARGIN
        for idx, group in enumerate(groups):
            start = cursor if idx == 0 else cursor + RULE_SPACE
            starts.append(start)
            cursor = start + self._group_length(group)
        return starts

    def place(self) -> None:
        """Places the buttons, rules, recent tools and Generate along the rail's current length."""
        length = self._content.height() if self._side else self._content.width()
        breadth = self._content.width() if self._side else self._content.height()
        end = length - RAIL_MARGIN
        if self._generate_shown():
            assert self._generate_button is not None
            generate_length = self._length(self._generate_button)
            end -= generate_length
            self._place(self._generate_button, end, generate_length, breadth)
            end -= RAIL_SPACING
        shown = self._shown_groups()
        starts = self._group_starts([group for _idx, group in shown], end)
        for rule in self._rules:
            rule.hide()
        recent_start: Optional[int] = None
        recent_end = end
        for position, ((idx, group), start) in enumerate(zip(shown, starts)):
            if position > 0:
                rule = self._rules[position - 1]
                self._place(rule, start - (RULE_SPACE + RULE_WIDTH) // 2, RULE_WIDTH, breadth - 2 * RULE_INSET,
                            RULE_INSET)
                rule.show()
                if recent_start is not None and recent_end == end:
                    recent_end = start - RULE_SPACE
            cursor = start
            for button in group:
                button_length = self._length(button)
                self._place(button, cursor, button_length, breadth)
                cursor += button_length + RAIL_SPACING
            if idx == self._recent_group:
                recent_start = cursor
        if self._recent_strip is not None:
            if recent_start is None:
                recent_start = RAIL_MARGIN if len(shown) == 0 else max(starts[-1], RAIL_MARGIN)
            self._place(self._recent_strip, recent_start, max(recent_end - recent_start, 0), breadth)

    def _place(self, widget: QWidget, start: int, length: int, breadth: int, offset: Optional[int] = None) -> None:
        """Sets a widget's geometry along the rail, centered across it unless `offset` is given."""
        widget_breadth = min(self._breadth(widget), breadth) if offset is None else breadth
        across = (breadth - widget_breadth) // 2 if offset is None else offset
        if self._side:
            widget.setGeometry(QRect(across, start, widget_breadth, length))
        else:
            widget.setGeometry(QRect(start, across, length, widget_breadth))

    def refresh_visibility(self, suspended: bool = False) -> None:
        """Shows each button with content, and the rail only when it has a visible button, recent tool or Generate
        button and is not suspended. Then places the contents."""
        for button in self.buttons:
            button.setVisible(button.dock.is_available)
        if self._recent_strip is not None:
            self._recent_strip.show()
        has_content = len(self._shown_groups()) > 0 or self._recent_strip is not None or self._generate_shown()
        self.setVisible(has_content and not suspended)
        self._content.updateGeometry()
        self.place()


class DockRails(QObject):
    """Owns the four `DockRail`s of a main window and keeps each dock's button in the rail of its area.

    Buttons are grouped by the docks' tab groups (`docked_groups`). The rails are placed again whenever a dock moves,
    resizes, opens or closes.
    """

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self._window = window
        self._rails: dict[Qt.DockWidgetArea, DockRail] = {}
        for area, name in ((Qt.DockWidgetArea.LeftDockWidgetArea, 'left_rail'),
                           (Qt.DockWidgetArea.RightDockWidgetArea, 'right_rail'),
                           (Qt.DockWidgetArea.TopDockWidgetArea, 'top_rail'),
                           (Qt.DockWidgetArea.BottomDockWidgetArea, 'bottom_rail')):
            rail = DockRail(window, area, name)
            self._rails[area] = rail
            window.addToolBar(toolbar_area_for(area), rail)
        self._docks: list[tuple[PanelDock, RailButton]] = []
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

    def add_dock(self, dock: PanelDock,
                 default_area: Qt.DockWidgetArea = Qt.DockWidgetArea.RightDockWidgetArea) -> RailButton:
        """Adds a button for a dock, in the rail of the dock's area."""
        button = RailButton(dock)
        self._docks.append((dock, button))
        self._dock_areas[dock] = default_area
        dock.dockLocationChanged.connect(lambda area, moved=dock: self._dock_moved(moved, area))
        dock.toggleViewAction().changed.connect(self.sync)
        dock.topLevelChanged.connect(self.sync)
        dock.installEventFilter(self)
        self.sync()
        return button

    def set_tools_dock(self, dock: PanelDock) -> None:
        """Puts the recent tools in the rail of this dock, after its group's buttons."""
        self._tools_dock = dock
        self.sync()

    def set_generation_dock(self, dock: PanelDock) -> None:
        """Puts the Generate button in the rail of this dock, shown while the dock is not showing."""
        self._generation_dock = dock
        dock.visibilityChanged.connect(self._refresh)
        self.sync()

    def set_tool_controller(self, tool_controller: ToolController) -> None:
        """Creates the recent tools strip for a tool controller, replacing any earlier one."""
        if self._recent_strip is not None:
            self._recent_strip.setParent(None)
            self._recent_strip.deleteLater()
        self._recent_strip = RecentToolStrip(tool_controller)
        self.sync()

    def eventFilter(self, _watched: QObject, event: QEvent) -> bool:  # pylint: disable=invalid-name
        """Places the rails again when a dock moves or resizes."""
        if event.type() in (QEvent.Type.Move, QEvent.Type.Resize) and not self._suspended:
            for rail in self._rails.values():
                if rail.isVisible():
                    rail.place()
        return False

    def _dock_moved(self, dock: PanelDock, area: Qt.DockWidgetArea) -> None:
        if area in self._rails:
            self._dock_areas[dock] = area
        self.sync()

    def sync(self, *_args) -> None:
        """Moves each button to the rail of its dock's current area, grouped by tab group. Call after a layout change
        Qt doesn't report with `dockLocationChanged`, such as `addDockWidget` or `restoreState`."""
        for dock, _button in self._docks:
            area = self._window.dockWidgetArea(dock)
            if area in self._rails:
                self._dock_areas[dock] = area
        buttons = dict(self._docks)
        groups = docked_groups(self._window, [dock for dock, _button in self._docks], with_empty=True)
        grouped = {dock for group in groups for dock in group}
        # An open floating dock's button is in its title bar (`FloatingTitleBar`). Closed floating docks follow the
        # groups of the area they were last docked in, each alone:
        groups += [[dock] for dock, _button in self._docks
                   if dock not in grouped and not (dock.isFloating() and not dock.isHidden())]
        for area, rail in self._rails.items():
            rail_groups = [[buttons[dock] for dock in group] for group in groups
                           if self._dock_areas[group[0]] == area]
            recent_group = -1
            if self._tools_dock is not None and self._dock_areas.get(self._tools_dock) == area:
                recent_group = next((idx for idx, group in enumerate(rail_groups)
                                     if any(button.dock is self._tools_dock for button in group)), -1)
            recent = self._recent_strip if recent_group >= 0 else None
            generate = self._generate_button if self._generation_dock is not None \
                and self._dock_areas.get(self._generation_dock) == area else None
            rail.set_contents(rail_groups, recent, recent_group, generate)
        self._refresh()

    def _refresh(self, *_args) -> None:
        """Updates which buttons and rails are visible, and places each rail's contents."""
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
