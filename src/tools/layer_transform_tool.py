"""An image editing tool that moves the selected editing region."""
from typing import Optional, Dict

from PyQt5.QtCore import Qt, QPoint, QRect, QRectF, QPointF
from PyQt5.QtGui import QCursor, QIcon, QPixmap, QImage, QPainter, \
    QKeySequence
from PyQt5.QtWidgets import QWidget, QLabel, QGraphicsPixmapItem, QGraphicsItem, QSpinBox, QDoubleSpinBox, \
    QCheckBox, QGridLayout, QPushButton

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.image_layer import ImageLayer
from src.image.layer_stack import LayerStack
from src.tools.base_tool import BaseTool
from src.ui.graphics_items.transform_outline import TransformOutline
from src.ui.image_viewer import ImageViewer
from src.ui.widget.key_hint_label import KeyHintLabel
from src.undo_stack import commit_action

X_LABEL = "X:"
Y_LABEL = "Y:"
X_SCALE_LABEL = "X-Scale:"
Y_SCALE_LABEL = "Y-Scale:"
WIDTH_LABEL = "Width:"
HEIGHT_LABEL = "Height:"
DEGREE_LABEL = 'Rotation:'

TRANSFORM_LABEL = 'Transform Layers'
TRANSFORM_TOOLTIP = 'Move, scale, or rotate the active layer.'
RESOURCES_TRANSFORM_TOOL_ICON = 'resources/icons/layer_transform_icon.svg'
ASPECT_RATIO_CHECK_LABEL = 'Preserve aspect ratio'
RESET_BUTTON_TEXT = 'Reset'
TRANSFORM_CONTROL_HINT = 'LMB+drag:move layer -'

FLOAT_MAX = 9999999.0
FLOAT_MIN = -9999999.0
MIN_NONZERO = 0.001
INT_MIN = -2147483646
INT_MAX = 2147483647
SCALE_STEP = 0.05


class LayerTransformTool(BaseTool):
    """Applies transformations to the active layer."""

    def __init__(self, layer_stack: LayerStack, image_viewer: ImageViewer) -> None:
        super().__init__()
        self._layer_stack = layer_stack
        self._image_viewer = image_viewer
        self._icon = QIcon(RESOURCES_TRANSFORM_TOOL_ICON)
        self._transform_outline = TransformOutline()
        self._transform_outline.transform_changed.connect(self._transformation_change_slot)
        self._transform_pixmap = QGraphicsPixmapItem(self._transform_outline)
        self._transform_pixmap.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresParentOpacity)
        self._transform_outline.setVisible(False)
        image_viewer.scene().addItem(self._transform_outline)
        self.cursor = QCursor(Qt.CursorShape.OpenHandCursor)
        self._dragging = False
        self._last_mouse_pos: Optional[QPoint] = None
        self._initial_layer_offset: Optional[QPoint] = None
        self._active_layer_id = None if layer_stack.active_layer is None else layer_stack.active_layer.id

        # prepare control panel, wait to fully initialize
        self._control_panel = QWidget()
        self._control_layout: Optional[QGridLayout] = None

        def _init_control(default_val, min_val, max_val, change_fn):
            new_control = QSpinBox() if isinstance(default_val, int) else QDoubleSpinBox()
            new_control.setRange(min_val, max_val)
            new_control.setValue(default_val)
            new_control.valueChanged.connect(change_fn)
            return new_control

        self._x_pos_box = _init_control(0.0, FLOAT_MIN, FLOAT_MAX, self.set_x)
        self._y_pos_box = _init_control(0.0, FLOAT_MIN, FLOAT_MAX, self.set_y)
        edit_size = AppConfig.instance().get(AppConfig.EDIT_SIZE)
        self._width_box = _init_control(float(edit_size.width()), MIN_NONZERO, FLOAT_MAX, self.set_width)
        self._height_box = _init_control(float(edit_size.height()), MIN_NONZERO, FLOAT_MAX, self.set_height)

        self._x_scale_box = _init_control(1.0, FLOAT_MIN, FLOAT_MAX, self.set_x_scale)
        self._y_scale_box = _init_control(1.0, FLOAT_MIN, FLOAT_MAX, self.set_y_scale)

        for scale_box in (self._y_scale_box, self._x_scale_box):
            scale_box.setSingleStep(SCALE_STEP)
        self._height_box = _init_control(float(edit_size.height()), MIN_NONZERO, FLOAT_MAX, self.set_height)
        self._rotate_box = _init_control(0.0, FLOAT_MIN, FLOAT_MAX, self.set_rotation)
        self._aspect_ratio_checkbox = QCheckBox()
        self._down_keys: Dict[QWidget, QKeySequence] = {}
        self._up_keys: Dict[QWidget, QKeySequence] = {}

        def _restore_aspect_ratio() -> None:
            self._transform_outline.preserve_aspect_ratio = self._aspect_ratio_checkbox.isChecked()

        self._aspect_ratio_checkbox.clicked.connect(_restore_aspect_ratio)

        # Register movement key overrides, tied to control panel visibility:
        config = KeyConfig.instance()
        for control, up_key_code, down_key_code in ((self._x_pos_box, KeyConfig.MOVE_RIGHT, KeyConfig.MOVE_LEFT),
                                                    (self._y_pos_box, KeyConfig.MOVE_DOWN, KeyConfig.MOVE_UP),
                                                    (self._width_box, KeyConfig.PAN_RIGHT, KeyConfig.PAN_LEFT),
                                                    (self._height_box, KeyConfig.PAN_UP, KeyConfig.PAN_DOWN),
                                                    (self._rotate_box, KeyConfig.ROTATE_CW_KEY,
                                                     KeyConfig.ROTATE_CCW_KEY)):
            self._up_keys[control] = config.get_keycodes(up_key_code)
            self._down_keys[control] = config.get_keycodes(down_key_code)

            def _step(steps: int, spinbox) -> bool:
                if not self.is_active:
                    return False
                spinbox.stepBy(steps)
                return True

            for key, sign in ((up_key_code, 1), (down_key_code, -1)):
                def _binding(mult, n=sign, box=control) -> bool:
                    return _step(n * mult, box)

                HotkeyFilter.instance().register_speed_modified_keybinding(_binding, key)

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return KeyConfig.instance().get_keycodes(KeyConfig.TRANSFORM_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return TRANSFORM_LABEL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return TRANSFORM_TOOLTIP

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        return f'{TRANSFORM_CONTROL_HINT} {super().get_input_hint()}'

    def restore_aspect_ratio(self) -> None:
        """Ensure that the aspect ratio is constant."""
        max_scale = max(self._transform_outline.scale)
        self._transform_outline.scale = (max_scale, max_scale)

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        if self._control_layout is not None:
            return self._control_panel
        self._control_layout = QGridLayout(self._control_panel)
        grid = self._control_layout
        grid.setAlignment(Qt.AlignCenter)

        def _add_control(label: str, widget: QWidget, row: int, col: int) -> None:
            label = QLabel(label)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(label, row, col)
            if widget in self._down_keys:
                down_hint = KeyHintLabel(self._down_keys[widget], self._control_panel)
                down_hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                grid.addWidget(down_hint, row, col + 1)
            grid.addWidget(widget, row, col + 2)
            if widget in self._up_keys:
                up_hint = KeyHintLabel(self._up_keys[widget], self._control_panel)
                up_hint.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                grid.addWidget(up_hint, row, col + 3)

        _add_control(X_LABEL, self._x_pos_box, 0, 0)
        _add_control(Y_LABEL, self._y_pos_box, 0, 4)

        _add_control(WIDTH_LABEL, self._width_box, 2, 0)
        _add_control(HEIGHT_LABEL, self._height_box, 2, 4)

        _add_control(X_SCALE_LABEL, self._x_scale_box, 3, 0)
        _add_control(Y_SCALE_LABEL, self._y_scale_box, 3, 4)

        _add_control(DEGREE_LABEL, self._rotate_box, 4, 0)
        self._aspect_ratio_checkbox.setText(ASPECT_RATIO_CHECK_LABEL)
        grid.addWidget(self._aspect_ratio_checkbox, 5, 2, 1, 5)

        reset_button = QPushButton()
        reset_button.setText(RESET_BUTTON_TEXT)
        reset_button.clicked.connect(self._reload_scene_item)
        grid.addWidget(reset_button, 7, 1, 1, 6)

        for label_col in (0, 4):
            grid.setColumnStretch(label_col, 10)
        for hint_col in (1, 3, 5, 7):
            grid.setColumnStretch(hint_col, 2)
        for field_col in (2, 6):
            grid.setColumnStretch(field_col, 30)
        grid.setSpacing(8)
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
        self._transform_outline.x = float(x_pos)

    def set_y(self, y_pos: float | int) -> None:
        """Sets the post-transformation vertical position of the layer in pixels."""
        self._transform_outline.y = float(y_pos)

    def set_x_scale(self, x_scale: float) -> None:
        """Sets the x-scale of the layer transformation, also changing y-scale if aspect ratio is preserved."""
        _, prev_y_scale = self._transform_outline.scale
        if self._aspect_ratio_checkbox.isChecked():
            self._transform_outline.scale = (x_scale, x_scale)
        else:
            self._transform_outline.scale = (x_scale, prev_y_scale)

    def set_y_scale(self, y_scale: float) -> None:
        """Sets the y-scale of the layer transformation, also changing x-scale if aspect ratio is preserved."""
        prev_x_scale, _ = self._transform_outline.scale
        self._transform_outline.scale = (prev_x_scale, y_scale)

    def set_width(self, width: float) -> None:
        """Sets the final width of the layer in pixels."""
        self._transform_outline.width = width

    def set_height(self, height: float) -> None:
        """Sets the final height of the layer in pixels."""
        self._transform_outline.height = height

    def set_rotation(self, rotation: float) -> None:
        """Sets the angle of layer rotation in degrees."""
        prev_rotation = self._transform_outline.rotation
        if prev_rotation != rotation:
            self._transform_outline.rotation = rotation

    def set_layer(self, layer: Optional[ImageLayer]) -> None:
        """Connects to a new image layer, or disconnects if the layer parameter is None."""
        if self._active_layer_id == (None if layer is None else layer.id):
            return
        last_layer = self._layer_stack.get_layer_by_id(self._active_layer_id)
        if last_layer is not None:
            self.apply_transformations_to_layer()
            last_layer.visibility_changed.disconnect(self._layer_visibility_slot)
            last_layer.bounds_changed.disconnect(self._layer_bounds_change_slot)
            last_layer.content_changed.disconnect(self._layer_content_change_slot)
            self._image_viewer.resume_rendering_layer(last_layer)
        self._active_layer_id = None if layer is None else layer.id
        self._reload_scene_item()
        if layer is not None:
            self._image_viewer.stop_rendering_layer(layer)
            layer.visibility_changed.connect(self._layer_visibility_slot)
            layer.bounds_changed.connect(self._layer_bounds_change_slot)
            layer.content_changed.connect(self._layer_content_change_slot)
            self._transform_outline.setRect(QRectF(layer.geometry))
        else:
            self._transform_pixmap.setPixmap(QPixmap())
            self._transform_outline.setVisible(False)

    def apply_transformations_to_layer(self) -> None:
        """Applies all pending transformations to the source layer."""
        layer = self._layer_stack.get_layer_by_id(self._active_layer_id)
        if layer is None:
            return
        initial_bounds = self._transform_outline.rect()
        bounds = self._transform_outline.mapRectToScene(initial_bounds)
        print(f'drawing bounds {bounds} from {initial_bounds}')
        transform_image = QImage(bounds.size().toSize(), QImage.Format.Format_ARGB32_Premultiplied)
        transform_image.fill(Qt.GlobalColor.transparent)
        # Temporarily hide everything else in the scene:
        opacity_map: Dict[QGraphicsItem: float] = {}
        for item in self._image_viewer.scene().items():
            opacity_map[item] = item.opacity()
            item.setOpacity(0.0)
        self._transform_pixmap.setOpacity(1.0)
        self._image_viewer.scene().update()
        # Render the scene into the image:
        painter = QPainter(transform_image)
        self._image_viewer.scene().render(painter, QRectF(QPoint(), bounds.size()), bounds)
        painter.end()
        # Restore previous scene item visibility:
        for scene_item, opacity in opacity_map.items():
            scene_item.setOpacity(opacity)
        source_image = layer.qimage
        source_pos = layer.position
        transform_pos = bounds.topLeft().toPoint()

        def _transform(pos=transform_pos, img=transform_image) -> None:
            if img is not None:
                layer.qimage = img
            layer.set_position(pos, False)

        def _undo_transform(pos=source_pos, img=source_image) -> None:
            if img is not None:
                layer.qimage = img
            layer.set_position(pos, False)

        transformed = commit_action(_transform, _undo_transform, ignore_if_locked=True)
        if not transformed:
            print('Warning: pending transformation was discarded')
        self._reload_scene_item()

    def _reload_scene_item(self):
        """Reset all transformations and reload the scene pixmap from the layer."""
        self._transform_outline.clearTransformations()
        layer = self._layer_stack.active_layer
        if layer is None or layer.id != self._active_layer_id:
            self._transform_pixmap.setPixmap(QPixmap())
            self._transform_outline.setVisible(False)
        self._transform_outline.prepareGeometryChange()
        if layer is None:
            self._transform_outline.setRect(QRectF())
            self._transform_pixmap.setPixmap(QPixmap())
            self._transform_outline.setVisible(False)
        else:
            self._transform_outline.setRect(QRectF(layer.geometry))
            self._transform_pixmap.setPixmap(layer.pixmap)
            self._transform_outline.setVisible(layer.visible)
            self._transform_outline.setZValue(-self._layer_stack.get_layer_index(layer))

    def _on_activate(self) -> None:
        """Connect to the active layer."""
        self._layer_stack.active_layer_changed.connect(self._active_layer_change_slot)
        self._image_viewer.mouse_moves_generation_area = False
        self.set_layer(self._layer_stack.active_layer)

    def _on_deactivate(self) -> None:
        """Disconnect from all layers."""
        self._layer_stack.active_layer_changed.disconnect(self._active_layer_change_slot)
        self._image_viewer.mouse_moves_generation_area = True
        self.set_layer(None)

    def _active_layer_change_slot(self, layer_id: int, layer_index: int) -> None:
        print(f'active layer now {layer_id}')
        if layer_id == self._active_layer_id:
            self._transform_outline.setZValue(-layer_index)
        else:
            self.set_layer(self._layer_stack.get_layer_by_id(layer_id))

    def _layer_visibility_slot(self, layer: ImageLayer, visible: bool) -> None:
        if layer != self._layer_stack.get_layer_by_id(self._active_layer_id):
            layer.visibility_changed.disconnect(self._layer_visibility_slot)
            return
        self._transform_outline.setVisible(visible)

    def _layer_bounds_change_slot(self, layer: ImageLayer, bounds: QRect) -> None:
        if layer != self._layer_stack.get_layer_by_id(self._active_layer_id):
            layer.visibility_changed.disconnect(self._layer_visibility_slot)
            return
        self._transform_outline.setPos(bounds.topLeft())

    def _layer_content_change_slot(self, layer: ImageLayer) -> None:
        if layer != self._layer_stack.get_layer_by_id(self._active_layer_id):
            layer.visibility_changed.disconnect(self._layer_visibility_slot)
            return
        self._reload_scene_item()

    def _transformation_change_slot(self, offset: QPointF, x_scale: float, y_scale: float, rotation: float) -> None:
        layer = self._layer_stack.get_layer_by_id(self._active_layer_id)
        if layer is None:
            return
        controls = (
            (self._x_pos_box, self._transform_outline.x, self.set_x),
            (self._y_pos_box, self._transform_outline.y, self.set_y),
            (self._width_box, self._transform_outline.width, self.set_width),
            (self._height_box, self._transform_outline.height, self.set_height),
            (self._x_scale_box, x_scale, self.set_x_scale),
            (self._y_scale_box, y_scale, self.set_y_scale),
            (self._rotate_box, rotation, self.set_rotation)
        )
        for field, _, change_handler in controls:
            field.valueChanged.disconnect(change_handler)

        for field, value, _ in controls:
            if field.value() != value:
                field.setValue(float(value) if isinstance(field, QDoubleSpinBox) else int(value))

        for field, _, change_handler in controls:
            field.valueChanged.connect(change_handler)


