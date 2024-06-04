"""Samples colors within the image, setting brush color."""
from typing import Optional

from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QIcon, QCursor, QColor, QMouseEvent
from PyQt5.QtWidgets import QWidget, QColorDialog

from src.config.application_config import AppConfig
from src.image.layer_stack import LayerStack
from src.tools.base_tool import BaseTool

RESOURCES_EYEDROPPER_ICON = 'resources/eyedropper_icon.svg'
RESOURCES_EYEDROPPER_CURSOR = 'resources/eyedropper_cursor.svg'
CURSOR_SIZE = 50

EYEDROPPER_LABEL = 'Color Picker'
EYEDROPPER_TOOLTIP = "Select a brush color"


class EyedropperTool(BaseTool):
    """Lets the user select colors from the scene or pick a color."""

    def __init__(self, layer_stack: LayerStack, config: AppConfig) -> None:
        super().__init__()
        self._layer_stack = layer_stack
        self._config = config
        self._control_panel = None
        self._icon = QIcon(RESOURCES_EYEDROPPER_ICON)
        cursor_icon = QIcon(RESOURCES_EYEDROPPER_CURSOR)
        self.cursor = QCursor(cursor_icon.pixmap(CURSOR_SIZE, CURSOR_SIZE), 0, CURSOR_SIZE)

    def get_hotkey(self) -> Qt.Key:
        """Returns the hotkey that should activate this tool."""
        return Qt.Key.Key_E

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return EYEDROPPER_LABEL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return EYEDROPPER_TOOLTIP

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        if self._control_panel is not None:
            return self._control_panel
        self._control_panel = QColorDialog()
        self._control_panel.setOption(QColorDialog.ShowAlphaChannel, True)
        self._control_panel.setOption(QColorDialog.NoButtons, True)
        self._control_panel.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        initial_color = QColor(self._config.get(AppConfig.LAST_BRUSH_COLOR))
        self._control_panel.setCurrentColor(initial_color)
        self._config.connect(self._control_panel, AppConfig.LAST_BRUSH_COLOR,
                             lambda color_str: self._control_panel.setCurrentColor(QColor(color_str)))
        self._control_panel.currentColorChanged.connect(lambda color: self._config.set(AppConfig.LAST_BRUSH_COLOR,
                                                                                 color.name(QColor.HexArgb)))
        return self._control_panel

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Copy the color under the mouse on left-click."""
        if event.buttons() == Qt.LeftButton:
            color = self._layer_stack.get_color_at_point(image_coordinates)
            self._config.set(AppConfig.LAST_BRUSH_COLOR, color.name(QColor.HexArgb))
        return False
