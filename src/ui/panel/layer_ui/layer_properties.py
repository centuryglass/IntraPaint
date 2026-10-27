"""The selected-layer header: one block above the layer list that edits the active layer.

It shows the layer's thumbnail and name with its lock, alpha lock and isolate toggles, then its blend mode and opacity.
A stripe on its left edge matches the active row's stripe, which ties the controls to that row. The block sits above
the list, outside any row, so rows keep one height and the list never shifts when the selection changes.

- `set_layer` points every control at a new layer. The header holds one layer; a multi-layer selection would pass
  its bulk state through the same controls.
- While the layer or a group above it is locked, a `DisabledBanner` names the locked layer and offers to unlock it,
  and the controls that would change the layer are disabled. The lock toggle stays enabled.
- The root group has no lock, alpha lock or isolate toggle. Its mode and opacity are editable like any group's, since
  both render and both are saved.
- Opacity changes are one undo step per drag. While the blend mode popup is open, the highlighted mode previews on the
  layer without an undo step, and closing the popup restores the layer's mode before any choice applies.
- Mode and opacity have two forms: one row, or stacked on two rows (`set_stacked`). Toggles show text labels in the
  large form (`set_labeled`).
"""
from typing import Optional

from PySide6.QtCore import QRect
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QApplication, QGridLayout, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from src.image.composite_mode import CompositeMode
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.ui.input_fields.slider_field import SliderField
from src.ui.panel.layer_ui.blend_mode_combo_box import BlendModeComboBox
from src.ui.panel.layer_ui.layer_flags import LAYER_FLAGS, LayerFlagButton
from src.ui.panel.layer_ui.layer_row import (ROW_SPACING, SELECTION_STRIPE_WIDTH, SMALL_THUMBNAIL_SIZE, LayerThumbnail,
                                             selection_stripe_color)
from src.ui.widget.disabled_banner import DisabledBanner
from src.ui.widget.elided_label import ElidedLabel
from src.undo_stack import UndoStack

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.panel.layer_ui.layer_properties'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


OPACITY_LABEL = _tr('Opacity')
OPACITY_TOOLTIP = _tr('Layer opacity')
LAYER_LOCKED_MESSAGE = _tr('"{layer_name}" is locked')
UNLOCK_BUTTON_TEXT = _tr('Unlock')

OPACITY_UNDO_GESTURE = 'LayerProperties.opacity'
BLOCK_MARGIN = 4


def locking_layer(layer: Layer) -> Optional[Layer]:
    """Returns the layer whose lock keeps a layer from changing: the layer itself, or the nearest locked group above
    it, or None if nothing locks it."""
    candidate: Optional[Layer] = layer
    while candidate is not None:
        if candidate.locked:
            return candidate
        parent = candidate.layer_parent
        candidate = parent if isinstance(parent, Layer) else None
    return None


class LayerProperties(QWidget):
    """Edits the active layer: its flags, blend mode and opacity. See the module docstring."""

    def __init__(self, image_stack: ImageStack, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._image_stack = image_stack
        self._layer: Optional[Layer] = None
        # The layer's own mode while the blend mode popup previews another:
        self._preview_original: Optional[CompositeMode] = None
        self._stacked = False
        self._labeled = False
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SELECTION_STRIPE_WIDTH + BLOCK_MARGIN, BLOCK_MARGIN, 0, BLOCK_MARGIN)
        layout.setSpacing(BLOCK_MARGIN)

        # The rows are widgets, not nested layouts, so planning's fresh measurements reach their layouts:
        name_row_widget = QWidget()
        name_row = QHBoxLayout(name_row_widget)
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(ROW_SPACING)
        self._thumbnail = LayerThumbnail(None, SMALL_THUMBNAIL_SIZE)
        self._name = ElidedLabel()
        name_row.addWidget(self._thumbnail)
        name_row.addWidget(self._name, stretch=1)
        self._flag_buttons = [LayerFlagButton(flag) for flag in LAYER_FLAGS]
        for button in self._flag_buttons:
            name_row.addWidget(button)
        layout.addWidget(name_row_widget)

        self._banner = DisabledBanner('', UNLOCK_BUTTON_TEXT)
        self._banner.fix_requested.connect(self._unlock_slot)
        self._banner.hide()
        layout.addWidget(self._banner)

        self._mode_box = BlendModeComboBox()
        self._mode_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._mode_box.setMinimumContentsLength(1)
        self._mode_box.currentIndexChanged.connect(self._mode_change_slot)
        self._mode_box.preview_requested.connect(self._preview_mode_slot)
        self._mode_box.preview_ended.connect(self._end_preview_slot)
        self._opacity = SliderField(OPACITY_LABEL, 100, 0, 100, suffix='%')
        self._opacity.setToolTip(OPACITY_TOOLTIP)
        self._opacity.valueChanged.connect(self._opacity_change_slot)
        self._opacity.dragStarted.connect(self._opacity_drag_started_slot)
        self._opacity.dragFinished.connect(self._opacity_drag_finished_slot)
        controls_widget = QWidget()
        self._controls = QGridLayout(controls_widget)
        self._controls.setContentsMargins(0, 0, 0, 0)
        self._controls.setSpacing(ROW_SPACING)
        layout.addWidget(controls_widget)
        self.set_stacked(False)
        image_stack.active_layer_changed.connect(self.set_layer)
        self.set_layer(image_stack.active_layer)

    @property
    def layer(self) -> Optional[Layer]:
        """The layer the header edits."""
        return self._layer

    @property
    def thumbnail(self) -> LayerThumbnail:
        """The layer's preview."""
        return self._thumbnail

    @property
    def name_text(self) -> str:
        """The layer's name, before ellipsizing."""
        return self._name.full_text

    @property
    def flag_buttons(self) -> list[LayerFlagButton]:
        """The lock, alpha lock and isolate toggles, including ones hidden because the layer lacks that flag."""
        return list(self._flag_buttons)

    @property
    def banner(self) -> DisabledBanner:
        """The banner shown while the layer is locked."""
        return self._banner

    @property
    def mode_box(self) -> BlendModeComboBox:
        """The blend mode control."""
        return self._mode_box

    @property
    def opacity_field(self) -> SliderField:
        """The opacity control, in percent."""
        return self._opacity

    def set_stacked(self, stacked: bool) -> None:
        """Puts mode and opacity on one row, or on two."""
        self._stacked = stacked
        self._controls.removeWidget(self._mode_box)
        self._controls.removeWidget(self._opacity)
        self._controls.addWidget(self._mode_box, 0, 0)
        self._controls.addWidget(self._opacity, 1 if stacked else 0, 0 if stacked else 1)
        self._controls.setColumnStretch(0, 1)
        self._controls.setColumnStretch(1, 0 if stacked else 1)

    def set_labeled(self, labeled: bool) -> None:
        """Shows text labels on the toggles, or icons alone. Labeled toggles also keep room for the whole name, so they
        only fit where the name needn't shorten for them."""
        self._labeled = labeled
        for button in self._flag_buttons:
            button.set_labeled(labeled)
        self._update_name_minimum()

    def _update_name_minimum(self) -> None:
        self._name.setMinimumWidth(self._name.full_text_width() if self._labeled else 1)

    def set_layer(self, layer: Optional[Layer]) -> None:
        """Points every control at a new layer."""
        if layer is self._layer:
            return
        self._end_preview_slot()
        if self._layer is not None:
            self._layer.name_changed.disconnect(self._name_change_slot)
            self._layer.lock_changed.disconnect(self._lock_change_slot)
            self._layer.opacity_changed.disconnect(self._layer_opacity_change_slot)
            self._layer.composition_mode_changed.disconnect(self._layer_mode_change_slot)
        self._layer = layer
        self._thumbnail.set_layer(layer)
        for button in self._flag_buttons:
            button.set_layer(layer)
        if layer is not None:
            layer.name_changed.connect(self._name_change_slot)
            layer.lock_changed.connect(self._lock_change_slot)
            layer.opacity_changed.connect(self._layer_opacity_change_slot)
            layer.composition_mode_changed.connect(self._layer_mode_change_slot)
            self._name.set_full_text(layer.name)
            self._update_name_minimum()
            self._show_opacity(layer.opacity)
            self._mode_box.set_mode(layer.composition_mode)
        self._lock_change_slot()

    def _name_change_slot(self, _layer: Layer, name: str) -> None:
        self._name.set_full_text(name)
        self._update_name_minimum()

    def _lock_change_slot(self, *_args) -> None:
        # The signal's arguments may describe a parent group's lock, so read the lock state from the layer instead.
        layer = self._layer
        locker = locking_layer(layer) if layer is not None else None
        editable = layer is not None and locker is None
        self._mode_box.setEnabled(editable)
        self._opacity.setEnabled(editable)
        self._banner.setVisible(locker is not None)
        if locker is not None:
            self._banner.set_message(LAYER_LOCKED_MESSAGE.format(layer_name=locker.name))

    def _unlock_slot(self) -> None:
        if self._layer is not None:
            locker = locking_layer(self._layer)
            if locker is not None:
                locker.locked = False

    # Opacity:

    def _show_opacity(self, opacity: float) -> None:
        percent = round(opacity * 100)
        if self._opacity.value() != percent:
            self._opacity.valueChanged.disconnect(self._opacity_change_slot)
            self._opacity.set_value(percent)
            self._opacity.valueChanged.connect(self._opacity_change_slot)

    def _opacity_change_slot(self, percent: int | float) -> None:
        layer = self._layer
        if layer is not None and round(layer.opacity * 100) != percent:
            layer.opacity = percent / 100

    def _layer_opacity_change_slot(self, _layer: Layer, opacity: float) -> None:
        self._show_opacity(opacity)

    @staticmethod
    def _opacity_drag_started_slot() -> None:
        UndoStack().begin_gesture(OPACITY_UNDO_GESTURE)

    @staticmethod
    def _opacity_drag_finished_slot() -> None:
        UndoStack().end_gesture()

    # Blend mode:

    def _mode_change_slot(self, _index: int) -> None:
        mode = self._mode_box.mode()
        self._end_preview_slot()
        layer = self._layer
        if layer is not None and mode is not None and layer.composition_mode != mode:
            layer.composition_mode = mode

    def _layer_mode_change_slot(self, _layer: Layer, mode: CompositeMode) -> None:
        if self._preview_original is None:
            self._mode_box.set_mode(mode)

    def _preview_mode_slot(self, mode: CompositeMode) -> None:
        layer = self._layer
        if layer is None or not self._mode_box.isEnabled():
            return
        if self._preview_original is None:
            self._preview_original = layer.composition_mode
        layer.set_composition_mode(mode)

    def _end_preview_slot(self) -> None:
        original = self._preview_original
        if original is None:
            return
        self._preview_original = None
        if self._layer is not None:
            self._layer.set_composition_mode(original)

    @property
    def previewing(self) -> bool:
        """Whether a blend mode preview is showing on the layer."""
        return self._preview_original is not None

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the stripe that matches the active row's."""
        painter = QPainter(self)
        painter.fillRect(QRect(0, 0, SELECTION_STRIPE_WIDTH, self.height()), selection_stripe_color(self))
        painter.end()
