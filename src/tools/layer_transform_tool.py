"""An image editing tool that moves the selected editing region."""
from typing import Optional, Dict

from PyQt5.QtCore import Qt, QPoint, QRect, QRectF
from PyQt5.QtGui import QMouseEvent, QCursor, QIcon, QTransform, QVector3D, QPixmap, QImage, QPainter, \
    QKeySequence
from PyQt5.QtWidgets import QWidget, QApplication, QLabel, QGraphicsPixmapItem, QGraphicsScale, \
    QGraphicsRotation, QGraphicsItem, QSpinBox, QDoubleSpinBox, \
    QCheckBox, QGridLayout, QPushButton

from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.image_layer import ImageLayer
from src.image.layer_stack import LayerStack
from src.tools.base_tool import BaseTool
from src.ui.image_viewer import ImageViewer
from src.ui.widget.key_hint_label import KeyHintLabel
from src.undo_stack import commit_action
from src.util.menu_action import INT_MAX

X_OFFSET_LABEL = "X Offset:"
Y_OFFSET_LABEL = "Y Offset:"
WIDTH_SCALE_LABEL = "Width scale:"
HEIGHT_SCALE_LABEL = "Height scale:"
DEGREE_LABEL = 'Rotation:'

TRANSFORM_LABEL = 'Transform Layers'
TRANSFORM_TOOLTIP = 'Move, scale, or rotate the active layer.'
RESOURCES_TRANSFORM_TOOL_ICON = 'resources/icons/layer_transform_icon.svg'
ASPECT_RATIO_CHECK_LABEL = 'Preserve aspect ratio:'
RESET_BUTTON_TEXT = 'Reset'

SCALE_STEP = 0.05
FLOAT_MAX = 99999.0
FLOAT_MIN = -99999.0


class LayerTransformTool(BaseTool):
    """Applies transformations to the active layer."""

    def __init__(self, layer_stack: LayerStack, image_viewer: ImageViewer) -> None:
        super().__init__()
        self._layer_stack = layer_stack
        self._image_viewer = image_viewer
        self._icon = QIcon(RESOURCES_TRANSFORM_TOOL_ICON)
        self._transform_pixmap = QGraphicsPixmapItem()
        self._transform_pixmap.setVisible(False)
        self._rotation = 0.0
        self._offset = QPoint()
        self._scale_x = 1.0
        self._scale_y = 1.0
        image_viewer.scene().addItem(self._transform_pixmap)
        self.cursor = QCursor(Qt.CursorShape.OpenHandCursor)
        self._dragging = False
        self._last_mouse_pos: Optional[QPoint] = None
        self._initial_layer_offset: Optional[QPoint] = None
        self._active_layer_id = None if layer_stack.active_layer is None else layer_stack.active_layer.id

        # prepare control panel, wait to fully initialize
        self._control_panel = QWidget()
        self._control_layout: Optional[QGridLayout] = None
        self._offset_box_x = QSpinBox()
        self._offset_box_x.valueChanged.connect(self._translate_x)
        self._offset_box_y = QSpinBox()
        self._offset_box_y.valueChanged.connect(self._translate_y)
        self._scale_box_x = QDoubleSpinBox()
        self._scale_box_x.setValue(1.0)
        self._scale_box_x.valueChanged.connect(self._set_scale_x)
        self._scale_box_y = QDoubleSpinBox()
        self._scale_box_y.setValue(1.0)
        self._scale_box_y.valueChanged.connect(self._set_scale_y)
        self._rotate_box = QDoubleSpinBox()
        self._rotate_box.valueChanged.connect(self.rotate)
        for float_box in (self._rotate_box, self._scale_box_x, self._scale_box_y):
            float_box.setRange(FLOAT_MIN, FLOAT_MAX)
        for scale_box in (self._scale_box_x, self._scale_box_y):
            scale_box.setSingleStep(SCALE_STEP)
        for int_box in (self._offset_box_x, self._offset_box_y):
            int_box.setRange(-INT_MAX + 1, INT_MAX)
        self._aspect_ratio_checkbox = QCheckBox()
        self._down_keys: Dict[QWidget, QKeySequence] = {}
        self._up_keys: Dict[QWidget, QKeySequence] = {}

        def _restore_aspect_ratio() -> None:
            if self._aspect_ratio_checkbox.isChecked() and self._active_layer_id is not None:
                max_scale = max(self._scale_x, self._scale_y)
                self.scale(max_scale, max_scale)

        self._aspect_ratio_checkbox.clicked.connect(_restore_aspect_ratio)

        # Register movement key overrides, tied to control panel visibility:
        config = KeyConfig.instance()
        for control, up_key_code, down_key_code in ((self._offset_box_x, KeyConfig.MOVE_RIGHT, KeyConfig.MOVE_LEFT),
                                                    (self._offset_box_y, KeyConfig.MOVE_DOWN, KeyConfig.MOVE_UP),
                                                    (self._scale_box_x, KeyConfig.PAN_RIGHT, KeyConfig.PAN_LEFT),
                                                    (self._scale_box_y, KeyConfig.PAN_UP, KeyConfig.PAN_DOWN),
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

        _add_control(X_OFFSET_LABEL, self._offset_box_x, 0, 0)
        _add_control(Y_OFFSET_LABEL, self._offset_box_y, 0, 4)

        _add_control(WIDTH_SCALE_LABEL, self._scale_box_x, 1, 0)
        _add_control(HEIGHT_SCALE_LABEL, self._scale_box_y, 1, 4)

        _add_control(DEGREE_LABEL, self._rotate_box, 2, 0)
        self._aspect_ratio_checkbox.setText(ASPECT_RATIO_CHECK_LABEL)
        _add_control('', self._aspect_ratio_checkbox, 3, 0)

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

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        if self._active_layer_id is None or event.buttons() != Qt.LeftButton \
                or QApplication.keyboardModifiers() != Qt.KeyboardModifier.NoModifier:
            return False
        self._dragging = True
        self._last_mouse_pos = image_coordinates
        self._initial_layer_offset = self._layer_stack.get_layer_by_id(self._active_layer_id).position
        return True

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        if event.buttons() != Qt.LeftButton or not self._dragging or self._last_mouse_pos is None \
                or self._initial_layer_offset is None:
            return False
        mouse_offset = image_coordinates - self._last_mouse_pos
        self.translate(self._offset + mouse_offset)
        self._last_mouse_pos = image_coordinates
        return True

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        self._dragging = False
        self._initial_layer_offset = None
        self._last_mouse_pos = None
        return True

    def translate(self, offset: QPoint) -> None:
        """Update the transformation x,y offset."""
        if self._offset != offset:
            self._offset = offset
            self._apply_transformations_to_view()
            if self._offset_box_x.value() != offset.x():
                self._offset_box_x.setValue(offset.x())
            if self._offset_box_y.value() != offset.y():
                self._offset_box_y.setValue(offset.y())

    def rotate(self, degrees: float) -> None:
        """Update the transformation rotation in degrees"""
        if self._rotation != degrees:
            self._rotation = degrees
            self._apply_transformations_to_view()
            if degrees != self._rotate_box.value():
                self._rotate_box.setValue(degrees)

    def scale(self, x_scale: float, y_scale: float) -> None:
        """Update the transformation scale."""
        if self._scale_x != x_scale or self._scale_y != y_scale:
            self._scale_x = x_scale
            self._scale_y = y_scale
            self._apply_transformations_to_view()
            if x_scale != self._scale_box_x.value():
                self._scale_box_x.setValue(x_scale)
            if y_scale != self._scale_box_y.value():
                self._scale_box_y.setValue(y_scale)

    def _on_activate(self) -> None:
        """Connect to the active layer."""
        self._layer_stack.active_layer_changed.connect(self._active_layer_change_slot)
        self.set_layer(self._layer_stack.active_layer)

    def _on_deactivate(self) -> None:
        """Disconnect from all layers."""
        self._layer_stack.active_layer_changed.disconnect(self._active_layer_change_slot)
        self.set_layer(None)

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
        else:
            self._transform_pixmap.setPixmap(QPixmap())
            self._transform_pixmap.setVisible(False)

    def apply_transformations_to_layer(self) -> None:
        """Applies all pending transformations to the source layer."""
        layer = self._layer_stack.get_layer_by_id(self._active_layer_id)
        if layer is None:
            return
        if (self._rotation % 360.0) == 0.0 and self._scale_x == 1.0 and self._scale_y == 1.0 \
                and self._offset == QPoint():
            return
        bounds = self._transform_pixmap.boundingRect()
        bounds = self._transform_pixmap.mapRectToScene(bounds)
        if (self._rotation % 360.0) != 0.0 or self._scale_x != 1.0 or self._scale_y != 1.0:
            transform_image = QImage(bounds.size().toSize(), QImage.Format.Format_ARGB32_Premultiplied)
            transform_image.fill(Qt.GlobalColor.transparent)
            # Temporarily hide everything else in the scene:
            visibility_map: Dict[QGraphicsItem: bool] = {}
            for item in self._image_viewer.scene().items():
                visibility_map[item] = item.isVisible()
                item.setVisible(False)
            self._image_viewer.scene().update()
            self._transform_pixmap.setVisible(True)
            # Render the scene into the image:
            painter = QPainter(transform_image)
            self._image_viewer.scene().render(painter, QRectF(QPoint(), bounds.size()), bounds)
            painter.end()
            # Restore previous scene item visibility:
            for scene_item, visibility in visibility_map.items():
                scene_item.setVisible(visibility)
            source_image = layer.qimage
        else:
            source_image = None
            transform_image = None
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
        self._offset = QPoint()
        self._rotation = 0
        self._scale_y = 1.0
        self._scale_x = 1.0
        self._transform_pixmap.setTransform(QTransform(), False)
        self._transform_pixmap.setTransformations([])
        layer = self._layer_stack.active_layer
        if layer is None or layer.id != self._active_layer_id:
            self._transform_pixmap.setPixmap(QPixmap())
            self._transform_pixmap.setVisible(False)
        self._transform_pixmap.prepareGeometryChange()
        if layer is None:
            self._transform_pixmap.setPos(0, 0)
            self._transform_pixmap.setPixmap(QPixmap())
            self._transform_pixmap.setVisible(False)
        else:
            self._transform_pixmap.setPos(layer.position.x(), layer.position.y())
            self._transform_pixmap.setPixmap(layer.pixmap)
            self._transform_pixmap.setVisible(layer.visible)
            self._transform_pixmap.setZValue(-self._layer_stack.get_layer_index(layer))
        self._offset_box_x.setValue(0)
        self._offset_box_y.setValue(0)
        self._scale_box_x.setValue(1.0)
        self._scale_box_y.setValue(1.0)
        self._rotate_box.setValue(0.0)

    def _translate_x(self, x_offset: int) -> None:
        self.translate(QPoint(x_offset, self._offset.y()))

    def _translate_y(self, y_offset: int) -> None:
        self.translate(QPoint(self._offset.x(), y_offset))

    def _set_scale_x(self, x_scale: float) -> None:
        y_scale = self._scale_y
        if self._aspect_ratio_checkbox.isChecked():
            y_scale = x_scale
        self.scale(x_scale, y_scale)

    def _set_scale_y(self, y_scale: float) -> None:
        x_scale = self._scale_x
        if self._aspect_ratio_checkbox.isChecked():
            x_scale = y_scale
        self.scale(x_scale, y_scale)

    def _apply_transformations_to_view(self) -> None:
        layer = self._layer_stack.active_layer
        if layer is None or layer.id != self._active_layer_id:
            return
        self._transform_pixmap.setTransform(QTransform(), False)
        self._transform_pixmap.setTransformations([])

        x0 = int(self._transform_pixmap.pos().x())
        y0 = int(self._transform_pixmap.pos().y())
        width = int(self._transform_pixmap.pixmap().size().width())
        height = int(self._transform_pixmap.pixmap().size().height())

        offset = QTransform()
        offset.translate(self._offset.x(), self._offset.y())
        self._transform_pixmap.setTransform(offset, False)

        graphics_transforms = []
        center = QVector3D(QPoint(x0 + self._offset.x() + width // 2, y0 + self._offset.y() + height // 2))

        rotation = QGraphicsRotation()
        rotation.setOrigin(center)
        rotation.setAngle(self._rotation)
        graphics_transforms.append(rotation)
        scale_transform = QGraphicsScale()
        scale_transform.setOrigin(center)
        scale_transform.setXScale(self._scale_x)
        scale_transform.setYScale(self._scale_y)
        graphics_transforms.append(scale_transform)

        self._transform_pixmap.setTransformations(graphics_transforms)

    def _active_layer_change_slot(self, layer_id: int, layer_index: int) -> None:
        print(f'active layer now {layer_id}')
        if layer_id == self._active_layer_id:
            self._transform_pixmap.setZValue(-layer_index)
        else:
            self.set_layer(self._layer_stack.get_layer_by_id(layer_id))

    def _layer_visibility_slot(self, layer: ImageLayer, visible: bool) -> None:
        if layer != self._layer_stack.get_layer_by_id(self._active_layer_id):
            layer.visibility_changed.disconnect(self._layer_visibility_slot)
            return
        self._transform_pixmap.setVisible(visible)

    def _layer_bounds_change_slot(self, layer: ImageLayer, bounds: QRect) -> None:
        if layer != self._layer_stack.get_layer_by_id(self._active_layer_id):
            layer.visibility_changed.disconnect(self._layer_visibility_slot)
            return
        self._transform_pixmap.setPos(bounds.topLeft())

    def _layer_content_change_slot(self, layer: ImageLayer) -> None:
        if layer != self._layer_stack.get_layer_by_id(self._active_layer_id):
            layer.visibility_changed.disconnect(self._layer_visibility_slot)
            return
        self._reload_scene_item()
