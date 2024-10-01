"""An image editing tool that moves the selected editing region."""
from typing import Optional, Callable

from PySide6.QtCore import Qt, QRect, QRectF, QSize
from PySide6.QtGui import QCursor, QIcon, QTransform
from PySide6.QtWidgets import QWidget, QSpinBox, QDoubleSpinBox, QApplication

from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_stack import LayerStack
from src.image.layers.transform_group import TransformGroup
from src.image.layers.transform_layer import TransformLayer
from src.tools.base_tool import BaseTool
from src.ui.graphics_items.transform_outline import TransformOutline
from src.ui.image_viewer import ImageViewer
from src.ui.panel.tool_control_panels.layer_transform_tool_panel import LayerTransformToolPanel
from src.undo_stack import UndoStack
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.text_drawing_utils import left_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.layer_transform_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


TRANSFORM_LABEL = _tr('Transform Layers')
TRANSFORM_TOOLTIP = _tr('Move, scale, or rotate the active layer.')
TRANSFORM_CONTROL_HINT = _tr('{left_mouse_icon}, drag: move layer')

RESOURCES_TRANSFORM_TOOL_ICON = f'{PROJECT_DIR}/resources/icons/tools/layer_transform_icon.svg'


class LayerTransformTool(BaseTool):
    """Applies transformations to the active layer."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        super().__init__(KeyConfig.TRANSFORM_TOOL_KEY, TRANSFORM_LABEL, TRANSFORM_TOOLTIP,
                         QIcon(RESOURCES_TRANSFORM_TOOL_ICON))
        self._layer: Optional[TransformLayer] = None
        self._image_stack = image_stack
        self._image_viewer = image_viewer
        self._initial_transform = QTransform()
        self._transform_outline = TransformOutline(QRectF())
        self._transform_outline.offset_changed.connect(self._offset_change_slot)
        self._transform_outline.scale_changed.connect(self._scale_change_slot)
        self._transform_outline.angle_changed.connect(self._angle_change_slot)
        self._transform_outline.transform_changed.connect(self._transform_change_slot)
        self._transform_outline.setVisible(False)
        scene = image_viewer.scene()
        assert scene is not None
        scene.addItem(self._transform_outline)
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)

        # prepare control panel:
        self._control_panel = LayerTransformToolPanel(image_stack)
        self._control_panel.x_changed.connect(self.set_x)
        self._control_panel.y_changed.connect(self.set_y)
        self._control_panel.width_changed.connect(self.set_width)
        self._control_panel.height_changed.connect(self.set_height)
        self._control_panel.x_scale_changed.connect(self.set_x_scale)
        self._control_panel.y_scale_changed.connect(self.set_y_scale)
        self._control_panel.angle_changed.connect(self.set_rotation)

        def _restore_aspect_ratio(preserve_ratio: bool) -> None:
            self._transform_outline.preserve_aspect_ratio = preserve_ratio
        self._control_panel.preserve_aspect_ratio_changed.connect(_restore_aspect_ratio)

        def _reset() -> None:
            if self.is_active and self._layer is not None:
                self._transform_outline.setTransform(self._initial_transform)

        def _clear() -> None:
            if self.is_active and self._layer is not None:
                self._transform_outline.setTransform(QTransform())

        self._control_panel.reset_signal.connect(_reset)
        self._control_panel.clear_signal.connect(_clear)

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        transform_hint = TRANSFORM_CONTROL_HINT.format(left_mouse_icon=left_button_hint_text())
        return f'{transform_hint}<br/>{super().get_input_hint()}'

    def restore_aspect_ratio(self) -> None:
        """Ensure that the aspect ratio is constant."""
        max_scale = max(self._transform_outline.transform_scale)
        self._transform_outline.transform_scale = (max_scale, max_scale)

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        return self._control_panel

    def set_x_offset(self, x_offset: float) -> None:
        """Sets the x-offset component of the layer transformation."""
        offset = self._transform_outline.offset
        offset.setX(x_offset)
        self._transform_outline.offset = offset

    def set_y_offset(self, y_offset: float) -> None:
        """Sets the y-offset component of the layer transformation."""
        offset = self._transform_outline.offset
        offset.setY(y_offset)
        self._transform_outline.offset = offset

    def set_x(self, x_pos: float | int) -> None:
        """Sets the post-transformation horizontal position of the layer in pixels."""
        self._transform_outline.x_pos = float(x_pos)

    def set_y(self, y_pos: float | int) -> None:
        """Sets the post-transformation vertical position of the layer in pixels."""
        self._transform_outline.y_pos = float(y_pos)

    def set_x_scale(self, x_scale: float) -> None:
        """Sets the x-scale of the layer transformation, also changing y-scale if aspect ratio is preserved."""
        _, prev_y_scale = self._transform_outline.transform_scale
        if self._control_panel.preserve_aspect_ratio:
            self._transform_outline.transform_scale = (x_scale, x_scale)
        else:
            self._transform_outline.transform_scale = (x_scale, prev_y_scale)

    def set_y_scale(self, y_scale: float) -> None:
        """Sets the y-scale of the layer transformation, also changing x-scale if aspect ratio is preserved."""
        prev_x_scale, _ = self._transform_outline.transform_scale
        self._transform_outline.transform_scale = (prev_x_scale, y_scale)

    def set_width(self, width: float) -> None:
        """Sets the final width of the layer in pixels."""
        self._transform_outline.width = width

    def set_height(self, height: float) -> None:
        """Sets the final height of the layer in pixels."""
        self._transform_outline.height = height

    def set_rotation(self, rotation: float) -> None:
        """Sets the angle of layer rotation in degrees."""
        prev_rotation = self._transform_outline.rotation_angle
        if prev_rotation != rotation:
            self._transform_outline.rotation_angle = rotation

    def set_layer(self, layer: Optional[Layer]) -> None:
        """Connects to a new image layer, or disconnects if the layer parameter is None."""
        last_layer = self._layer
        if last_layer is not None:
            last_layer.transform_changed.disconnect(self._layer_transform_change_slot)
            last_layer.size_changed.disconnect(self._layer_size_change_slot)
            last_layer.lock_changed.disconnect(self._layer_lock_change_slot)
        if layer is None or isinstance(layer, TransformLayer):
            self._layer = layer
        else:
            assert isinstance(layer, LayerStack)
            self._layer = TransformGroup(layer)
        self._reload_scene_item()
        if self._layer is not None:
            self._layer.transform_changed.connect(self._layer_transform_change_slot)
            self._layer.size_changed.connect(self._layer_size_change_slot)
            self._layer.lock_changed.connect(self._layer_lock_change_slot)
            self._layer_lock_change_slot(self._layer, self._layer.locked)
        else:
            self._control_panel.set_preview_bounds(QRect())
            self._transform_outline.setVisible(False)

    def reset_transformation(self) -> None:
        """Resets the transformation to its previous state."""
        layer = self._layer
        if layer is not None and self.is_active:
            changed_transform = self._transform_outline.transform()
            source_transform = self._initial_transform
            if changed_transform != source_transform:

                def _apply(active=layer, matrix=source_transform):
                    active.set_transform(matrix)

                def _undo(active=layer, matrix=changed_transform):
                    active.set_transform(matrix)

                UndoStack().commit_action(_apply, _undo, 'LayerTransformTool.reset_transformation')
            self._transform_outline.setTransform(self._initial_transform)

    def _reload_scene_item(self):
        """Reset all transformations and reload properties from the layer."""
        layer = self._layer

        # Clear old transform outline:
        self._transform_outline.offset_changed.disconnect(self._offset_change_slot)
        self._transform_outline.scale_changed.disconnect(self._scale_change_slot)
        self._transform_outline.angle_changed.disconnect(self._angle_change_slot)
        self._transform_outline.transform_changed.disconnect(self._transform_change_slot)
        scene = self._transform_outline.scene()
        if scene is not None:
            scene.removeItem(self._transform_outline)
        scene = self._image_viewer.scene()
        assert scene is not None

        # Re-create for new layer:
        self._transform_outline = TransformOutline(QRectF() if layer is None else QRectF(layer.bounds))
        self._transform_outline.setZValue(self._image_stack.selection_layer.z_value + 1)
        self._transform_outline.offset_changed.connect(self._offset_change_slot)
        self._transform_outline.scale_changed.connect(self._scale_change_slot)
        self._transform_outline.angle_changed.connect(self._angle_change_slot)
        self._transform_outline.transform_changed.connect(self._transform_change_slot)
        self._transform_outline.setVisible(False)
        scene.addItem(self._transform_outline)

        # Load layer image, set visibility and zValues:
        self._transform_outline.prepareGeometryChange()
        if layer is None:
            self._transform_outline.setVisible(False)
            self._transform_outline.setRect(QRectF())
            self._control_panel.set_preview_bounds(QRect())
            self._control_panel.set_preview_transform(QTransform())
            self._transform_outline.setVisible(False)
        else:
            self._initial_transform = layer.transform
            self._control_panel.set_preview_bounds(layer.bounds)
            self._transform_outline.setVisible(layer.visible and not layer.size.isEmpty())
            self._control_panel.set_preview_transform(self._initial_transform)
            self._transform_outline.setTransform(self._initial_transform)
        self._control_panel.setEnabled(layer is not None and not layer.locked and not layer.parent_locked
                                       and not self._layer.size.isEmpty())
        self._update_all_controls()

    def _on_activate(self, restoring_after_delegation=False) -> None:
        """Connect to the active layer."""
        self._image_stack.active_layer_changed.connect(self._active_layer_change_slot)
        self.set_layer(self._image_stack.active_layer)

    def _on_deactivate(self) -> None:
        """Disconnect from all layers."""
        self._image_stack.active_layer_changed.disconnect(self._active_layer_change_slot)
        self.set_layer(None)

    def _active_layer_change_slot(self, active_layer: Layer) -> None:
        self.set_layer(active_layer)

    def _layer_lock_change_slot(self, layer: Layer, locked: bool) -> None:
        assert self._layer is not None
        assert layer == self._layer or layer.contains_recursive(self._layer) or isinstance(layer, TransformGroup)
        if self._control_panel is not None:
            self._control_panel.setEnabled(not locked)
            self._transform_outline.setEnabled(not locked)

    # noinspection PyUnusedLocal
    def _layer_transform_change_slot(self, layer: Layer, transform: QTransform) -> None:
        assert layer == self._layer
        if transform != self._transform_outline.transform():
            self._transform_outline.setTransform(transform)

    # noinspection PyUnusedLocal
    def _layer_size_change_slot(self, layer: Layer, size: QSize) -> None:
        assert layer == self._layer
        self._reload_scene_item()

    def _transform_change_slot(self, transform: QTransform) -> None:
        layer = self._layer
        if layer is None:
            return
        try:
            layer.transform = transform
        except RuntimeError:  # undo stack conflict, just don't register this one in the undo history
            layer.set_transform(transform)
        self._control_panel.set_preview_transform(layer.transform)

    @staticmethod
    def _update_control(field: QSpinBox | QDoubleSpinBox, value: float, change_handler: Callable[..., None]):
        field.valueChanged.disconnect(change_handler)
        if field.value() != value:
            if isinstance(field, QSpinBox):
                field.setValue(int(value))
            else:  # QDoubleSpinBox
                field.setValue(float(value))
        field.valueChanged.connect(change_handler)

    # noinspection PyUnusedLocal
    def _offset_change_slot(self, *unused_args) -> None:
        self._control_panel.x_position = self._transform_outline.x_pos
        self._control_panel.y_position = self._transform_outline.y_pos

    def _scale_change_slot(self, x_scale: float, y_scale: float) -> None:
        self._control_panel.layer_width = self._transform_outline.width
        self._control_panel.layer_height = self._transform_outline.height
        self._control_panel.x_scale = x_scale
        self._control_panel.y_scale = y_scale

    def _angle_change_slot(self, angle: float) -> None:
        self._control_panel.rotation = angle

    def _update_all_controls(self) -> None:
        self._offset_change_slot()
        self._scale_change_slot(*self._transform_outline.transform_scale)
        self._angle_change_slot(self._transform_outline.rotation_angle)
