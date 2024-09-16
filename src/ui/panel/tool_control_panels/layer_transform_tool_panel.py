"""Control panel for the layer transformation tool."""
from typing import Optional, Tuple, Dict

from PySide6.QtCore import QRect, QPoint, QSize, QRectF, Signal, QSignalBlocker
from PySide6.QtGui import QPaintEvent, QTransform, QColor, Qt, QPolygonF, QPainter, QPen, QKeySequence
from PySide6.QtWidgets import QSizePolicy, QApplication, QGridLayout, QWidget, QDoubleSpinBox, QCheckBox, QSpinBox, \
    QPushButton, QLabel

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.layers.image_stack import ImageStack
from src.ui.input_fields.check_box import CheckBox
from src.ui.layout.reactive_layout_widget import ReactiveLayoutWidget
from src.ui.widget.key_hint_label import KeyHintLabel
from src.util.shared_constants import FLOAT_MIN, FLOAT_MAX, MIN_NONZERO, ASPECT_RATIO_CHECK_LABEL, INT_MAX
from src.util.visual.geometry_utils import get_rect_transformation, get_scaled_placement
from src.util.visual.image_utils import get_transparency_tile_pixmap
from src.util.visual.text_drawing_utils import find_text_size

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.layer_transform_tool_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


X_LABEL = _tr('X:')
Y_LABEL = _tr('Y:')
X_SCALE_LABEL = _tr('X-Scale:')
Y_SCALE_LABEL = _tr('Y-Scale:')
WIDTH_LABEL = _tr('W:')
HEIGHT_LABEL = _tr('H:')
DEGREE_LABEL = _tr('Angle:')
RESET_BUTTON_TEXT = _tr('Reset')
CLEAR_BUTTON_TEXT = _tr('Clear')

SCALE_STEP = 0.05
MIN_WIDTH_FOR_PREVIEW = 600
CONTROL_GRID_SPACING = 10


class LayerTransformToolPanel(ReactiveLayoutWidget):
    """Control panel for the layer transformation tool."""

    x_changed = Signal(float)
    y_changed = Signal(float)
    width_changed = Signal(float)
    height_changed = Signal(float)
    x_scale_changed = Signal(float)
    y_scale_changed = Signal(float)
    angle_changed = Signal(float)
    preserve_aspect_ratio_changed = Signal(bool)
    reset_signal = Signal()
    clear_signal = Signal()

    def __init__(self, image_stack: ImageStack):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self._layout = QGridLayout(self)
        self._preview = _TransformPreview(image_stack.size, QRectF(), QTransform())
        image_stack.size_changed.connect(self._preview.set_image_size)

        def _init_control(default_val, min_val, max_val, signal):
            new_control = QSpinBox() if isinstance(default_val, int) else QDoubleSpinBox()
            new_control.setRange(min_val, max_val)
            new_control.setValue(default_val)
            new_control.valueChanged.connect(signal)
            return new_control

        self._x_pos_box = _init_control(0.0, FLOAT_MIN, FLOAT_MAX, self.x_changed)
        self._y_pos_box = _init_control(0.0, FLOAT_MIN, FLOAT_MAX, self.y_changed)
        edit_size = Cache().get(Cache.EDIT_SIZE)
        self._width_box = _init_control(float(edit_size.width()), MIN_NONZERO, FLOAT_MAX, self.width_changed)
        self._height_box = _init_control(float(edit_size.height()), MIN_NONZERO, FLOAT_MAX, self.height_changed)

        self._x_scale_box = _init_control(1.0, FLOAT_MIN, FLOAT_MAX, self.x_scale_changed)
        self._y_scale_box = _init_control(1.0, FLOAT_MIN, FLOAT_MAX, self.y_scale_changed)

        for scale_box in (self._y_scale_box, self._x_scale_box):
            scale_box.setSingleStep(SCALE_STEP)
        self._rotate_box = _init_control(0.0, FLOAT_MIN, FLOAT_MAX, self.angle_changed)
        self._aspect_ratio_checkbox = CheckBox()
        self._aspect_ratio_checkbox.setText(ASPECT_RATIO_CHECK_LABEL)
        self._aspect_ratio_checkbox.valueChanged.connect(self.preserve_aspect_ratio_changed)
        self._modifier_set_aspect_ratio = False

        # Holding the aspect ratio modifier should enable fixed aspect ratio and releasing it should reset it, but
        # make sure the modifier is ignored if it's explicitly checked.
        def _set_checkbox_when_modifier_held(modifiers: Qt.KeyboardModifier) -> None:
            if self.isVisible() and not self._aspect_ratio_checkbox.isChecked() and \
                    KeyConfig.modifier_held(KeyConfig.FIXED_ASPECT_MODIFIER, held_modifiers=modifiers):
                self._modifier_set_aspect_ratio = True
                self._aspect_ratio_checkbox.setChecked(True)
            elif self.isVisible() and self._aspect_ratio_checkbox.isChecked() and self._modifier_set_aspect_ratio \
                    and not KeyConfig.modifier_held(KeyConfig.FIXED_ASPECT_MODIFIER, held_modifiers=modifiers):
                self._aspect_ratio_checkbox.setChecked(False)
        HotkeyFilter.instance().modifiers_changed.connect(_set_checkbox_when_modifier_held)

        self._down_keys: Dict[QWidget, Tuple[QKeySequence, str]] = {}
        self._up_keys: Dict[QWidget, Tuple[QKeySequence, str]] = {}

        self._reset_button = QPushButton()
        self._reset_button.setText(RESET_BUTTON_TEXT)
        self._reset_button.setMinimumHeight(self._reset_button.sizeHint().height())
        self._reset_button.clicked.connect(self.reset_signal)

        self._clear_button = QPushButton()
        self._clear_button.setText(CLEAR_BUTTON_TEXT)
        self._clear_button.setMinimumHeight(self._clear_button.sizeHint().height())
        self._clear_button.clicked.connect(self.clear_signal)

        # Register movement key overrides, tied to control panel visibility:
        config = KeyConfig()
        for control, up_key_code, down_key_code in ((self._x_pos_box, KeyConfig.MOVE_RIGHT, KeyConfig.MOVE_LEFT),
                                                    (self._y_pos_box, KeyConfig.MOVE_DOWN, KeyConfig.MOVE_UP),
                                                    (self._width_box, KeyConfig.PAN_RIGHT, KeyConfig.PAN_LEFT),
                                                    (self._height_box, KeyConfig.PAN_UP, KeyConfig.PAN_DOWN),
                                                    (self._rotate_box, KeyConfig.ROTATE_CW_KEY,
                                                     KeyConfig.ROTATE_CCW_KEY)):
            self._up_keys[control] = (config.get_keycodes(up_key_code), up_key_code)
            self._down_keys[control] = (config.get_keycodes(down_key_code), down_key_code)

            for key, sign in ((up_key_code, 1), (down_key_code, -1)):
                def _binding(mult, n=sign, box=control) -> bool:
                    steps = n * mult
                    if not self.isVisible() or image_stack.active_layer.locked:
                        return False
                    box.stepBy(steps)
                    return True

                HotkeyFilter.instance().register_speed_modified_keybinding(_binding, key)
        self.setContentsMargins(0, 0, 0, 0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        grid = self._layout
        grid.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        aspect_ratio_hint = KeyHintLabel(None, KeyConfig.FIXED_ASPECT_MODIFIER)

        def _get_down_hint(control_widget: QWidget) -> Optional[KeyHintLabel]:
            if control_widget == self._aspect_ratio_checkbox:
                return aspect_ratio_hint
            if control_widget in self._down_keys:
                down_keycode, down_config_key = self._down_keys[control_widget]
                down_hint_widget = KeyHintLabel(down_keycode, down_config_key)
                down_hint_widget.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                return down_hint_widget
            return None

        def _get_up_hint(control_widget: QWidget) -> Optional[KeyHintLabel]:
            if control_widget in self._up_keys:
                up_keycode, up_config_key = self._up_keys[control_widget]
                up_hint_widget = KeyHintLabel(up_keycode, up_config_key)
                up_hint_widget.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                return up_hint_widget
            return None

        down_control_hints = [_get_down_hint(control) for control in controls]
        up_control_hints = [_get_up_hint(control) for control in controls]
        item_map = {}
        for i, label in enumerate(labels):
            item_map[label] = (controls[i], down_control_hints[i], up_control_hints[i])
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
                grid.takeAt(0)
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
            control_widget, up_key_hint, down_key_hint = item_map[label_text]
            control_widget.setMinimumHeight(control.sizeHint().height())
            if use_hints is False:
                up_key_hint = None
                down_key_hint = None
            grid_column = column * 4
            if not isinstance(control_widget, (QPushButton, QCheckBox)):
                ctrl_label = QLabel(label_text)
                ctrl_label.setMinimumHeight(control_widget.sizeHint().height())
                grid.addWidget(ctrl_label, row, grid_column, 1, 2 if up_key_hint is None else 1)
            if up_key_hint is not None:
                grid.addWidget(up_key_hint, row, grid_column + 1)
                up_key_hint.show()
            grid.addWidget(control_widget, row, grid_column + 2)
            control_widget.show()
            if down_key_hint is not None:
                grid.addWidget(down_key_hint, row, grid_column + 3)
                down_key_hint.show()

        self.setMinimumWidth(column_width - 10)
        self.setMinimumHeight(row_height * 3)
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
        self.add_layout_mode('wide layout', _build_wide_layout, wide_layout_size, wide_layout_max)

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
        self.add_layout_mode('extra wide layout', _build_extra_wide_layout,
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
        self.add_layout_mode('tall layout', _build_tall_layout, tall_layout_size,
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
        self.add_layout_mode('extra tall layout', _build_extra_tall_layout, extra_tall_layout_size,
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
        self.add_default_layout_mode(_build_reduced_layout)

    @property
    def x_position(self) -> float:
        """Accesses the layer's transformed x-position value."""
        return self._x_pos_box.value()

    @x_position.setter
    def x_position(self, x: float) -> None:
        # noinspection PyUnusedLocal
        signal_blocker = QSignalBlocker(self._x_pos_box)
        self._x_pos_box.setValue(x)

    @property
    def y_position(self) -> float:
        """Accesses the layer's transformed y-position value."""
        return self._y_pos_box.value()

    @y_position.setter
    def y_position(self, y: float) -> None:
        # noinspection PyUnusedLocal
        signal_blocker = QSignalBlocker(self._y_pos_box)
        self._y_pos_box.setValue(y)

    @property
    def layer_width(self) -> float:
        """Accesses the layer's transformed width value."""
        return self._width_box.value()

    @layer_width.setter
    def layer_width(self, width: float) -> None:
        # noinspection PyUnusedLocal
        signal_blocker = QSignalBlocker(self._width_box)
        self._width_box.setValue(width)

    @property
    def layer_height(self) -> float:
        """Accesses the layer's transformed width value."""
        return self._width_box.value()

    @layer_height.setter
    def layer_height(self, width: float) -> None:
        # noinspection PyUnusedLocal
        signal_blocker = QSignalBlocker(self._height_box)
        self._height_box.setValue(width)

    @property
    def x_scale(self) -> float:
        """Accesses the layer's transformed x-scale value."""
        return self._x_scale_box.value()

    @x_scale.setter
    def x_scale(self, x: float) -> None:
        # noinspection PyUnusedLocal
        signal_blocker = QSignalBlocker(self._x_scale_box)
        self._x_scale_box.setValue(x)

    @property
    def y_scale(self) -> float:
        """Accesses the layer's transformed y-position value."""
        return self._y_scale_box.value()

    @y_scale.setter
    def y_scale(self, y: float) -> None:
        # noinspection PyUnusedLocal
        signal_blocker = QSignalBlocker(self._y_scale_box)
        self._y_scale_box.setValue(y)

    @property
    def rotation(self) -> float:
        """Accesses the layer's transformation angle"""
        return self._rotate_box.value()

    @rotation.setter
    def rotation(self, rotation: float) -> None:
        """Accesses the layer's transformation angle"""
        # noinspection PyUnusedLocal
        signal_blocker = QSignalBlocker(self._y_scale_box)
        self._rotate_box.setValue(rotation)

    @property
    def preserve_aspect_ratio(self) -> bool:
        """Accesses whether aspect ratio is fixed"""
        return self._aspect_ratio_checkbox.isChecked()

    @preserve_aspect_ratio.setter
    def preserve_aspect_ratio(self, preserve_ratio: bool) -> None:
        # noinspection PyUnusedLocal
        signal_blocker = QSignalBlocker(self._aspect_ratio_checkbox)
        self._aspect_ratio_checkbox.setChecked(preserve_ratio)

    def set_preview_bounds(self, bounds: QRect) -> None:
        """Update the preview widget bounds"""
        self._preview.set_layer_bounds(bounds)

    def set_preview_transform(self, transform: QTransform) -> None:
        """Update the preview widget transformation"""
        self._preview.set_transform(transform)


class _TransformPreview(QWidget):

    def __init__(self, image_size: QSize, layer_bounds: QRectF, layer_transform: QTransform) -> None:
        super().__init__()
        self._image_size = image_size
        self._layer_bounds = layer_bounds
        self._layer_transform = layer_transform
        self._brush = Qt.GlobalColor.white
        self._pen = QPen(Qt.GlobalColor.black, 3)
        self._pen.setCosmetic(True)
        self._background = get_transparency_tile_pixmap(image_size)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)

    def sizeHint(self) -> QSize:
        """Preview size is capped at 200x200."""
        return QSize(200, 200)

    def minimumSizeHint(self) -> QSize:
        """Preview size is capped at 200x200."""
        return self.sizeHint()

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
        final_image_poly = self._layer_transform.map(QPolygonF(self._layer_bounds))
        full_bounds = image_bounds.united(final_image_poly.boundingRect().toRect())
        scaled_full_bounds = get_scaled_placement(self.size(), full_bounds.size(), 4)
        initial_transform = get_rect_transformation(full_bounds, scaled_full_bounds)
        image_bounds_color = QColor(Qt.GlobalColor.black)
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
