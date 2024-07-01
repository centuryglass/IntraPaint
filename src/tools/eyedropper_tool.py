"""Samples colors within the image, setting brush color."""
from typing import Optional

from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QIcon, QCursor, QColor, QMouseEvent, QKeySequence, QResizeEvent, QShowEvent
from PyQt5.QtWidgets import QWidget, QColorDialog

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.image_stack import ImageStack
from src.tools.base_tool import BaseTool
from src.ui.widget.color_picker import ColorPicker
from src.util.display_size import get_window_size

RESOURCES_EYEDROPPER_ICON = 'resources/icons/eyedropper_icon.svg'
RESOURCES_EYEDROPPER_CURSOR = 'resources/cursors/eyedropper_cursor.svg'
CURSOR_SIZE = 50

EYEDROPPER_LABEL = 'Color Picker'
EYEDROPPER_TOOLTIP = "Select a brush color"
EYEDROPPER_CONTROL_HINT = "LMB:pick color -"


class EyedropperTool(BaseTool):
    """Lets the user select colors from the scene or pick a color."""

    def __init__(self, image_stack: ImageStack) -> None:
        super().__init__()
        self._image_stack = image_stack
        self._control_panel: Optional[QColorDialog] = None
        self._icon = QIcon(RESOURCES_EYEDROPPER_ICON)
        cursor_icon = QIcon(RESOURCES_EYEDROPPER_CURSOR)
        self.cursor = QCursor(cursor_icon.pixmap(CURSOR_SIZE, CURSOR_SIZE), 0, CURSOR_SIZE)

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return KeyConfig().get_keycodes(KeyConfig.EYEDROPPER_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return EYEDROPPER_LABEL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return EYEDROPPER_TOOLTIP

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        return f'{EYEDROPPER_CONTROL_HINT} {super().get_input_hint()}'

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        if self._control_panel is not None:
            return self._control_panel
        self._control_panel = _ControlPanel()
        return self._control_panel

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Copy the color under the mouse on left-click."""
        assert event is not None
        if event.buttons() == Qt.LeftButton:
            color = self._image_stack.get_color_at_point(image_coordinates)
            Cache().set(Cache.LAST_BRUSH_COLOR, color.name(QColor.HexArgb))
            return True
        return False


class _ControlPanel(ColorPicker):

    def __init__(self) -> None:
        super().__init__()
        self._orientation = Qt.Orientation.Horizontal
        cache = Cache()

        initial_color = QColor(cache.get(Cache.LAST_BRUSH_COLOR))
        self.setCurrentColor(initial_color)
        cache.connect(self, Cache.LAST_BRUSH_COLOR, self._apply_config_color)
        self.currentColorChanged.connect(_update_config_color)

    def _apply_config_color(self, color_str: str) -> None:
        self.setCurrentColor(QColor(color_str))

    def set_orientation(self, orientation: Qt.Orientation):
        """Update the panel layout based on window size and requested orientation."""
        self._orientation = orientation
        window_size = get_window_size()
        panel_size = self.panel_size()
        if orientation == Qt.Orientation.Vertical:
            if window_size.height() > panel_size.height() * 6:
                self.set_vertical_mode()
            elif window_size.height() > panel_size.height() * 4:
                self.set_vertical_two_tab_mode()
            else:
                self.set_four_tab_mode()
        elif orientation == Qt.Orientation.Horizontal:
            if window_size.width() > panel_size.width() * 6:
                self.set_horizontal_mode()
            elif window_size.width() > panel_size.width() * 4:
                self.set_horizontal_two_tab_mode()
            else:
                self.set_four_tab_mode()

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Re-apply layout on size change."""
        self.set_orientation(self._orientation)

    def showEvent(self, event: Optional[QShowEvent]) -> None:
        """Re-apply layout whenever the panel is shown."""
        self.set_orientation(self._orientation)


def _update_config_color(color: QColor) -> None:
    cache = Cache()
    cache.set(Cache.LAST_BRUSH_COLOR, color.name(QColor.HexArgb))
