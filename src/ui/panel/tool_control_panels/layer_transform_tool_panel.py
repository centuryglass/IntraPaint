"""Layer transform tool control panel: the shared `GeometryBlock` with its Scale and Angle rows, Revert and Clear
transform, and a preview of the layer over the image.

The panel is a view over the transform tool's outline. It emits a signal per field the user changes, and the tool sets
the fields back with the panel's properties, which emit nothing.

- The geometry block shows at every size. Its ratio lock is "Keep aspect ratio", and links W:H and Scale X:Scale Y.
  Holding the fixed-aspect modifier locks it temporarily without changing the stored setting.
  `preserve_aspect_ratio_changed` carries whether either one locks the ratio, which the tool's outline also follows.
- Revert restores the transform the layer had when the tool selected it. Clear transform removes the transform, in
  the danger weight and apart from Revert.
- The preview shows the layer over the image bounds, with a legend. It is decorative: it hides where it doesn't fit,
  and takes spare space up to `PREVIEW_MAX_SIZE`.

The panel is a `src.ui.layout.panel_fit.FitContent`, planned in the space the Tools panel gives it:
- Side: one column, with the buttons under the fields and the preview under them.
- Strip: a geometry column, then the preview. The buttons go under the fields when the strip's height holds both, and
  in a column of their own beside them otherwise. A short strip puts the block's position and size rows on one line.
"""
from typing import Optional

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPalette, QPen, QPixmap, QPolygonF, QTransform
from PySide6.QtWidgets import (QApplication, QBoxLayout, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.layers.image_stack import ImageStack
from src.ui.button_weight import ButtonWeight, set_button_weight
from src.ui.input_fields.geometry_block import (ANGLE, HEIGHT, SCALE_X, SCALE_Y, WIDTH, X, Y, GeometryBlock,
                                                bind_step_keys)
from src.ui.layout.panel_fit import REQUIRED, FitItem, FitPlanner, Orientation, Placement
from src.ui.panel.tool_control_panels.fit_tool_panel import FitToolPanel
from src.util.visual.geometry_utils import get_rect_transformation, get_scaled_placement
from src.util.visual.image_utils import get_transparency_tile_pixmap

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panels.layer_transform_tool_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


REVERT_BUTTON_TEXT = _tr('Revert')
REVERT_BUTTON_TOOLTIP = _tr('Restore the transform this layer had when you selected it')
CLEAR_BUTTON_TEXT = _tr('Clear transform')
CLEAR_BUTTON_TOOLTIP = _tr('Remove all movement, scaling and rotation from this layer')
LEGEND_IMAGE = _tr('Image')
LEGEND_LAYER = _tr('Layer')

SECTION_SPACING = 10
PREVIEW_MIN_SIZE = QSize(120, 90)
PREVIEW_MAX_SIZE = QSize(300, 300)
PREVIEW_MARGIN = 4
LEGEND_SWATCH_SIZE = 10
IMAGE_BOUNDS_ALPHA = 0.3
LAYER_OUTLINE_WIDTH = 3

# The planned items, in placement order:
GEOMETRY_ITEM = FitItem(REQUIRED, 2)
ACTIONS_ITEM = FitItem(REQUIRED, 2)
PREVIEW_ITEM = FitItem(1)
# Forms of the geometry item:
STACKED = 0
HORIZONTAL = 1
# Forms of the actions item:
UNDER = 0
BESIDE = 1


def _image_bounds_color() -> QColor:
    color = QColor(Qt.GlobalColor.black)
    color.setAlphaF(IMAGE_BOUNDS_ALPHA)
    return color


class LayerTransformToolPanel(FitToolPanel):
    """Layer transform tool control panel.

    Without a host that calls `set_fit_space`, the panel plans for its own size when resized.
    """

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

    def __init__(self, image_stack: ImageStack, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._geometry = GeometryBlock(show_scale=True, show_angle=True, integer=False, parent=self)
        self._geometry.set_image_size(image_stack.size)
        image_stack.size_changed.connect(self._geometry.set_image_size)
        field_signals = {X: self.x_changed, Y: self.y_changed, WIDTH: self.width_changed,
                         HEIGHT: self.height_changed, SCALE_X: self.x_scale_changed, SCALE_Y: self.y_scale_changed,
                         ANGLE: self.angle_changed}
        self._geometry.valueChanged.connect(lambda name, value: field_signals[name].emit(float(value)))

        def _key_predicate() -> bool:
            active_layer = image_stack.active_layer
            return (self.isVisible() and self.isEnabled() and active_layer is not None and not active_layer.locked
                    and not active_layer.parent_locked)

        bind_step_keys(self._geometry, HotkeyFilter.instance(), KeyConfig, _key_predicate)
        self._geometry.ratioLockToggled.connect(self._lock_changed)
        self._geometry.temporaryLockToggled.connect(self._lock_changed)

        self._revert_button = QPushButton(REVERT_BUTTON_TEXT, self)
        self._revert_button.setToolTip(REVERT_BUTTON_TOOLTIP)
        self._revert_button.clicked.connect(self.reset_signal)
        self._clear_button = QPushButton(CLEAR_BUTTON_TEXT, self)
        self._clear_button.setToolTip(CLEAR_BUTTON_TOOLTIP)
        set_button_weight(self._clear_button, ButtonWeight.DANGER)
        self._clear_button.clicked.connect(self.clear_signal)
        self._actions = QWidget(self)
        self._actions_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self._actions)
        self._actions_layout.setContentsMargins(0, 0, 0, 0)

        self._preview = _TransformPreview(image_stack.size, self)
        image_stack.size_changed.connect(self._preview.set_image_size)
        self._preview_box = QWidget(self)
        preview_layout = QVBoxLayout(self._preview_box)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.addWidget(self._preview, stretch=1)
        preview_layout.addLayout(self._build_legend())
        # Height past the preview's cap goes below the legend:
        preview_layout.addStretch(0)

        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(SECTION_SPACING)

        self._planner = FitPlanner([GEOMETRY_ITEM, ACTIONS_ITEM, PREVIEW_ITEM], self._apply_fit, self._measure_fit)
        self._apply_fit(Orientation.SIDE, (STACKED, UNDER, 0))

    def _build_legend(self) -> QHBoxLayout:
        """Returns a row naming the preview's image bounds and layer, each beside a swatch drawn as the preview draws
        it."""
        legend = QHBoxLayout()
        legend.setContentsMargins(0, 0, 0, 0)
        dim_palette = QPalette(self.palette())
        dim_palette.setColor(QPalette.ColorRole.WindowText, self.palette().color(QPalette.ColorRole.PlaceholderText))
        for text, fill, outline in ((LEGEND_IMAGE, _image_bounds_color(), None),
                                    (LEGEND_LAYER, QColor(Qt.GlobalColor.white), QColor(Qt.GlobalColor.black))):
            swatch = QPixmap(LEGEND_SWATCH_SIZE, LEGEND_SWATCH_SIZE)
            swatch.fill(Qt.GlobalColor.transparent)
            painter = QPainter(swatch)
            painter.fillRect(swatch.rect(), fill)
            if outline is not None:
                painter.setPen(QPen(outline, 1))
                painter.drawRect(swatch.rect().adjusted(0, 0, -1, -1))
            painter.end()
            swatch_label = QLabel(self)
            swatch_label.setPixmap(swatch)
            text_label = QLabel(text, self)
            text_label.setPalette(dim_palette)
            legend.addWidget(swatch_label)
            legend.addWidget(text_label)
        legend.addStretch(1)
        return legend

    # -----------------------------------------------------------------------------------------------------------------
    # Values
    # -----------------------------------------------------------------------------------------------------------------

    @property
    def geometry_block(self) -> GeometryBlock:
        """The position, size, scale and angle fields."""
        return self._geometry

    @property
    def revert_button(self) -> QPushButton:
        """The button that restores the layer's transform from when it was selected."""
        return self._revert_button

    @property
    def clear_button(self) -> QPushButton:
        """The button that removes the layer's transform."""
        return self._clear_button

    @property
    def preview(self) -> QWidget:
        """The preview with its legend."""
        return self._preview_box

    @property
    def x_position(self) -> float:
        """Accesses the layer's transformed x-position value."""
        return float(self._geometry.value(X))

    @x_position.setter
    def x_position(self, x: float) -> None:
        self._geometry.set_value(X, x)

    @property
    def y_position(self) -> float:
        """Accesses the layer's transformed y-position value."""
        return float(self._geometry.value(Y))

    @y_position.setter
    def y_position(self, y: float) -> None:
        self._geometry.set_value(Y, y)

    @property
    def layer_width(self) -> float:
        """Accesses the layer's transformed width value."""
        return float(self._geometry.value(WIDTH))

    @layer_width.setter
    def layer_width(self, width: float) -> None:
        self._geometry.set_value(WIDTH, width)

    @property
    def layer_height(self) -> float:
        """Accesses the layer's transformed height value."""
        return float(self._geometry.value(HEIGHT))

    @layer_height.setter
    def layer_height(self, height: float) -> None:
        self._geometry.set_value(HEIGHT, height)

    @property
    def x_scale(self) -> float:
        """Accesses the layer's transformed x-scale value."""
        return float(self._geometry.value(SCALE_X))

    @x_scale.setter
    def x_scale(self, x: float) -> None:
        self._geometry.set_value(SCALE_X, x)

    @property
    def y_scale(self) -> float:
        """Accesses the layer's transformed y-scale value."""
        return float(self._geometry.value(SCALE_Y))

    @y_scale.setter
    def y_scale(self, y: float) -> None:
        self._geometry.set_value(SCALE_Y, y)

    @property
    def rotation(self) -> float:
        """Accesses the layer's transformation angle."""
        return float(self._geometry.value(ANGLE))

    @rotation.setter
    def rotation(self, rotation: float) -> None:
        self._geometry.set_value(ANGLE, rotation)

    @property
    def preserve_aspect_ratio(self) -> bool:
        """Accesses the stored "Keep aspect ratio" setting, which the temporary lock doesn't change."""
        return self._geometry.ratio_locked()

    @preserve_aspect_ratio.setter
    def preserve_aspect_ratio(self, preserve_ratio: bool) -> None:
        self._geometry.blockSignals(True)
        try:
            self._geometry.set_ratio_locked(preserve_ratio)
        finally:
            self._geometry.blockSignals(False)

    def _lock_changed(self, _locked: bool) -> None:
        self.preserve_aspect_ratio_changed.emit(self._geometry.effective_ratio_locked())

    def set_preview_bounds(self, bounds: QRect) -> None:
        """Update the preview widget bounds"""
        self._preview.set_layer_bounds(QRectF(bounds))

    def set_preview_transform(self, transform: QTransform) -> None:
        """Update the preview widget transformation"""
        self._preview.set_transform(transform)

    # -----------------------------------------------------------------------------------------------------------------
    # Layout
    # -----------------------------------------------------------------------------------------------------------------

    def _apply_fit(self, orientation: Orientation, placement: Placement) -> None:
        geometry_form, actions_form, preview_form = placement
        self._orientation = orientation
        strip = orientation == Orientation.STRIP
        beside = strip and actions_form == BESIDE
        preview = preview_form is not None
        self._geometry.set_horizontal(strip and geometry_form == HORIZONTAL)
        self._arrange_actions(beside)
        grid = self._grid
        self._clear(grid, (self._geometry, self._actions, self._preview_box))
        top = Qt.AlignmentFlag.AlignTop
        grid.addWidget(self._geometry, 0, 0, top)
        if strip:
            if beside:
                grid.addWidget(self._actions, 0, 1, 2, 1)
            else:
                grid.addWidget(self._actions, 1, 0, top)
            used_columns = 2 if beside else 1
            if preview:
                grid.addWidget(self._preview_box, 0, used_columns, 2, 1)
                used_columns += 1
            grid.setRowStretch(1, 1)
        else:
            grid.addWidget(self._actions, 1, 0, top)
            if preview:
                grid.addWidget(self._preview_box, 2, 0)
            grid.setRowStretch(2 if preview else 3, 1)
            used_columns = 1
        # Spare width goes to the fields and the preview, up to their caps, and not to a column of buttons:
        for column in range(used_columns):
            grid.setColumnStretch(column, 0 if beside and column == 1 else 1)
        grid.setColumnStretch(used_columns, 0)
        self._preview_box.setVisible(preview)
        self._cap_width(self._geometry)
        if beside:
            self._actions.setMaximumWidth(self._actions.sizeHint().width())
        else:
            self._cap_width(self._actions)

    def _arrange_actions(self, column: bool) -> None:
        """Puts Revert and Clear transform in a row, or a column, with spare room between them."""
        layout = self._actions_layout
        while layout.count() > 0:
            layout.takeAt(0)
        layout.setDirection(QBoxLayout.Direction.TopToBottom if column else QBoxLayout.Direction.LeftToRight)
        layout.addWidget(self._revert_button)
        layout.addStretch(1)
        layout.addWidget(self._clear_button)
        self._actions.setSizePolicy(QSizePolicy.Policy.Preferred,
                                    QSizePolicy.Policy.Expanding if column else QSizePolicy.Policy.Fixed)


class _TransformPreview(QWidget):
    """Draws the layer's transformed bounds over the image bounds, scaled to fit."""

    def __init__(self, image_size: QSize, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._image_size = image_size
        self._layer_bounds = QRectF()
        self._layer_transform = QTransform()
        self._brush = QColor(Qt.GlobalColor.white)
        self._pen = QPen(Qt.GlobalColor.black, LAYER_OUTLINE_WIDTH)
        self._pen.setCosmetic(True)
        self._background = get_transparency_tile_pixmap(image_size)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMaximumSize(PREVIEW_MAX_SIZE)

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the smallest size the preview is drawn at."""
        return PREVIEW_MIN_SIZE

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the smallest size the preview is drawn at."""
        return PREVIEW_MIN_SIZE

    def set_image_size(self, new_size: QSize) -> None:
        """Update the previewed size of the edited image."""
        self._image_size = new_size
        self.update()

    def set_layer_bounds(self, new_bounds: QRectF) -> None:
        """Update the previewed layer bounds."""
        self._layer_bounds = new_bounds
        self.update()

    def set_transform(self, new_transform: QTransform) -> None:
        """Update the previewed layer transformation."""
        self._layer_transform = new_transform
        self.update()

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draw the transformed layer over the image bounds."""
        painter = QPainter(self)
        painter.drawTiledPixmap(QRect(QPoint(), self.size()), self._background)
        image_bounds = QRect(QPoint(), self._image_size)
        final_image_poly = self._layer_transform.map(QPolygonF(self._layer_bounds))
        assert isinstance(final_image_poly, QPolygonF)
        full_bounds = image_bounds.united(final_image_poly.boundingRect().toRect())
        scaled_full_bounds = get_scaled_placement(self.size(), full_bounds.size(), PREVIEW_MARGIN)
        initial_transform = get_rect_transformation(full_bounds, scaled_full_bounds)
        painter.setTransform(initial_transform)
        painter.fillRect(image_bounds, _image_bounds_color())
        if not self._layer_bounds.isNull():
            painter.setTransform(self._layer_transform, True)
            painter.setPen(self._pen)
            painter.setBrush(self._brush)
            painter.fillRect(self._layer_bounds, self._brush)
            painter.drawRect(self._layer_bounds)
        painter.end()
