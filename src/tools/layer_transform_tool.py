"""An image editing tool that moves, scales, rotates and skews the active layer, through one TransformState."""
import math
from typing import Optional

from PySide6.QtCore import Qt, QRect, QRectF, QSize, QPoint, QPointF
from PySide6.QtGui import QCursor, QIcon, QTransform, QMouseEvent, QPixmap
from PySide6.QtWidgets import QWidget, QApplication, QMenu, QGraphicsPixmapItem, QGraphicsItem

from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.image.layers.image_stack_utils import top_layer_at_point, layers_at_point
from src.image.layers.image_layer import ImageLayer
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.layers.non_destructive_layer import NonDestructiveLayer
from src.image.layers.transform_group import TransformGroup
from src.image.layers.transform_layer import TransformLayer
from src.tools.base_tool import BaseTool, ToolGroup
from src.tools.layer_transform_state import MAX_SKEW, TransformState
from src.ui.canvas_extras import CanvasExtraCategory
from src.ui.graphics_items.layer_lock_alert_item import LayerLockAlertItem
from src.ui.graphics_items.transform_handle import TRANSFORM_MODE_SCALE
from src.ui.graphics_items.transform_outline import TransformOutline, corner_point, edge_point, EDGE_HANDLE_IDS
from src.ui.image_viewer import ImageViewer
from src.ui.input_fields.geometry_block import ANGLE, HEIGHT, SCALE_X, SCALE_Y, SKEW, WIDTH, X, Y
from src.ui.panel.tool_control_panels.layer_transform_tool_panel import LayerTransformToolPanel
from src.util.math_utils import clamp
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.text_drawing_utils import left_button_hint_text, right_button_hint_text

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.layer_transform_tool'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


TRANSFORM_LABEL = _tr('Transform layers')
TRANSFORM_TOOLTIP = _tr('Move, scale, rotate or skew the active layer.')
TRANSFORM_CONTROL_HINT = _tr('{left_mouse_icon}: select layer<br/>{left_mouse_icon}, drag: move layer'
                             '<br/>{right_mouse_icon}: choose from layers under cursor')

ICON_PATH_TRANSFORM_TOOL = f'{PROJECT_DIR}/resources/icons/tools/layer_transform_icon.svg'


class LayerTransformTool(BaseTool):
    """Applies transformations to the active layer.

    The tool keeps the layer's transform as one `TransformState`, and `_apply` is its only writer:
    - The outline and the panel send edits as intents, and each becomes a new state passed to `_apply`.
    - `_apply` redraws the outline and panel, then writes the drag preview during a mouse drag, and the layer's
      transform otherwise, through `_write_layer_transform`. Nothing else in the tool assigns `layer.transform`.
    - `_adopt` reads the layer into a new state when the tool selects it, and when its bounds or transform change
      from outside the tool (undo, menu rotate or flip, a load). A transform change is from outside when it differs
      from `_layer_matrix`, the matrix the tool last read or wrote.
    - A layer with a perspective transform has no state. The tool shows it as it is, with the fields and handles
      disabled, and only Revert and Clear transform change it.

    A mouse drag on a single layer moves a Normal-mode preview item instead of the layer, and sets the layer's
    transform once on release. The preview ignores blend modes and layers above the dragged one. Layer groups and
    panel edits change the layer transform on every step.
    """

    TOOL_GROUP = ToolGroup.EDIT

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        super().__init__(KeyConfig.TRANSFORM_TOOL_KEY, TRANSFORM_LABEL, TRANSFORM_TOOLTIP,
                         QIcon(ICON_PATH_TRANSFORM_TOOL))
        self._layer: Optional[TransformLayer] = None
        self._image_stack = image_stack
        self._image_viewer = image_viewer
        self._initial_transform = QTransform()
        self._state: Optional[TransformState] = None
        self._layer_matrix = QTransform()
        # Whether edits keep abs(x_scale / y_scale) at _fixed_ratio, which is captured from the state when the lock
        # engages and whenever the tool adopts a layer:
        self._ratio_locked = False
        self._fixed_ratio = 1.0
        self._transform_outline = TransformOutline(image_stack.undo_stack)
        self._transform_outline.moved.connect(self._move_slot)
        self._transform_outline.handle_dragged.connect(self._handle_drag_slot)
        self._transform_outline.origin_dragged.connect(self.set_transformation_origin)
        self._transform_outline.setVisible(False)
        image_viewer.canvas_extras.register(self._transform_outline, CanvasExtraCategory.TOOL)
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)
        self._layer_menu: Optional[QMenu] = None
        self._mouse_dragging = False
        self._drag_preview: Optional[QGraphicsPixmapItem] = None
        self._drag_transform: Optional[QTransform] = None
        self._transform_outline.drag_started.connect(self._drag_start_slot)
        self._transform_outline.drag_finished.connect(self._drag_finish_slot)

        # prepare control panel:
        self._control_panel = LayerTransformToolPanel(image_stack, image_viewer.hotkey_filter)
        self._control_panel.x_changed.connect(self.set_x)
        self._control_panel.y_changed.connect(self.set_y)
        self._control_panel.width_changed.connect(self.set_width)
        self._control_panel.height_changed.connect(self.set_height)
        self._control_panel.x_scale_changed.connect(self.set_x_scale)
        self._control_panel.y_scale_changed.connect(self.set_y_scale)
        self._control_panel.angle_changed.connect(self.set_rotation)
        self._control_panel.skew_changed.connect(self.set_skew)
        self._control_panel.preserve_aspect_ratio_changed.connect(self._set_ratio_locked)
        self._control_panel.reset_signal.connect(self.reset_transformation)
        self._control_panel.clear_signal.connect(lambda: self._replace_layer_transform(QTransform()))

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        transform_hint = TRANSFORM_CONTROL_HINT.format(left_mouse_icon=left_button_hint_text(),
                                                       right_mouse_icon=right_button_hint_text())
        return f'{transform_hint}<br/>{super().get_input_hint()}'

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Left-click activates the top unlocked TransformLayer under the cursor, right-click lists all of them."""
        assert event is not None
        if QApplication.keyboardModifiers() != Qt.KeyboardModifier.NoModifier:
            return False
        if event.buttons() == Qt.MouseButton.LeftButton:
            clicked_layer = top_layer_at_point(self._image_stack, image_coordinates)
            if clicked_layer is not None and isinstance(clicked_layer, TransformLayer) and clicked_layer != self._layer:
                self._select_layer(clicked_layer)
            return True
        if event.buttons() == Qt.MouseButton.RightButton:
            layers = layers_at_point(self._image_stack, image_coordinates)
            if len(layers) > 0:
                self._show_layer_menu(layers, event.globalPosition().toPoint())
            return True
        return False

    def _select_layer(self, layer: TransformLayer) -> None:
        if layer.locked or layer.parent_locked:
            LayerLockAlertItem(layer, self._image_viewer)
        self._image_stack.active_layer = layer

    def _show_layer_menu(self, layers: list[ImageLayer | NonDestructiveLayer], global_pos: QPoint) -> None:
        """Opens a non-modal menu naming each layer, topmost first, at the given screen position."""
        if self._layer_menu is not None:
            self._layer_menu.close()
            self._layer_menu.deleteLater()
        menu = QMenu(self._image_viewer)
        for layer in layers:
            action = menu.addAction(layer.name)
            action.setCheckable(True)
            action.setChecked(layer == self._layer)
            action.triggered.connect(lambda _checked=False, target=layer: self._select_layer(target))
        self._layer_menu = menu
        menu.popup(global_pos)

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        return self._control_panel

    @property
    def state(self) -> Optional[TransformState]:
        """The active layer's transform as the tool edits it, or None without a layer or for a perspective
           transform."""
        return self._state

    # -----------------------------------------------------------------------------------------------------------------
    # Edits: each turns one intent into a new state for _apply
    # -----------------------------------------------------------------------------------------------------------------

    def set_x(self, x_pos: float | int) -> None:
        """Sets the horizontal scene position of the transformation origin, moving the layer."""
        if self._state is not None:
            self._apply(self._state.with_origin_pos(QPointF(float(x_pos), self._state.origin_pos.y())))

    def set_y(self, y_pos: float | int) -> None:
        """Sets the vertical scene position of the transformation origin, moving the layer."""
        if self._state is not None:
            self._apply(self._state.with_origin_pos(QPointF(self._state.origin_pos.x(), float(y_pos))))

    def set_x_scale(self, x_scale: float) -> None:
        """Sets the x-scale of the layer transformation."""
        if self._state is not None:
            self._apply(self._scaled(x_scale, self._state.y_scale))

    def set_y_scale(self, y_scale: float) -> None:
        """Sets the y-scale of the layer transformation."""
        if self._state is not None:
            self._apply(self._scaled(self._state.x_scale, y_scale))

    def set_width(self, width: float) -> None:
        """Sets the final width of the layer in pixels, keeping a flip."""
        state = self._state
        if state is None:
            return
        state = state.with_size(width, state.height)
        if self._ratio_locked:
            state = state.with_scale(state.x_scale, math.copysign(state.x_scale / self._fixed_ratio, state.y_scale))
        self._apply(state)

    def set_height(self, height: float) -> None:
        """Sets the final height of the layer in pixels, keeping a flip."""
        state = self._state
        if state is None:
            return
        state = state.with_size(state.width, height)
        if self._ratio_locked:
            state = state.with_scale(math.copysign(state.y_scale * self._fixed_ratio, state.x_scale), state.y_scale)
        self._apply(state)

    def set_rotation(self, rotation: float) -> None:
        """Sets the angle of layer rotation in degrees."""
        if self._state is not None:
            self._apply(self._state.with_rotation(rotation))

    def set_skew(self, skew: float) -> None:
        """Sets the skew angle in degrees about the transformation origin, clamped to MAX_SKEW either way."""
        if self._state is not None:
            self._apply(self._state.with_skew(clamp(skew, -MAX_SKEW, MAX_SKEW)))

    def set_transformation_origin(self, local_point: QPointF) -> None:
        """Moves the transformation origin to a point in the layer's untransformed coordinates, leaving the layer in
           place."""
        state = self._state
        if state is None:
            return
        rect = state.rect
        relative = state.relative_origin
        if rect.width() != 0:
            relative.setX((local_point.x() - rect.x()) / rect.width())
        if rect.height() != 0:
            relative.setY((local_point.y() - rect.y()) / rect.height())
        self._apply(state.with_relative_origin(relative))

    def _scaled(self, x_scale: float, y_scale: float) -> TransformState:
        """Returns the state at new scales. With the ratio locked, the scale that changed more sets the other."""
        assert self._state is not None
        if self._ratio_locked:
            if abs(x_scale - self._state.x_scale) >= abs(y_scale - self._state.y_scale):
                y_scale = math.copysign(x_scale / self._fixed_ratio, y_scale)
            else:
                x_scale = math.copysign(y_scale * self._fixed_ratio, x_scale)
        return self._state.with_scale(x_scale, y_scale)

    def _move_slot(self, dx: float, dy: float) -> None:
        if self._state is not None:
            self._apply(self._state.moved_by(dx, dy))

    def _handle_drag_slot(self, handle_id: str, scene_pos: QPointF) -> None:
        """Applies a corner or edge handle drag, holding the opposite corner or edge, as the outline's mode says.

        In scale mode, corners scale and edges scale one axis. In rotate mode, corners rotate about the origin and
        edges skew."""
        state = self._state
        if state is None:
            return
        scaling = self._transform_outline.mode == TRANSFORM_MODE_SCALE
        fixed_ratio = self._fixed_ratio if self._ratio_locked else None
        if handle_id in EDGE_HANDLE_IDS:
            edge = edge_point(state.rect, handle_id)
            if scaling:
                target = state.matrix().inverted()[0].map(scene_pos)
                self._apply(state.with_edge_moved(edge, target, fixed_ratio))
            else:
                self._apply(state.with_edge_sheared(edge, scene_pos))
            return
        corner = corner_point(state.rect, handle_id)
        if scaling:
            target = state.matrix().inverted()[0].map(scene_pos)
            self._apply(state.with_corner_moved(corner, target, fixed_ratio))
        else:
            self._apply(state.with_corner_turned(corner, scene_pos))

    def _set_ratio_locked(self, locked: bool) -> None:
        self._ratio_locked = locked
        if locked:
            self._capture_ratio()

    def _capture_ratio(self) -> None:
        if self._state is not None:
            self._fixed_ratio = abs(self._state.x_scale / self._state.y_scale)

    def reset_transformation(self) -> None:
        """Restores the transform the layer had when the tool selected it."""
        self._replace_layer_transform(self._initial_transform)

    # -----------------------------------------------------------------------------------------------------------------
    # The writer
    # -----------------------------------------------------------------------------------------------------------------

    def _apply(self, state: TransformState) -> None:
        """Makes state current: redraws the outline and panel, then writes the drag preview during a mouse drag and
           the layer's transform otherwise. Does nothing without an editable layer."""
        layer = self._layer
        if layer is None or self._state is None or layer.locked or layer.parent_locked:
            return
        self._state = state
        self._show_state()
        matrix = state.matrix()
        if matrix == (self._drag_transform if self._drag_transform is not None else self._layer_matrix):
            return
        if self._mouse_dragging and isinstance(layer, ImageLayer | NonDestructiveLayer):
            if self._drag_preview is None:
                self._start_drag_preview(layer)
            if self._drag_preview is not None:
                self._drag_transform = matrix
                self._drag_preview.setTransform(matrix)
                return
        self._write_layer_transform(matrix)

    def _write_layer_transform(self, matrix: QTransform) -> None:
        """Assigns the layer's transform, recording it first so the change it signals isn't read back as external."""
        assert self._layer is not None
        self._layer_matrix = QTransform(matrix)
        self._layer.transform = matrix
        self._control_panel.set_preview_transform(matrix)

    def _replace_layer_transform(self, matrix: QTransform) -> None:
        """Writes a whole matrix to the layer for Revert and Clear transform, then reads it back. Works on a layer
           with perspective too."""
        layer = self._layer
        if layer is None or not self.is_active or layer.locked or layer.parent_locked:
            return
        self._write_layer_transform(matrix)
        self._adopt(keep_relative_origin=True)

    def _show_state(self) -> None:
        """Draws the current state in the outline, and shows its values in the panel and preview."""
        state = self._state
        if self._layer is None:
            return
        if state is None:
            self._transform_outline.show_uneditable(QRectF(self._layer.bounds), self._layer_matrix)
            self._control_panel.set_preview_transform(self._layer_matrix)
            return
        self._transform_outline.set_state(state)
        self._control_panel.set_preview_transform(state.matrix())
        origin = state.origin_pos
        self._control_panel.geometry_block.set_values(**{
            X: origin.x(), Y: origin.y(), WIDTH: state.width, HEIGHT: state.height,
            SCALE_X: state.x_scale, SCALE_Y: state.y_scale, ANGLE: state.rotation, SKEW: state.skew})

    # -----------------------------------------------------------------------------------------------------------------
    # Adopting the layer
    # -----------------------------------------------------------------------------------------------------------------

    def set_layer(self, layer: Optional[Layer]) -> None:
        """Connects to a new image layer, or disconnects if the layer parameter is None. Cancels any drag preview, and
           the rest of an in-progress drag changes the new layer directly."""
        self._end_drag_preview(apply=False)
        self._mouse_dragging = False
        last_layer = self._layer
        if last_layer is not None:
            last_layer.transform_changed.disconnect(self._layer_transform_change_slot)
            last_layer.size_changed.disconnect(self._layer_size_change_slot)
            last_layer.lock_changed.disconnect(self._layer_lock_change_slot)
            if isinstance(last_layer, TransformGroup):
                last_layer.bounds_changed.disconnect(self._update_transform_group_bounds)
                last_layer.remove_all()
        if layer is None or isinstance(layer, TransformLayer):
            self._layer = layer
        else:
            assert isinstance(layer, LayerGroup)
            self._layer = TransformGroup(layer)
        if self._layer is not None:
            self._initial_transform = self._layer.transform
        self._ratio_locked = self._control_panel.geometry_block.effective_ratio_locked()
        self._adopt(keep_relative_origin=False)
        if self._layer is not None:
            self._layer.transform_changed.connect(self._layer_transform_change_slot)
            self._layer.size_changed.connect(self._layer_size_change_slot)
            self._layer.lock_changed.connect(self._layer_lock_change_slot)
            if isinstance(self._layer, TransformGroup):
                self._layer.bounds_changed.connect(self._update_transform_group_bounds)

    def _adopt(self, keep_relative_origin: bool) -> None:
        """Reads the layer's bounds and transform into a new state, without writing to the layer.

        The transformation origin moves to the layer center, unless keep_relative_origin is set for a reload of the
        same layer."""
        layer = self._layer
        outline = self._transform_outline
        relative_origin = QPointF(0.5, 0.5)
        if keep_relative_origin and self._state is not None:
            relative_origin = self._state.relative_origin
        outline.setZValue(self._image_stack.selection_layer.z_value + 1)
        if layer is None:
            self._state = None
            self._layer_matrix = QTransform()
            outline.setVisible(False)
            self._control_panel.set_preview_bounds(QRect())
            self._control_panel.set_preview_transform(QTransform())
        else:
            self._layer_matrix = layer.transform
            self._state = TransformState.from_matrix(self._layer_matrix, QRectF(layer.bounds), relative_origin)
            self._control_panel.set_preview_bounds(layer.bounds)
            outline.setVisible(layer.shown and not layer.size.isEmpty())
            self._capture_ratio()
            self._show_state()
        self._update_enabled()

    def _update_enabled(self) -> None:
        """Enables the panel for an unlocked, non-empty layer, and its fields and the outline only while the layer has
           a state."""
        layer = self._layer
        layer_editable = (layer is not None and not layer.locked and not layer.parent_locked
                          and not layer.size.isEmpty())
        fields_editable = layer_editable and self._state is not None
        self._control_panel.setEnabled(layer_editable)
        self._control_panel.set_transform_editable(layer is None or self._state is not None)
        self._transform_outline.setEnabled(fields_editable)
        self.set_disabled_cursor(not fields_editable)

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

    def _update_transform_group_bounds(self, bounds: QRect) -> None:
        """Re-adopts a layer group whose untransformed bounds differ from the outline's rectangle."""
        if QRectF(bounds) != self._transform_outline.rect():
            self._adopt(keep_relative_origin=True)

    def _layer_lock_change_slot(self, layer: Layer, _locked: bool) -> None:
        assert self._layer is not None
        assert layer == self._layer or (isinstance(layer, LayerGroup) and layer.contains_recursive(self._layer))  \
               or isinstance(layer, TransformGroup)
        self._update_enabled()

    def _layer_transform_change_slot(self, layer: Layer, transform: QTransform) -> None:
        assert layer == self._layer
        if transform != self._layer_matrix:
            self._adopt(keep_relative_origin=True)

    def _layer_size_change_slot(self, layer: Layer, _size: QSize) -> None:
        assert layer == self._layer
        self._adopt(keep_relative_origin=True)

    # -----------------------------------------------------------------------------------------------------------------
    # Drag preview
    # -----------------------------------------------------------------------------------------------------------------

    def _drag_start_slot(self) -> None:
        self._mouse_dragging = True

    def _drag_finish_slot(self) -> None:
        self._mouse_dragging = False
        self._end_drag_preview(apply=True)

    def _start_drag_preview(self, layer: TransformLayer) -> None:
        """Hides the layer and shows a Normal-mode copy of its image in the scene to stand in for it."""
        scene = self._image_viewer.scene()
        if scene is None or layer.size.isEmpty() or not layer.visible:
            return
        preview = QGraphicsPixmapItem(QPixmap.fromImage(layer.get_qimage().copy()))
        preview.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        preview.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        preview.setOpacity(layer.opacity)
        preview.setTransform(layer.transform)
        preview.setZValue(self._transform_outline.zValue() - 1)
        scene.addItem(preview)
        self._drag_preview = preview
        layer.set_visible(False)

    def _end_drag_preview(self, apply: bool) -> None:
        """Removes the drag preview and shows the layer again, first setting its transform to the dragged one if
           apply is set."""
        preview = self._drag_preview
        if preview is None:
            return
        layer = self._layer
        transform = self._drag_transform
        self._drag_preview = None
        self._drag_transform = None
        scene = preview.scene()
        if scene is not None:
            scene.removeItem(preview)
        if layer is None:
            return
        # The layer is still hidden, so the transform change recomposites nothing, and showing it redraws once:
        if apply and transform is not None:
            self._write_layer_transform(transform)
        layer.set_visible(True)
        self._control_panel.set_preview_transform(layer.transform)
