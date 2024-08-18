"""Add text to an image."""
from typing import Optional

from PySide6.QtCore import QPoint
from PySide6.QtGui import QIcon, QKeySequence, QMouseEvent, Qt
from PySide6.QtWidgets import QWidget, QApplication

from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.text_layer import TextLayer
from src.image.text_rect import TextRect
from src.tools.base_tool import BaseTool
from src.ui.graphics_items.click_and_drag_selection import ClickAndDragSelection
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.text_tool_panel import TextToolPanel
from src.util.shared_constants import PROJECT_DIR

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.text_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


RESOURCES_TEXT_ICON = f'{PROJECT_DIR}/resources/icons/tools/text_icon.svg'
CURSOR_SIZE = 50

TEXT_LABEL = _tr('Text')
TEXT_TOOLTIP = _tr('Add text to a text layer')
TEXT_CONTROL_HINT = _tr('TODO: text controls')


class TextTool(BaseTool):
    """Lets the user fill image areas with solid colors."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        super().__init__()
        scene = image_viewer.scene()
        assert scene is not None
        self._scene = scene
        self._control_panel = TextToolPanel()
        self._image_stack = image_stack
        self._text_layer: Optional[TextLayer] = None
        self._selection_handler = ClickAndDragSelection(scene)
        self._dragging = False
        self._icon = QIcon(RESOURCES_TEXT_ICON)
        self._control_panel.text_rect_changed.connect(self._update_layer_text_slot)
        image_stack.active_layer_changed.connect(self._active_layer_change_slot)

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return KeyConfig().get_keycodes(KeyConfig.TEXT_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return TEXT_LABEL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return TEXT_TOOLTIP

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        return (f'{TEXT_CONTROL_HINT}'
                f'{super().get_input_hint()}')

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        return self._control_panel

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Updates text placement or selects a text layer on click."""
        assert event is not None
        if self._text_layer is not None:
            if event.buttons() == Qt.MouseButton.LeftButton:
                self._update_position(image_coordinates)
                return True
            if event.buttons() == Qt.MouseButton.RightButton:
                self._update_size(image_coordinates)
                return True
        else:
            clicked_layer = self._image_stack.top_layer_at_point(image_coordinates)
            if isinstance(clicked_layer, TextLayer):
                self._image_stack.active_layer = clicked_layer
                return True
        return False

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Updates text placement while dragging when a text layer is active."""
        assert event is not None
        if self._text_layer is not None:
            if event.buttons() == Qt.MouseButton.LeftButton:
                self._update_position(image_coordinates)
                return True
            if event.buttons() == Qt.MouseButton.RightButton:
                self._update_size(image_coordinates)
                return True
        return False

    def _update_position(self, image_coordinates: QPoint) -> None:
        text_data = self._control_panel.text_rect
        text_bounds = text_data.bounds
        if image_coordinates != text_bounds.topLeft():
            text_bounds.moveTopLeft(image_coordinates)
            text_data.bounds = text_bounds
            self._control_panel.text_rect = text_data

    def _update_size(self, image_coordinates: QPoint) -> None:
        text_data = self._control_panel.text_rect
        text_bounds = text_data.bounds
        bottom_right = text_bounds.topLeft() + QPoint(text_bounds.width(), text_bounds.height())
        if image_coordinates != bottom_right:
            text_bounds.setWidth(max(0, image_coordinates.x() - text_bounds.x()))
            text_bounds.setHeight(max(0, image_coordinates.y() - text_bounds.y()))
            text_data.bounds = text_bounds
            self._control_panel.text_rect = text_data

    def _create_and_activate_text_layer(self, layer_data: Optional[TextRect]) -> None:
        self._text_layer = self._image_stack.create_text_layer(layer_data)
        self._image_stack.active_layer = self._text_layer

    def _update_layer_text_slot(self, text_data: TextRect) -> None:
        if not self.is_active:
            return
        if len(text_data.text) > 0 and self._text_layer is None:
            self._create_and_activate_text_layer(text_data)
        elif self._text_layer is not None:
            self._text_layer.set_text_rect(text_data)

    def _active_layer_change_slot(self, active_layer: Layer) -> None:
        if isinstance(active_layer, TextLayer):
            self._text_layer = active_layer
            self._control_panel.text_rect = active_layer.text_rect
            if self.is_active and self._control_panel.isVisible():
                self._control_panel.focus_text_input()
        else:
            self._text_layer = None
            self._control_panel.text_rect = TextRect()
