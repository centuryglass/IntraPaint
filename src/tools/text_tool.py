"""Add text to an image."""
from typing import Optional

from PySide6.QtCore import QPoint, QPointF, QSizeF, QSize
from PySide6.QtGui import QIcon, QKeySequence, QMouseEvent, Qt, QTransform
from PySide6.QtWidgets import QWidget, QApplication

from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.text_layer import TextLayer
from src.image.layers.transform_layer import TransformLayer
from src.image.text_rect import TextRect
from src.tools.base_tool import BaseTool
from src.ui.graphics_items.click_and_drag_selection import ClickAndDragSelection
from src.ui.graphics_items.placement_outline import PlacementOutline
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.text_tool_panel import TextToolPanel
from src.undo_stack import UndoStack
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
        self._placement_outline: Optional[PlacementOutline] = None
        self._text_layer: Optional[TextLayer] = None
        self._selection_handler = ClickAndDragSelection(scene)
        self._dragging = False
        self._icon = QIcon(RESOURCES_TEXT_ICON)

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
            return False
        elif event.buttons() == Qt.MouseButton.LeftButton:
            clicked_layer = self._image_stack.top_layer_at_point(image_coordinates)
            if isinstance(clicked_layer, TextLayer):
                self._connect_text_layer(clicked_layer)
                return True
            else:
                self._dragging = True
                self._selection_handler.start_selection(image_coordinates)
        return False

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Updates text placement while dragging when a text layer is active."""
        assert event is not None
        if self._text_layer is not None:
            if self._dragging:
                self._selection_handler.end_selection(image_coordinates)
                self._dragging = False
            return False
        elif event.buttons() == Qt.MouseButton.LeftButton and self._dragging:
            self._selection_handler.drag_to(image_coordinates)
            return True
        elif self._dragging:
            self._selection_handler.end_selection(image_coordinates)
            self._dragging = False
            return True
        return False

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """If dragging, finish and create a new text layer."""
        if self._dragging:
            new_bounds = self._selection_handler.end_selection(image_coordinates).boundingRect().toAlignedRect()
            self._dragging = False
            self._control_panel.offset = new_bounds.topLeft()
            text_rect = self._control_panel.text_rect
            text_rect.size = new_bounds.size()
            self._control_panel.text_rect = text_rect
            self._create_and_activate_text_layer(text_rect, new_bounds.topLeft())
            return True
        return False

    def _on_activate(self) -> None:
        """Called when the tool becomes active, implement to handle any setup that needs to be done."""
        active_layer = self._image_stack.active_layer
        if isinstance(active_layer, TextLayer):
            self._connect_text_layer(active_layer)

    def _on_deactivate(self) -> None:
        """Called when the tool stops being active, implement to handle any cleanup that needs to be done."""
        if self._text_layer is not None:
            self._disconnect_text_layer()
        else:
            self._disconnect_signals()
        if self._dragging:
            self._selection_handler.end_selection(QPoint())
            self._dragging = False

    def _connect_text_layer(self, layer: TextLayer) -> None:
        if self._text_layer is not None:
            self._disconnect_text_layer()
        else:
            self._disconnect_signals()
        self._text_layer = layer
        if self._image_stack.active_layer != layer:
            self._image_stack.active_layer = layer
        text_rect = layer.text_rect
        self._control_panel.text_rect = text_rect
        self._control_panel.offset = layer.offset.toPoint()
        self._placement_outline = PlacementOutline(layer.offset, QSizeF(text_rect.size))
        self._scene.addItem(self._placement_outline)
        self._placement_outline.setTransform(layer.transform)
        self._placement_outline.setZValue(layer.z_value - 1)
        self._connect_signals()
        self._control_panel.focus_text_input()

    def _disconnect_text_layer(self) -> None:
        if self._text_layer is not None:
            self._disconnect_signals()
            self._text_layer = None
            text_rect = self._control_panel.text_rect
            text_rect.text = ''
            self._control_panel.text_rect = text_rect
            if self._placement_outline is not None:
                self._scene.removeItem(self._placement_outline)
                self._placement_outline = None

    def _disconnect_signals(self) -> None:
        self._image_stack.active_layer_changed.disconnect(self._active_layer_change_slot)
        if self._text_layer is not None:
            self._text_layer.transform_changed.disconnect(self._layer_transform_change_slot)
            self._text_layer.size_changed.disconnect(self._layer_size_change_slot)
        self._control_panel.text_rect_changed.disconnect(self._control_text_data_changed_slot)
        self._control_panel.offset_changed.disconnect(self._control_offset_changed_slot)
        if self._placement_outline is not None:
            self._placement_outline.placement_changed.disconnect(self._placement_outline_changed_slot)

    def _connect_signals(self):
        self._image_stack.active_layer_changed.connect(self._active_layer_change_slot)
        if self._text_layer is not None:
            self._text_layer.transform_changed.connect(self._layer_transform_change_slot)
            self._text_layer.size_changed.connect(self._layer_size_change_slot)
        self._control_panel.text_rect_changed.connect(self._control_text_data_changed_slot)
        self._control_panel.offset_changed.connect(self._control_offset_changed_slot)
        if self._placement_outline is not None:
            self._placement_outline.placement_changed.connect(self._placement_outline_changed_slot)

    def _create_and_activate_text_layer(self, layer_data: Optional[TextRect], offset: QPoint) -> None:
        with UndoStack().combining_actions('TextTool._create_and_activate_text_layer'):
            text_layer = self._image_stack.create_text_layer(layer_data)
            text_layer.transform = QTransform.fromTranslate(offset.x(), offset.y())
            self._connect_text_layer(text_layer)

    def _control_text_data_changed_slot(self, text_data: TextRect) -> None:
        if not self.is_active:
            return
        elif self._text_layer is not None:
            assert self._placement_outline is not None
            self._disconnect_signals()
            self._text_layer.text_rect = text_data
            self._placement_outline.outline_size = text_data.size
            self._connect_signals()

    def _control_offset_changed_slot(self, offset: QPoint) -> None:
        if self._text_layer is not None and self.is_active:
            assert self._placement_outline is not None
            self._disconnect_signals()
            if offset != self._text_layer.offset.toPoint():
                self._text_layer.offset = offset
            self._placement_outline.setTransform(self._text_layer.transform)
            self._connect_signals()

    def _placement_outline_changed_slot(self, offset: QPointF, size: QSizeF) -> None:
        if not self.is_active:
            return
        assert self._placement_outline is not None and self._text_layer is not None
        self._disconnect_signals()
        text_rect = self._control_panel.text_rect
        text_rect.size = size.toSize()
        self._control_panel.offset = offset.toPoint()
        self._control_panel.text_rect = text_rect
        self._text_layer.offset = offset
        self._text_layer.text_rect = text_rect
        self._connect_signals()

    def _layer_size_change_slot(self, layer: Layer, size: QSize) -> None:
        if layer != self._text_layer:
            layer.size_changed.disconnect(self._layer_size_change_slot)
            return
        if not self.is_active:
            return
        assert isinstance(layer, TextLayer)
        assert self._placement_outline is not None
        self._disconnect_signals()
        text_rect = self._control_panel.text_rect
        text_rect.size = size
        self._control_panel.text_rect = text_rect
        self._placement_outline.outline_size = QSizeF(size)
        self._connect_signals()

    def _layer_transform_change_slot(self, layer: TransformLayer, transform: QTransform) -> None:
        if layer != self._text_layer:
            layer.transform_changed.disconnect(self._layer_transform_change_slot)
            return
        if not self.is_active:
            return
        assert isinstance(layer, TextLayer)
        assert self._placement_outline is not None
        self._disconnect_signals()
        self._control_panel.offset = layer.offset.toPoint()
        self._placement_outline.setTransform(transform)
        self._connect_signals()

    def _active_layer_change_slot(self, active_layer: Layer) -> None:
        if active_layer == self._text_layer or not self.is_active:
            return
        if isinstance(active_layer, TextLayer):
            assert self.is_active
            self._connect_text_layer(active_layer)
        else:
            self._disconnect_text_layer()
