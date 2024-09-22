"""Represents a group of linked image layers that can be manipulated as one in limited ways."""
from typing import List, Optional, Dict, Any, TypeAlias, Callable

from PySide6.QtCore import QRect, Signal, QPoint
from PySide6.QtGui import QPainter, QImage, QTransform

from src.image.composite_mode import CompositeMode
from src.image.layers.image_layer import ImageLayer, ImageLayerState
from src.image.layers.layer import Layer, LayerParent
from src.image.layers.text_layer import TextLayer
from src.image.layers.transform_layer import TransformLayer
from src.undo_stack import UndoStack
from src.util.application_state import APP_STATE_NO_IMAGE, APP_STATE_EDITING, AppStateTracker
from src.util.cached_data import CachedData
from src.util.signals_blocked import signals_blocked
from src.util.visual.geometry_utils import map_rect_precise
from src.util.visual.image_utils import create_transparent_image
from src.util.validation import assert_valid_index


RenderAdjustFn: TypeAlias = Callable[[int, QImage, QRect, QPainter], Optional[QImage]]


class LayerStack(Layer, LayerParent):
    """Represents a group of linked image layers that can be manipulated as one in limited ways."""

    bounds_changed = Signal(Layer, QRect)
    layer_added = Signal(Layer)
    layer_removed = Signal(Layer)

    def __init__(self, name: str) -> None:
        """Initialize with no layer data."""
        super().__init__(name)
        self._image_cache = CachedData(None)
        self._layers: List[Layer] = []
        self._bounds = QRect()

    # PROPERTY DEFINITIONS:

    @property
    def count(self) -> int:
        """Returns the number of layers"""
        return len(self._layers)

    def _get_local_bounds(self) -> QRect:
        bounds = None
        for child in self._layers:
            if isinstance(child, TransformLayer):
                child_bounds = child.transformed_bounds
            else:
                child_bounds = child.bounds
            if bounds is None:
                bounds = child_bounds
            else:
                bounds = bounds.united(child_bounds)
        if bounds is None:
            return QRect()
        if self.size != bounds.size():
            self.set_size(bounds.size())
        return bounds

    @property
    def has_image(self) -> bool:
        """Returns whether any image layers are present."""
        return len(self._layers) > 0

    @property
    def child_layers(self) -> List[Layer]:
        """Returns all child layers."""
        return [*self._layers]

    @property
    def recursive_child_layers(self) -> List[Layer]:
        """Returns all child layers or children of child layers, recursively."""
        flattened_stack = []

        def _unpack_layers(layer_stack: LayerStack):
            for idx in range(layer_stack.count):
                child_layer = layer_stack.get_layer_by_index(idx)
                flattened_stack.append(child_layer)
                if isinstance(child_layer, LayerStack):
                    _unpack_layers(child_layer)
        _unpack_layers(self)
        return flattened_stack

    def copy(self) -> 'LayerStack':
        """Returns a copy of this layer, and all the layers within it."""
        copy = LayerStack(self.name + ' (copy)')
        copy.opacity = self.opacity
        copy.composition_mode = self.composition_mode
        for layer in self._layers:
            child_layer_copy = layer.copy()
            copy.insert_layer(child_layer_copy, copy.count)
        return copy

    def cut_masked(self, image_mask: QImage) -> None:
        """Clear the contents of an area in the parent image."""
        assert image_mask.size() == self.bounds.size(), 'Mask should be pre-converted to layer group size'
        with UndoStack().combining_actions('image.layers.layer_stack.cut_masked'):
            for layer in self.recursive_child_layers:
                if isinstance(layer, LayerStack) or layer.locked:
                    continue
                layer_mask = create_transparent_image(layer.size)
                painter = QPainter(layer_mask)
                group_pos = self.bounds.topLeft()
                if isinstance(layer, TransformLayer):
                    painter_transform = layer.transform.inverted()[0]
                else:
                    layer_pos = layer.bounds.topLeft()
                    painter_transform = QTransform.fromTranslate(-layer_pos.x(), -layer_pos.y())
                painter.setTransform(QTransform.fromTranslate(group_pos.x(),  group_pos.y()) * painter_transform)
                painter.drawImage(0, 0, image_mask)
                painter.end()
                layer.cut_masked(layer_mask)

    def crop_to_content(self):
        """Crops the layer to remove transparent areas."""
        with UndoStack().combining_actions('image.layers.layer_stack.crop_to_content'):
            for layer in self.recursive_child_layers:
                if isinstance(layer, (LayerStack, TextLayer)) or layer.locked:
                    continue
                assert isinstance(layer, (ImageLayer, LayerStack))
                layer.crop_to_content(False)

    def get_qimage(self) -> QImage:
        """Returns combined visible layer content as a QImage object."""
        if self._image_cache.valid:
            return self._image_cache.data
        image = self.render()
        self._image_cache.data = image
        return image

    def render(self, base_image: Optional[QImage] = None,
               paint_param_adjuster: Optional[RenderAdjustFn] = None) -> QImage:
        """Render all layers to a QImage with a custom base image and accepting a function to control layer painting on
        a per-layer basis.

        Parameters
        ----------
        base_image: QImage, optional, default=None.
            The base image that all layer content will be painted onto.  If None, a new image will be created that's
            large enough to fit all layers.
        paint_param_adjuster: Optional[Callable[[int, QImage, QRect, QPainter) -> Optional[QImage]]
            Default=None. If provided, it will be called before each layer is painted, allowing it to directly make
            changes to the image, paint bounds, or painter as needed. Parameters are layer_id, layer_image,
            paint_bounds and layer_painter.  If it returns a QImage, that image will replace the layer image.
        Returns
        -------
        QImage: The final rendered image.
        """
        if base_image is None:
            image_bounds = self.bounds
            base_image = create_transparent_image(image_bounds.size())
        else:
            image_bounds = QRect(QPoint(), base_image.size())
        if not self.visible or self.opacity == 0.0 or image_bounds.isEmpty():
            return base_image
        if self.opacity != 1.0 or self.composition_mode != CompositeMode.NORMAL:
            final_base_image = base_image
            base_image = create_transparent_image(base_image.size())
        else:
            final_base_image = None

        offset = -image_bounds.topLeft()
        for layer in reversed(self._layers):
            if offset != QPoint():
                def _offset_adjuster(layer_id: int, layer_image: QImage, paint_bounds: QRect,
                                     layer_painter: QPainter) -> Optional[QImage]:
                    layer_painter.setTransform(layer_painter.transform() * QTransform.fromTranslate(offset.x(),
                                                                                                    offset.y()))
                    if paint_param_adjuster is not None:
                        return paint_param_adjuster(layer_id, layer_image, paint_bounds, layer_painter)
                    return None
                layer.render(base_image, _offset_adjuster)
            else:
                layer.render(base_image, paint_param_adjuster)
        if final_base_image is not None:
            qt_composite_mode = self.composition_mode.qt_composite_mode()
            if qt_composite_mode is not None:
                painter = QPainter(final_base_image)
                final_bounds = QRect(QPoint(), final_base_image.size())
                painter.setOpacity(self.opacity)
                painter.setCompositionMode(qt_composite_mode)
                if paint_param_adjuster is not None:
                    replacement_image = paint_param_adjuster(self.id, base_image, final_bounds, painter)
                    if replacement_image is not None:
                        base_image = replacement_image
                painter.drawImage(final_bounds, base_image)
                painter.end()
            else:
                composite_op = self.composition_mode.custom_composite_op()
                composite_op(base_image, final_base_image, self.opacity, None)
            return final_base_image
        return base_image

    def set_qimage(self, image: QImage) -> None:
        raise RuntimeError('Tried to directly assign image content to a LayerStack layer group')

    # LAYER ACCESS / MANIPULATION FUNCTIONS:

    def get_layer_by_index(self, index: int) -> Layer:
        """Returns a layer from the stack"""
        assert_valid_index(index, self._layers)
        return self._layers[index]

    def get_layer_by_id(self, layer_id: Optional[int]) -> Optional[Layer]:
        """Returns a layer from the stack, or None if no matching layer was found."""
        if layer_id is None:
            return None
        if layer_id == self.id:
            return self
        for layer in self._layers:
            if layer.id == layer_id:
                return layer
            if isinstance(layer, LayerStack):
                inner_layer = layer.get_layer_by_id(layer_id)
                if inner_layer is not None:
                    return inner_layer
        return None

    def get_layer_index(self, layer: Layer | int) -> Optional[int]:
        """Returns a layer's index in the stack, or None if it isn't found."""
        if isinstance(layer, Layer):
            try:
                return self._layers.index(layer)
            except (KeyError, ValueError):
                return None
        if isinstance(layer, int):
            for i in range(self.count):
                if self._layers[i].id == layer:
                    return i
        return None

    def contains(self, child_layer: Layer) -> bool:
        """Returns whether this layer contains a given child layer."""
        return child_layer in self._layers

    def contains_recursive(self, child_layer: Layer) -> bool:
        """Returns whether child_layer is underneath this layer in the layer tree."""
        parent = child_layer.layer_parent
        while parent is not None:
            if parent == self:
                return True
            if isinstance(parent, Layer):
                parent = parent.layer_parent
            else:
                parent = None
        return False

    def remove_layer(self, layer: Layer) -> None:
        """Removes a layer.

        - If the removed layer_index was invalid, throw an assertion error and exit.
        - If the removed layer was active, the previous layer becomes active, or no layer will become active if
          that was the last layer.
        - The 'layer_removed' signal is triggered.
        - If the active layer was after the removed layer, the 'active_layer_index_changed' signal is triggered with
          the adjusted layer_index.
        - If the removed layer was visible, the 'content_changed' signal is triggered.

        Parameters
        ----------
            layer: ImageLayer | int | None, default=None
                The layer object to copy, or its id. If None, the active layer will be used, and the method will fail
                silently if no layer is active.
        """
        assert layer in self._layers, f'layer {layer.name} is not in the image stack.'
        layer.content_changed.disconnect(self._layer_content_change_slot)
        layer.opacity_changed.disconnect(self._layer_content_change_slot)
        layer.composition_mode_changed.disconnect(self._layer_content_change_slot)
        layer.visibility_changed.disconnect(self._layer_visibility_change_slot)
        if isinstance(layer, TransformLayer):
            layer.transform_changed.disconnect(self._layer_bounds_change_slot)
        elif isinstance(layer, LayerStack):
            layer.bounds_changed.disconnect(self._layer_bounds_change_slot)
        layer.size_changed.disconnect(self._layer_bounds_change_slot)

        index = self.get_layer_index(layer)
        assert index is not None
        self._layers.pop(index)
        layer.layer_parent = None
        if layer.visible:
            self._image_cache.invalidate()
            self.invalidate_pixmap()
            self.content_changed.emit(self, layer.bounds if not isinstance(layer, TransformLayer)
                                      else layer.transformed_bounds)
        self._get_local_bounds()  # Ensure size is correct
        if isinstance(layer, LayerStack):
            child_layers = layer.child_layers
            for child_layer in child_layers:
                self.layer_removed.emit(child_layer)
            layer.layer_added.disconnect(self.layer_added)
            layer.layer_removed.disconnect(self.layer_removed)
        self.layer_removed.emit(layer)

    def insert_layer(self, layer: Layer, index: Optional[int]) -> None:
        """Insert a layer into the stack, optionally connect layer signals, and emit all required image stack signals.
           This does not alter the undo history."""
        if index is None:
            index = len(self._layers)
        assert layer not in self._layers, f'layer {layer.name}:{layer.id} is already in the image stack.'
        empty_image = layer.empty
        assert_valid_index(index, self._layers, allow_end=True)
        layer.content_changed.connect(self._layer_content_change_slot)
        layer.opacity_changed.connect(self._layer_content_change_slot)
        layer.composition_mode_changed.connect(self._layer_content_change_slot)
        layer.visibility_changed.connect(self._layer_visibility_change_slot)
        layer_bounds = layer.bounds
        if isinstance(layer, TransformLayer):
            layer_bounds = layer.transformed_bounds
            layer.transform_changed.connect(self._layer_bounds_change_slot)
        elif isinstance(layer, LayerStack):
            layer.bounds_changed.connect(self._layer_bounds_change_slot)
        bounds_changing = not layer_bounds.isEmpty() and not self._get_local_bounds().contains(layer_bounds)
        layer.size_changed.connect(self._layer_bounds_change_slot)
        self._layers.insert(index, layer)
        layer.layer_parent = self
        if len(self._layers) == 1 and AppStateTracker.app_state() == APP_STATE_NO_IMAGE:
            AppStateTracker.set_app_state(APP_STATE_EDITING)
        if layer.visible and not empty_image:
            self._image_cache.invalidate()
            self.invalidate_pixmap()
            self.content_changed.emit(self, self.bounds)
        self.layer_added.emit(layer)
        if bounds_changing:
            self._layer_bounds_change_slot(layer)
        if isinstance(layer, LayerStack):
            for child_layer in layer.recursive_child_layers:
                self.layer_added.emit(child_layer)
            layer.layer_added.connect(self.layer_added)
            layer.layer_removed.connect(self.layer_removed)

    def move_layer(self, layer: Layer, new_index: int) -> None:
        """Moves a layer to a new index.  This does not emit any signals or alter the undo history."""
        assert self.contains(layer) and 0 <= new_index < len(self._layers)
        current_index = self.get_layer_index(layer)
        assert current_index is not None and 0 <= current_index <= len(self._layers)
        if current_index == new_index:
            return
        self._layers.remove(layer)
        self._layers.insert(new_index, layer)

    def save_state(self) -> Any:
        """Export the current layer state, so it can be restored later."""
        return LayerStackState(self)

    def restore_state(self, saved_state: Any) -> None:
        """Restore the layer state from a previous saved state."""
        assert isinstance(saved_state, LayerStackState)
        assert self.id == saved_state.id, (f'saved state from layer {saved_state.id} applied to layer'
                                           f' {self.name}:{self.id}')
        self.set_name(saved_state.name)
        self.set_visible(saved_state.visible)
        self.set_opacity(saved_state.opacity)
        self.set_composition_mode(saved_state.mode)
        for i, layer in enumerate(saved_state.child_layers):
            layer_at_idx = None if self.count <= i else self.get_layer_by_index(i)
            if layer != layer_at_idx:
                if layer.layer_parent == self:
                    self.move_layer(layer, i)
                else:
                    self.insert_layer(layer, i)
            assert layer.id in saved_state.child_states
            if layer.locked:
                with signals_blocked(layer):
                    layer.set_locked(False)
                    if isinstance(layer, ImageLayer) and layer.alpha_locked:
                        layer.set_alpha_locked(False)
            layer.restore_state(saved_state.child_states[layer.id])
        while self.count > len(saved_state.child_layers):
            extra_layer = self.get_layer_by_index(len(saved_state.child_layers))
            assert extra_layer is not None
            self.remove_layer(extra_layer)

    def set_visible(self, visible: bool, send_signals: bool = True) -> None:
        super().set_visible(visible, send_signals)
        for layer in self.recursive_child_layers:
            layer.visibility_changed.emit(layer, layer.visible)

    def is_empty(self, bounds: Optional[QRect] = None) -> bool:
        """Returns whether this layer contains only fully transparent pixels, optionally restricting the check to a
           bounding rectangle."""
        for layer in self._layers:
            if bounds is not None and isinstance(layer, TransformLayer):
                layer_bounds = map_rect_precise(bounds, layer.transform.inverted()[0]).toAlignedRect()
            else:
                layer_bounds = bounds
            if not layer.is_empty(layer_bounds):
                return False
        return True

    def _layer_content_change_slot(self, layer: Layer, _=None) -> None:
        if layer.visible and layer in self._layers:
            self._image_cache.invalidate()
            self.invalidate_pixmap()
            bounds = self._get_local_bounds()  # Ensure size is correct
            self.content_changed.emit(self, bounds)

    def _layer_visibility_change_slot(self, layer: Layer, _=None) -> None:
        if layer in self._layers:
            self._image_cache.invalidate()
            self.invalidate_pixmap()
            self.content_changed.emit(self, self.bounds)

    def _layer_bounds_change_slot(self, layer: Layer, _=None) -> None:
        if layer in self._layers:
            self._image_cache.invalidate()
            self.invalidate_pixmap()
            bounds = self._get_local_bounds()  # Ensure size is correct
            self.content_changed.emit(self, bounds)
            self.bounds_changed.emit(self, bounds)


class LayerStackState:
    """Preserves a copy of a layer stack's state."""

    def __init__(self, layer: LayerStack) -> None:
        self.name = layer.name
        self.id = layer.id
        self.visible = layer.visible
        self.opacity = layer.opacity
        self.mode = layer.composition_mode
        self.child_states: Dict[int, ImageLayerState | LayerStackState] = {}
        self.child_layers: List[Layer] = []
        for i in range(layer.count):
            child = layer.get_layer_by_index(i)
            self.child_layers.append(child)
            self.child_states[child.id] = child.save_state()
