"""An image editing tool that moves the selected editing region."""
from typing import Optional, Dict, cast, Tuple, Callable

from PyQt5.QtCore import Qt, QRect, QRectF, QSize, QPoint
from PyQt5.QtGui import QCursor, QIcon, QKeySequence, QTransform, QPen, QPaintEvent, QPainter, QColor, \
    QPolygon
from PyQt5.QtWidgets import QWidget, QLabel, QSpinBox, QDoubleSpinBox, QCheckBox, QGridLayout, QPushButton, QSizePolicy, \
    QGraphicsRectItem

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.tools.base_tool import BaseTool
from src.ui.graphics_items.transform_outline import TransformOutline
from src.ui.image_viewer import ImageViewer
from src.ui.widget.key_hint_label import KeyHintLabel
from src.ui.widget.reactive_layout_widget import ReactiveLayoutWidget
from src.undo_stack import commit_action
from src.util.display_size import find_text_size
from src.util.geometry_utils import get_scaled_placement, get_rect_transformation
from src.util.image_utils import get_transparency_tile_pixmap
from src.util.shared_constants import FLOAT_MIN, FLOAT_MAX, MIN_NONZERO, INT_MAX

CLEAR_BUTTON_TEXT = 'Clear'

CONTROL_GRID_SPACING = 10

X_LABEL = "X:"
Y_LABEL = "Y:"
X_SCALE_LABEL = "X-Scale:"
Y_SCALE_LABEL = "Y-Scale:"
WIDTH_LABEL = "W:"
HEIGHT_LABEL = "H:"
DEGREE_LABEL = 'Angle:'

TRANSFORM_LABEL = 'Transform Layers'
TRANSFORM_TOOLTIP = 'Move, scale, or rotate the active layer.'
RESOURCES_TRANSFORM_TOOL_ICON = 'resources/icons/layer_transform_icon.svg'
ASPECT_RATIO_CHECK_LABEL = 'Keep aspect ratio'
RESET_BUTTON_TEXT = 'Reset'
TRANSFORM_CONTROL_HINT = 'LMB+drag:move layer -'

SCALE_STEP = 0.05
MIN_WIDTH_FOR_PREVIEW = 600


class LayerTransformTool(BaseTool):
    """Applies transformations to the active layer."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        super().__init__()
        self._image_stack = image_stack
        self._image_viewer = image_viewer
        self._icon = QIcon(RESOURCES_TRANSFORM_TOOL_ICON)
        self._initial_transform = QTransform()
        self._parent_item: Optional[QGraphicsRectItem] = None
        self._transform_outline = TransformOutline(QRect())
        self._transform_outline.offset_changed.connect(self._offset_change_slot)
        self._transform_outline.scale_changed.connect(self._scale_change_slot)
        self._transform_outline.angle_changed.connect(self._angle_change_slot)
        self._transform_outline.transform_changed.connect(self._transform_change_slot)
        self._transform_outline.setVisible(False)
        scene = image_viewer.scene()
        assert scene is not None
        scene.addItem(self._transform_outline)
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)
        self._active_layer_id = None

        # prepare control panel, wait to fully initialize
        self._control_panel = ReactiveLayoutWidget()
        self._control_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._control_layout: Optional[QGridLayout] = None
        self._preview = _TransformPreview(image_stack.size, QRect(), QTransform())
        image_stack.size_changed.connect(self._preview.set_image_size)

        def _init_control(default_val, min_val, max_val, change_fn):
            new_control = QSpinBox() if isinstance(default_val, int) else QDoubleSpinBox()
            new_control.setRange(min_val, max_val)
            new_control.setValue(default_val)
            new_control.valueChanged.connect(change_fn)
            return new_control

        self._x_pos_box = _init_control(0.0, FLOAT_MIN, FLOAT_MAX, self.set_x)
        self._y_pos_box = _init_control(0.0, FLOAT_MIN, FLOAT_MAX, self.set_y)
        edit_size = AppConfig().get(AppConfig.EDIT_SIZE)
        self._width_box = _init_control(float(edit_size.width()), MIN_NONZERO, FLOAT_MAX, self.set_width)
        self._height_box = _init_control(float(edit_size.height()), MIN_NONZERO, FLOAT_MAX, self.set_height)

        self._x_scale_box = _init_control(1.0, FLOAT_MIN, FLOAT_MAX, self.set_x_scale)
        self._y_scale_box = _init_control(1.0, FLOAT_MIN, FLOAT_MAX, self.set_y_scale)

        for scale_box in (self._y_scale_box, self._x_scale_box):
            scale_box.setSingleStep(SCALE_STEP)
        self._height_box = _init_control(float(edit_size.height()), MIN_NONZERO, FLOAT_MAX, self.set_height)
        self._rotate_box = _init_control(0.0, FLOAT_MIN, FLOAT_MAX, self.set_rotation)
        self._aspect_ratio_checkbox = QCheckBox()
        self._aspect_ratio_checkbox.setText(ASPECT_RATIO_CHECK_LABEL)
        self._down_keys: Dict[QWidget, QKeySequence] = {}
        self._up_keys: Dict[QWidget, QKeySequence] = {}

        self._reset_button = QPushButton()
        self._reset_button.setText(RESET_BUTTON_TEXT)
        self._reset_button.clicked.connect(self.reset_transformation)

        self._clear_button = QPushButton()
        self._clear_button.setText(CLEAR_BUTTON_TEXT)
        self._clear_button.clicked.connect(lambda: self._transform_outline.setTransform(QTransform()))

        def _restore_aspect_ratio() -> None:
            self._transform_outline.preserve_aspect_ratio = self._aspect_ratio_checkbox.isChecked()

        self._aspect_ratio_checkbox.clicked.connect(_restore_aspect_ratio)

        # Register movement key overrides, tied to control panel visibility:
        config = KeyConfig()
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
        return KeyConfig().get_keycodes(KeyConfig.TRANSFORM_TOOL_KEY)

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
        max_scale = max(self._transform_outline.transform_scale)
        self._transform_outline.transform_scale = (max_scale, max_scale)

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        if self._control_layout is not None:
            return self._control_panel
        self._control_layout = QGridLayout(self._control_panel)
        self._control_panel.setContentsMargins(0, 0, 0, 0)
        self._control_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        grid = self._control_layout
        grid.setAlignment(Qt.AlignCenter)
        grid.setSpacing(CONTROL_GRID_SPACING)

        labels = [X_LABEL, Y_LABEL, WIDTH_LABEL, HEIGHT_LABEL, X_SCALE_LABEL, Y_SCALE_LABEL, DEGREE_LABEL,
                  ASPECT_RATIO_CHECK_LABEL]
        controls = [self._x_pos_box, self._y_pos_box, self._width_box, self._height_box, self._x_scale_box,
                    self._y_scale_box, self._rotate_box, self._aspect_ratio_checkbox]

        label_width = 0
        label_height = 0
        for label in labels:
            text_size = find_text_size(label)
            label_width = max(text_size.width(), label_width)
            label_height = max(text_size.height(), label_height)

        def _get_down_hint(control: QWidget) -> Optional[KeyHintLabel]:
            if control in self._down_keys:
                down_hint_widget = KeyHintLabel(self._down_keys[control])
                down_hint_widget.setAlignment(cast(Qt.Alignment,
                                                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                return down_hint_widget
            return None

        def _get_up_hint(control: QWidget) -> Optional[KeyHintLabel]:
            if control in self._up_keys:
                up_hint_widget = KeyHintLabel(self._up_keys[control])
                up_hint_widget.setAlignment(cast(Qt.Alignment,
                                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
                return up_hint_widget
            return None

        down_control_hints = [_get_down_hint(control) for control in controls]
        up_control_hints = [_get_up_hint(control) for control in controls]
        item_map = {}
        for i in range(len(labels)):
            item_map[labels[i]] = (controls[i], down_control_hints[i], up_control_hints[i])
        item_map[RESET_BUTTON_TEXT] = (self._reset_button, None, None)
        item_map[CLEAR_BUTTON_TEXT] = (self._clear_button, None, None)

        control_width = 0
        control_height = 0
        for control, down_hint, up_hint in zip(controls, down_control_hints, up_control_hints):
            control_size = control.minimumSize()
            hint_size = QSize()
            if down_hint is not None:
                hint_size = down_hint.sizeHint()
            if up_hint is not None:
                up_hint_size = up_hint.sizeHint()
                hint_size = QSize(up_hint_size.width() + hint_size.width(),
                                  max(hint_size.height(), up_hint_size.height()))
            width = control_size.width() + hint_size.width()
            if control == self._aspect_ratio_checkbox:
                width -= label_width
            control_width = max(width, control_width)
            control_height = max(control_size.height() + hint_size.height(), control_height)

        column_width = label_width + control_width + CONTROL_GRID_SPACING
        row_height = max(label_height, control_height) + CONTROL_GRID_SPACING
        preview_size = self._preview.sizeHint()

        # Layout setup functions:
        def _clear_grid() -> None:
            while grid.count() > 0:
                item = grid.itemAt(0)
                assert item is not None
                widget = item.widget()
                assert widget is not None
                widget.hide()
                grid.removeItem(item)
            for row_num in range(grid.rowCount()):
                grid.setRowStretch(row_num, 0)
            for col_num in range(grid.columnCount()):
                grid.setColumnStretch(col_num, 0)

        def _get_grid_item(row: int, column: int) -> Tuple[QWidget | None, int, int]:
            item = grid.itemAtPosition(row, column)
            if item is None:
                return None, 0, 0
            widget = item.widget()
            if widget is None:
                return None, 0, 0
            index = grid.indexOf(widget)
            _, _, row_span, column_span = grid.getItemPosition(index)
            assert row_span is not None
            assert column_span is not None
            return widget, row_span, column_span

        def _set_grid_weights() -> None:
            row_heights = {}
            column_widths = {}
            for row in range(grid.rowCount()):
                if row not in row_heights:
                    row_heights[row] = grid.rowStretch(row)
                for column in range(grid.columnCount()):
                    if column not in column_widths:
                        column_widths[column] = grid.columnStretch(column)
                    widget, row_span, column_span = _get_grid_item(row, column)
                    if widget is not None:
                        widget_size = widget.sizeHint()
                        row_heights[row] = max(row_heights[row], widget_size.height() // row_span)
                        column_widths[column] = max(column_widths[column], widget_size.width() // column_span)
            for row, stretch in row_heights.items():
                grid.setRowStretch(row, stretch)
            for column, stretch in column_widths.items():
                grid.setColumnStretch(column, stretch)

        def _add_control(label_text: str, row: int, column: int, use_hints: bool = True) -> None:
            control, up_key_hint, down_key_hint = item_map[label_text]
            if use_hints is False:
                up_key_hint = None
                down_key_hint = None
            grid_column = column * 4
            if not isinstance(control, (QPushButton, QCheckBox)):
                grid.addWidget(QLabel(label_text), row, grid_column, 1, 2 if up_key_hint is None else 1)
            if up_key_hint is not None:
                grid.addWidget(up_key_hint, row, grid_column + 1)
                up_key_hint.show()
            grid.addWidget(control, row, grid_column + 2)
            control.show()
            if down_key_hint is not None:
                grid.addWidget(down_key_hint, row, grid_column + 3)
                down_key_hint.show()

        self._control_panel.setMinimumWidth(column_width - 10)
        self._control_panel.setMinimumHeight(row_height * 3)
        wide_layout_size = QSize(column_width * 3, row_height * 3)
        extra_wide_layout_size = QSize(wide_layout_size.width() + preview_size.width(),
                                       max(wide_layout_size.height(), preview_size.height()))

        tall_layout_size = QSize(column_width, row_height * len(controls))
        extra_tall_layout_size = QSize(tall_layout_size.width(), tall_layout_size.height() + preview_size.height())

        # Wide layout: 3x3 control grid
        def _build_wide_layout() -> None:
            _clear_grid()
            grid.setRowStretch(0, 50)
            _add_control(X_LABEL, 1, 0)
            _add_control(Y_LABEL, 1, 1)
            _add_control(DEGREE_LABEL, 1, 2)
            _add_control(WIDTH_LABEL, 2, 0)
            _add_control(HEIGHT_LABEL, 2, 1)
            _add_control(ASPECT_RATIO_CHECK_LABEL, 2, 2)
            _add_control(X_SCALE_LABEL, 3, 0)
            _add_control(Y_SCALE_LABEL, 3, 1)
            _add_control(RESET_BUTTON_TEXT, 3, 2)
            grid.addWidget(self._clear_button, 3, 8)
            self._clear_button.show()
            grid.setRowStretch(4, 100)
            _set_grid_weights()

        wide_layout_max = QSize(extra_wide_layout_size.width() - 1, INT_MAX)
        self._control_panel.add_layout_mode('wide layout', _build_wide_layout, wide_layout_size, wide_layout_max)

        # Extra wide layout: wide layout + preview
        def _build_extra_wide_layout() -> None:
            _build_wide_layout()
            grid.addWidget(self._preview, 0, 12, grid.rowCount(), 1)
            preview_stretch = 0
            for row in range(grid.rowCount()):
                preview_stretch += grid.rowStretch(row)
            grid.setColumnStretch(12, preview_stretch)
            self._preview.show()
        extra_wide_layout_max = QSize(INT_MAX, INT_MAX)
        self._control_panel.add_layout_mode('extra wide layout', _build_extra_wide_layout,
                                            extra_wide_layout_size, extra_wide_layout_max)

        # Tall layout: one column
        def _build_tall_layout() -> None:
            _clear_grid()
            _add_control(X_LABEL, 0, 0)
            _add_control(Y_LABEL, 1, 0)
            _add_control(WIDTH_LABEL, 2, 0)
            _add_control(HEIGHT_LABEL, 3, 0)
            _add_control(X_SCALE_LABEL, 4, 0)
            _add_control(Y_SCALE_LABEL, 5, 0)
            _add_control(DEGREE_LABEL, 6, 0)
            grid.addWidget(self._aspect_ratio_checkbox, 7, 0, 1, 4)
            self._aspect_ratio_checkbox.show()
            grid.addWidget(self._reset_button, 8, 0, 1, 4)
            self._reset_button.show()
            grid.addWidget(self._clear_button, 8, 0, 1, 4)
            self._clear_button.show()
            _set_grid_weights()
        self._control_panel.add_layout_mode('tall layout', _build_tall_layout, tall_layout_size,
                                            QSize(wide_layout_size.width() - 1, extra_tall_layout_size.height() - 1))

        # Extra tall layout: add preview

        def _build_extra_tall_layout() -> None:
            _clear_grid()
            grid.setRowStretch(0, 30)
            grid.setRowStretch(1, 30)
            grid.addWidget(self._preview, 1, 1, 1, 4)
            self._preview.show()
            grid.setRowStretch(2, 100)
            _add_control(X_LABEL, 3, 0)
            _add_control(Y_LABEL, 4, 0)
            _add_control(WIDTH_LABEL, 5, 0)
            _add_control(HEIGHT_LABEL, 6, 0)
            _add_control(X_SCALE_LABEL, 7, 0)
            _add_control(Y_SCALE_LABEL, 8, 0)
            _add_control(DEGREE_LABEL, 9, 0)
            grid.addWidget(self._aspect_ratio_checkbox, 10, 0, 1, 4)
            self._aspect_ratio_checkbox.show()
            grid.addWidget(self._reset_button, 11, 0, 1, 4)
            self._reset_button.show()
            grid.addWidget(self._clear_button, 12, 0, 1, 4)
            self._clear_button.show()
            grid.setRowStretch(13, 30)
            _set_grid_weights()
        self._control_panel.add_layout_mode('extra tall layout', _build_extra_tall_layout, extra_tall_layout_size,
                                            QSize(wide_layout_size.width() - 1, INT_MAX))

        # Reduced layout: leave out width, height, control hints
        def _build_reduced_layout() -> None:
            _clear_grid()
            _add_control(X_LABEL, 0, 0)
            _add_control(Y_LABEL, 1, 0)
            _add_control(X_SCALE_LABEL, 2, 0)
            _add_control(Y_SCALE_LABEL, 3, 0)
            _add_control(DEGREE_LABEL, 4, 0)
            grid.addWidget(self._aspect_ratio_checkbox, 5, 0, 1, 3)
            self._aspect_ratio_checkbox.show()
            grid.addWidget(self._reset_button, 6, 0)
            grid.addWidget(self._clear_button, 6, 2)
            self._reset_button.show()
            self._clear_button.show()
            for hint_widget in [*up_control_hints, *down_control_hints]:
                if hint_widget is not None:
                    grid.removeWidget(hint_widget)
                    hint_widget.hide()
            _set_grid_weights()
        self._control_panel.add_default_layout_mode(_build_reduced_layout)

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
        if self._aspect_ratio_checkbox.isChecked():
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
        last_layer = self._image_stack.get_layer_by_id(self._active_layer_id)
        if last_layer is not None:
            last_layer.transform_changed.disconnect(self._layer_transform_change_slot)
            last_layer.z_value_changed.disconnect(self._layer_z_value_change_slot)
            last_layer.size_changed.disconnect(self._layer_size_change_slot)
        self._active_layer_id = None if layer is None else layer.id
        self._reload_scene_item()
        if layer is not None:
            layer.transform_changed.connect(self._layer_transform_change_slot)
            layer.z_value_changed.connect(self._layer_z_value_change_slot)
            layer.size_changed.connect(self._layer_size_change_slot)
        else:
            self._preview.set_layer_bounds(QRect())
            self._transform_outline.setVisible(False)

    def reset_transformation(self) -> None:
        """Resets the transformation to its previous state."""
        layer = self._image_stack.active_layer
        if layer is not None and self.is_active:
            changed_transform = self._transform_outline.transform()
            source_transform = self._initial_transform
            if changed_transform != source_transform:

                def _apply(active=layer, matrix=source_transform):
                    active.set_transform(matrix)

                def _undo(active=layer, matrix=changed_transform):
                    active.set_transform(matrix)

                commit_action(_apply, _undo, 'LayerTransformTool.reset_transformation')
            self._transform_outline.setTransform(self._initial_transform)

    def _reload_scene_item(self):
        """Reset all transformations and reload properties from the layer."""
        layer = self._image_stack.active_layer

        # Clear old transform outline:
        self._transform_outline.offset_changed.disconnect(self._offset_change_slot)
        self._transform_outline.scale_changed.disconnect(self._scale_change_slot)
        self._transform_outline.angle_changed.disconnect(self._angle_change_slot)
        self._transform_outline.transform_changed.disconnect(self._transform_change_slot)
        scene = self._transform_outline.scene()
        if scene is not None:
            scene.removeItem(self._transform_outline)
            if self._parent_item is not None:
                scene.removeItem(self._parent_item)
        scene = self._image_viewer.scene()
        assert scene is not None

        # Re-create for new layer:
        layer_parent = None if layer is None else layer.parent
        if layer_parent is not None:
            self._parent_item = QGraphicsRectItem(QRectF(layer_parent.local_bounds))
            self._parent_item.setBrush(Qt.transparent)
            self._parent_item.setPen(Qt.transparent)
            self._parent_item.setTransform(layer_parent.transform)
            scene.addItem(self._parent_item)
        else:
            self._parent_item = None
        self._transform_outline = TransformOutline(QRectF() if layer is None else QRectF(layer.local_bounds),
                                                   parent=self._parent_item)
        self._transform_outline.offset_changed.connect(self._offset_change_slot)
        self._transform_outline.scale_changed.connect(self._scale_change_slot)
        self._transform_outline.angle_changed.connect(self._angle_change_slot)
        self._transform_outline.transform_changed.connect(self._transform_change_slot)
        self._transform_outline.setVisible(False)
        if self._transform_outline.scene() is None:
            scene.addItem(self._transform_outline)

        # Load layer image, set visibility and zValues:
        if layer is None or layer.id != self._active_layer_id:
            self._transform_outline.setVisible(False)
        self._transform_outline.prepareGeometryChange()
        if layer is None:
            self._transform_outline.setRect(QRectF())
            self._preview.set_layer_bounds(QRect())
            self._preview.set_transform(QTransform())
            self._transform_outline.setVisible(False)
        else:
            self._initial_transform = layer.transform
            self._preview.set_layer_bounds(layer.local_bounds)
            self._preview.set_transform(layer.full_image_transform)
            self._transform_outline.setVisible(layer.visible)
            self._transform_outline.setZValue(layer.z_value + 1)
            self._transform_outline.setTransform(self._initial_transform)
        self._update_all_controls()

    def _on_activate(self) -> None:
        """Connect to the active layer."""
        self._image_stack.active_layer_changed.connect(self._active_layer_change_slot)
        self.set_layer(self._image_stack.active_layer)

    def _on_deactivate(self) -> None:
        """Disconnect from all layers."""
        self._image_stack.active_layer_changed.disconnect(self._active_layer_change_slot)
        self.set_layer(None)

    def _active_layer_change_slot(self, active_layer: Layer) -> None:
        self.set_layer(active_layer)

    def _layer_z_value_change_slot(self, layer: Layer, z_value: int) -> None:
        if layer != self._image_stack.get_layer_by_id(self._active_layer_id):
            layer.z_value_changed.disconnect(self._layer_z_value_change_slot)
            return
        self._transform_outline.setZValue(z_value + 1)

    # noinspection PyUnusedLocal
    def _layer_transform_change_slot(self, layer: Layer, transform: QTransform) -> None:
        if layer != self._image_stack.get_layer_by_id(self._active_layer_id):
            layer.transform_changed.disconnect(self._layer_transform_change_slot)
            return
        if transform != self._transform_outline.transform():
            self._transform_outline.setTransform(transform)

    # noinspection PyUnusedLocal
    def _layer_size_change_slot(self, layer: Layer, size: QSize) -> None:
        if layer != self._image_stack.get_layer_by_id(self._active_layer_id):
            layer.size_changed.disconnect(self._layer_size_change_slot)
            return
        self._reload_scene_item()

    def _transform_change_slot(self, transform: QTransform) -> None:
        layer = self._image_stack.get_layer_by_id(self._active_layer_id)
        if layer is None:
            return
        try:
            layer.transform = transform
        except RuntimeError:  # undo stack conflict, just don't register this one in the undo history
            layer.set_transform(transform)
        self._preview.set_transform(layer.full_image_transform)

    @staticmethod
    def _update_control(field: QWidget, value: float, change_handler: Callable[..., None]):
        assert hasattr(field, 'valueChanged')
        assert hasattr(field, 'setValue')
        field.valueChanged.disconnect(change_handler)
        if field.value() != value:
            field.setValue(float(value) if isinstance(field, QDoubleSpinBox) else int(value))
        field.valueChanged.connect(change_handler)

    def _offset_change_slot(self, *unused_args) -> None:
        self._update_control(self._x_pos_box, self._transform_outline.x_pos, self.set_x)
        self._update_control(self._y_pos_box, self._transform_outline.y_pos, self.set_y)

    def _scale_change_slot(self, x_scale: float, y_scale: float) -> None:
        self._update_control(self._width_box, self._transform_outline.width, self.set_width),
        self._update_control(self._height_box, self._transform_outline.height, self.set_height)
        self._update_control(self._x_scale_box, x_scale, self.set_x_scale)
        self._update_control(self._y_scale_box, y_scale, self.set_y_scale)

    def _angle_change_slot(self, angle: float) -> None:
        self._update_control(self._rotate_box, angle, self.set_rotation)

    def _update_all_controls(self) -> None:
        self._offset_change_slot()
        self._scale_change_slot(*self._transform_outline.transform_scale)
        self._angle_change_slot(self._transform_outline.rotation_angle)


class _TransformPreview(QWidget):

    def __init__(self, image_size: QSize, layer_bounds: QRectF, layer_transform: QTransform) -> None:
        super().__init__()
        self._image_size = image_size
        self._layer_bounds = layer_bounds
        self._layer_transform = layer_transform
        self._brush = Qt.white
        self._pen = QPen(Qt.black, 3)
        self._pen.setCosmetic(True)
        self._background = get_transparency_tile_pixmap(image_size)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

    def sizeHint(self) -> QSize:
        """Preview size is capped at 200x200."""
        return QSize(200, 200)

    def set_image_size(self, new_size: QSize) -> None:
        """Update the previewed size of the edited image."""
        self._image_size = new_size
        self.update()

    def set_layer_bounds(self, new_bounds: QRect) -> None:
        """Update the previewed layer bounds."""
        self._layer_bounds = new_bounds
        self.update()

    def set_transform(self, new_transform: QTransform) -> None:
        """Update the previewed layer transformation."""
        self._layer_transform = new_transform
        self.update()

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        """Draw the transformed layer over the image bounds."""
        painter = QPainter(self)
        painter.drawTiledPixmap(QRect(QPoint(), self.size()), self._background)
        image_bounds = QRect(QPoint(), self._image_size)
        final_image_poly = self._layer_transform.map(QPolygon(self._layer_bounds))
        full_bounds = image_bounds.united(final_image_poly.boundingRect())
        scaled_full_bounds = get_scaled_placement(self.size(), full_bounds.size(), 4)
        initial_transform = get_rect_transformation(full_bounds, scaled_full_bounds)
        image_bounds_color = QColor(Qt.black)
        image_bounds_color.setAlphaF(0.3)
        painter.setTransform(initial_transform)
        painter.fillRect(image_bounds, image_bounds_color)
        if not self._layer_bounds.isNull():
            painter.setTransform(self._layer_transform, True)
            painter.setPen(self._pen)
            painter.setBrush(self._brush)
            painter.fillRect(self._layer_bounds, self._brush)
            painter.drawRect(self._layer_bounds)
        painter.end()
