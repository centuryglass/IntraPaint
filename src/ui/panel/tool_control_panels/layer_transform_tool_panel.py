"""Control panel for the layer transformation tool."""
from typing import Optional

from PySide6.QtCore import QRect, QPoint, QSize, QRectF, Signal
from PySide6.QtGui import QPaintEvent, QTransform, QColor, Qt, QPolygonF, QPainter, QPen, QKeySequence
from PySide6.QtWidgets import QSizePolicy, QApplication, QGridLayout, QWidget, QPushButton

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.layers.image_stack import ImageStack
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox, FloatSliderSpinbox
from src.ui.layout.reactive_layout_widget import ReactiveLayoutWidget
from src.ui.widget.key_hint_label import KeyHintLabel
from src.util.layout import clear_layout, wrap_widget_with_key_hints
from src.util.shared_constants import FLOAT_MIN, FLOAT_MAX, MIN_NONZERO, ASPECT_RATIO_CHECK_LABEL, INT_MAX
from src.util.signals_blocked import signals_blocked
from src.util.visual.geometry_utils import get_rect_transformation, get_scaled_placement
from src.util.visual.image_utils import get_transparency_tile_pixmap

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

        def _key_predicate() -> bool:
            return (self.isVisible() and self.isEnabled() and not image_stack.active_layer.locked
                    and not image_stack.active_layer.parent_locked)

        def _init_control(default_val: float | int, min_val: float | int, max_val: float | int, signal: Signal,
                          text: str, down_key: Optional[str] = None, up_key: Optional[str] = None):
            new_control = IntSliderSpinbox(parent=self) if isinstance(default_val, int) else FloatSliderSpinbox()
            new_control.set_slider_included(False)
            new_control.setRange(min_val, max_val)
            new_control.setValue(default_val)
            new_control.setText(text)
            if down_key is not None and up_key is not None:
                HotkeyFilter.instance().bind_slider_controls(new_control, down_key, up_key, _key_predicate)
            new_control.valueChanged.connect(signal)
            return new_control

        self._x_pos_box = _init_control(0.0, FLOAT_MIN, FLOAT_MAX, self.x_changed, X_LABEL,
                                        KeyConfig.MOVE_LEFT, KeyConfig.MOVE_RIGHT)
        self._y_pos_box = _init_control(0.0, FLOAT_MIN, FLOAT_MAX, self.y_changed, Y_LABEL,
                                        KeyConfig.MOVE_UP, KeyConfig.MOVE_DOWN)
        edit_size = Cache().get(Cache.EDIT_SIZE)
        self._width_box = _init_control(float(edit_size.width()), MIN_NONZERO, FLOAT_MAX, self.width_changed,
                                        WIDTH_LABEL, KeyConfig.PAN_LEFT, KeyConfig.PAN_RIGHT)
        self._height_box = _init_control(float(edit_size.height()), MIN_NONZERO, FLOAT_MAX, self.height_changed,
                                         HEIGHT_LABEL, KeyConfig.PAN_DOWN, KeyConfig.PAN_UP)

        self._x_scale_box = _init_control(1.0, FLOAT_MIN, FLOAT_MAX, self.x_scale_changed, X_SCALE_LABEL)
        self._y_scale_box = _init_control(1.0, FLOAT_MIN, FLOAT_MAX, self.y_scale_changed, Y_SCALE_LABEL)

        for scale_box in (self._y_scale_box, self._x_scale_box):
            scale_box.setSingleStep(SCALE_STEP)
        self._rotate_box = _init_control(0.0, FLOAT_MIN, FLOAT_MAX, self.angle_changed, DEGREE_LABEL,
                                         KeyConfig.ROTATE_CCW_KEY, KeyConfig.ROTATE_CW_KEY)
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

        self._down_keys: dict[QWidget, tuple[QKeySequence, str]] = {}
        self._up_keys: dict[QWidget, tuple[QKeySequence, str]] = {}

        self._reset_button = QPushButton()
        self._reset_button.setText(RESET_BUTTON_TEXT)
        self._reset_button.setMinimumHeight(self._reset_button.sizeHint().height())
        self._reset_button.clicked.connect(self.reset_signal)

        self._clear_button = QPushButton()
        self._clear_button.setText(CLEAR_BUTTON_TEXT)
        self._clear_button.setMinimumHeight(self._clear_button.sizeHint().height())
        self._clear_button.clicked.connect(self.clear_signal)

        self.setContentsMargins(0, 0, 0, 0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        grid = self._layout
        grid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.setSpacing(CONTROL_GRID_SPACING)

        self._aspect_ratio_hint = KeyHintLabel(None, KeyConfig.FIXED_ASPECT_MODIFIER, parent=self)
        self._aspect_ratio_wrapper = wrap_widget_with_key_hints(self._aspect_ratio_checkbox,
                                                                right_hint=self._aspect_ratio_hint,
                                                                alignment=Qt.AlignmentFlag.AlignLeft)

        controls = [self._x_pos_box, self._y_pos_box, self._width_box, self._height_box, self._x_scale_box,
                    self._y_scale_box, self._rotate_box, self._aspect_ratio_wrapper, self._clear_button,
                    self._reset_button]

        control_width = 0
        control_height = 0
        for control in controls:
            min_size = control.minimumSizeHint()
            control_width = max(min_size.width(), control_width)
            control_height = max(min_size.height(), control_height)
        preview_size = self._preview.sizeHint()

        # Layout setup functions:
        def _clear_grid() -> None:
            clear_layout(grid, unparent=False, hide=True)
            for row_num in range(grid.rowCount()):
                grid.setRowStretch(row_num, 0)
            for col_num in range(grid.columnCount()):
                grid.setColumnStretch(col_num, 0)

        def _get_grid_item(row: int, column: int) -> tuple[QWidget | None, int, int]:
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

        def _final_grid_adjustments(hide_key_hints=False) -> None:
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
            spinbox_map: dict[int, list[IntSliderSpinbox | FloatSliderSpinbox]] = {}
            for control_widget in controls:
                control_idx = grid.indexOf(control_widget)
                if control_idx < 0:
                    continue
                control_widget.show()
                if isinstance(control_widget, (IntSliderSpinbox, FloatSliderSpinbox)):
                    control_widget.set_key_hints_visible(not hide_key_hints)
                    _, column, _, _ = grid.getItemPosition(control_idx)
                    if column not in spinbox_map:
                        spinbox_map[column] = []
                    spinbox_map[column].append(control_widget)
            for spinbox_column in spinbox_map.values():
                IntSliderSpinbox.align_slider_spinboxes(spinbox_column)
            self._aspect_ratio_hint.setVisible(not hide_key_hints)
            if grid.indexOf(self._preview) >= 0:
                self._preview.show()

        self.setMinimumWidth(control_width - 10)
        self.setMinimumHeight(control_height * 3)
        wide_layout_size = QSize(control_width * 3, control_height * 3)
        extra_wide_layout_size = QSize(wide_layout_size.width() + preview_size.width(),
                                       max(wide_layout_size.height(), preview_size.height()))

        tall_layout_size = QSize(control_width, control_height * len(controls))
        extra_tall_layout_size = QSize(tall_layout_size.width(), tall_layout_size.height() + preview_size.height())

        # Wide layout: 3x3 control grid
        wide_layout: tuple[tuple[QWidget, int, int], ...] = (
            (self._x_pos_box, 1, 0),
            (self._y_pos_box, 1, 1),
            (self._rotate_box, 1, 2),
            (self._width_box, 2, 0),
            (self._height_box, 2, 1),
            (self._aspect_ratio_wrapper, 2, 2),
            (self._x_scale_box, 3, 0),
            (self._y_scale_box, 3, 1),
            (self._clear_button, 3, 2),
            (self._reset_button, 3, 8)
        )
        wide_layout_row_stretch = {0: 50, 4: 100}

        def _build_wide_layout() -> None:
            _clear_grid()
            for widget, row, column in wide_layout:
                grid.addWidget(widget, row, column)
            for row, row_stretch in wide_layout_row_stretch.items():
                grid.setRowStretch(row, row_stretch)
            _final_grid_adjustments()

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
        tall_layout: tuple[tuple[QWidget, int, int, int], ...] = (
            (self._x_pos_box, 0, 0, 2),
            (self._y_pos_box, 1, 0, 2),
            (self._width_box, 2, 0, 2),
            (self._height_box, 3, 0, 2),
            (self._x_scale_box, 4, 0, 2),
            (self._y_scale_box, 5, 0, 2),
            (self._rotate_box, 6, 0, 2),
            (self._aspect_ratio_wrapper, 7, 0, 2),
            (self._reset_button, 8, 0, 1),
            (self._clear_button, 8, 1, 1)
        )

        def _build_tall_layout() -> None:
            _clear_grid()
            for widget, row, col, col_stretch in tall_layout:
                grid.addWidget(widget, row, col, 1, col_stretch)
            _final_grid_adjustments()

        self.add_layout_mode('tall layout', _build_tall_layout, tall_layout_size,
                             QSize(wide_layout_size.width() - 1, extra_tall_layout_size.height() - 1))

        # Extra tall layout: add preview
        extra_tall_row_stretch = {0: 30, 1: 30, 2: 100, 13: 30}

        def _build_extra_tall_layout() -> None:
            _clear_grid()
            for row, row_stretch in extra_tall_row_stretch.items():
                grid.setRowStretch(row, row_stretch)
            grid.addWidget(self._preview, 1, 1, 1, 4)
            for widget, row, col, col_stretch in tall_layout:
                grid.addWidget(widget, row + 3, col, 1, col_stretch)
            _final_grid_adjustments()

        self.add_layout_mode('extra tall layout', _build_extra_tall_layout, extra_tall_layout_size,
                             QSize(wide_layout_size.width() - 1, INT_MAX))

        # Reduced layout: leave out width, height, control hints
        self._reduced_layout: tuple[tuple[QWidget, int, int, int], ...] = (
            (self._x_pos_box, 0, 0, 2),
            (self._y_pos_box, 1, 0, 2),
            (self._width_box, 2, 0, 2),
            (self._height_box, 3, 0, 2),
            (self._rotate_box, 4, 0, 2),
            (self._aspect_ratio_wrapper, 5, 0, 2),
            (self._reset_button, 6, 0, 1),
            (self._clear_button, 6, 1, 1)
        )

        def _build_reduced_layout() -> None:
            _clear_grid()
            for widget, row, col, col_stretch in self._reduced_layout:
                grid.addWidget(widget, row, col, 1, col_stretch)
            _final_grid_adjustments(True)

        self.add_default_layout_mode(_build_reduced_layout)

    @property
    def x_position(self) -> float:
        """Accesses the layer's transformed x-position value."""
        return self._x_pos_box.value()

    @x_position.setter
    def x_position(self, x: float) -> None:
        with signals_blocked(self._x_pos_box):
            self._x_pos_box.setValue(x)

    @property
    def y_position(self) -> float:
        """Accesses the layer's transformed y-position value."""
        return self._y_pos_box.value()

    @y_position.setter
    def y_position(self, y: float) -> None:
        with signals_blocked(self._y_pos_box):
            self._y_pos_box.setValue(y)

    @property
    def layer_width(self) -> float:
        """Accesses the layer's transformed width value."""
        return self._width_box.value()

    @layer_width.setter
    def layer_width(self, width: float) -> None:
        with signals_blocked(self._width_box):
            self._width_box.setValue(width)

    @property
    def layer_height(self) -> float:
        """Accesses the layer's transformed width value."""
        return self._width_box.value()

    @layer_height.setter
    def layer_height(self, width: float) -> None:
        with signals_blocked(self._height_box):
            self._height_box.setValue(width)

    @property
    def x_scale(self) -> float:
        """Accesses the layer's transformed x-scale value."""
        return self._x_scale_box.value()

    @x_scale.setter
    def x_scale(self, x: float) -> None:
        with signals_blocked(self._x_scale_box):
            self._x_scale_box.setValue(x)

    @property
    def y_scale(self) -> float:
        """Accesses the layer's transformed y-position value."""
        return self._y_scale_box.value()

    @y_scale.setter
    def y_scale(self, y: float) -> None:
        with signals_blocked(self._y_scale_box):
            self._y_scale_box.setValue(y)

    @property
    def rotation(self) -> float:
        """Accesses the layer's transformation angle"""
        return self._rotate_box.value()

    @rotation.setter
    def rotation(self, rotation: float) -> None:
        """Accesses the layer's transformation angle"""
        with signals_blocked(self._rotate_box):
            self._rotate_box.setValue(rotation)

    @property
    def preserve_aspect_ratio(self) -> bool:
        """Accesses whether aspect ratio is fixed"""
        return self._aspect_ratio_checkbox.isChecked()

    @preserve_aspect_ratio.setter
    def preserve_aspect_ratio(self, preserve_ratio: bool) -> None:
        with signals_blocked(self._aspect_ratio_checkbox):
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
