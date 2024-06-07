"""An image editing tool that moves the selected editing region."""

from typing import Optional

from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QMouseEvent, QKeyEvent, QCursor, QIcon
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication, QLabel

from src.config.application_config import AppConfig
from src.image.layer_stack import LayerStack
from src.tools.base_tool import BaseTool
from src.ui.image_viewer import ImageViewer

RESOURCES_SELECTION_ICON = 'resources/layer_transform.svg'
TRANSFORM_LABEL = 'Transform Layers'
TRANSFORM_TOOLTIP = 'Move, scale, or rotate the active layer.'


class LayerTransformTool(BaseTool):
    """Applies transformations to the active layer."""

    def __init__(self, layer_stack: LayerStack, image_viewer: ImageViewer, config: AppConfig) -> None:
        super().__init__()
        self._layer_stack = layer_stack
        self._image_viewer = image_viewer
        self._config = config
        self._icon = QIcon(RESOURCES_SELECTION_ICON)
        self.cursor = QCursor(Qt.CursorShape.OpenHandCursor)
        self._control_panel: Optional[QWidget] = None
        self._control_layout: Optional[QVBoxLayout] = None
        self._dragging = False
        self._initial_click_pos: Optional[QPoint] = None
        self._initial_layer_offset: Optional[QPoint] = None
        self._active_layer_idx = self._layer_stack.active_layer_index
        self._layer_stack.active_layer_changed.connect(self._handle_layer_change)

    def _handle_layer_change(self, _, layer_idx: int) -> None:
        if self._active_layer_idx != layer_idx:
            self._active_layer_idx = layer_idx
            self._dragging = False
            self._initial_click_pos = None
            self._initial_layer_offset = None

    def get_hotkey(self) -> Qt.Key:
        """Returns the hotkey that should activate this tool."""
        key = self._config.get_keycodes(AppConfig.TRANSFORM_TOOL_KEY)
        return key[0]

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return TRANSFORM_LABEL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return TRANSFORM_TOOLTIP

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        if self._control_panel is not None:
            return self._control_panel
        self._control_panel = QWidget()
        self._control_layout = QVBoxLayout(self._control_panel)
        self._control_layout.setSpacing(1)
        self._control_layout.addWidget(QLabel('TODO: switch between move, scale, and rotate'))
        return self._control_panel

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        if self._active_layer_idx is None or event.buttons() != Qt.LeftButton \
                or QApplication.keyboardModifiers() != Qt.KeyboardModifier.NoModifier:
            return False
        self._dragging = True
        self._initial_click_pos = image_coordinates
        self._initial_layer_offset = self._layer_stack.get_layer_by_index(self._active_layer_idx).position
        return True

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        if event.buttons() != Qt.LeftButton or not self._dragging or self._initial_click_pos is None\
                or self._initial_layer_offset is None:
            return False
        mouse_offset = image_coordinates - self._initial_click_pos
        layer = self._layer_stack.get_layer_by_index(self._active_layer_idx)
        layer.position = self._initial_layer_offset + mouse_offset
        return True

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        self._dragging = False
        self._initial_layer_offset = None
        self._initial_click_pos = None
        return True

    def key_event(self, event: Optional[QKeyEvent]) -> bool:
        """Move layer with arrow keys."""
        if self._active_layer_idx is None:
            return False
        translation = QPoint(0, 0)
        multiplier = 10 if QApplication.keyboardModifiers() == Qt.ShiftModifier else 1
        match event.key():
            case Qt.Key.Key_Left:
                translation.setX(-1 * multiplier)
            case Qt.Key.Key_Right:
                translation.setX(1 * multiplier)
            case Qt.Key.Key_Up:
                translation.setY(-1 * multiplier)
            case Qt.Key.Key_Down:
                translation.setY(1 * multiplier)
            case _:
                return False
        layer = self._layer_stack.get_layer_by_index(self._active_layer_idx)
        layer.position = layer.position + translation
        return True

