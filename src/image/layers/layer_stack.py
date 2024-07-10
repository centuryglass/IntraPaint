"""Represents a group of linked image layers that can be manipulated as one in limited ways."""
from typing import List, Optional, Dict, Any

from PyQt5.QtCore import Qt, QRect, pyqtSignal
from PyQt5.QtGui import QPainter, QImage

from src.image.layers.image_layer import ImageLayer, ImageLayerState
from src.image.layers.layer import Layer
from src.util.application_state import APP_STATE_NO_IMAGE, APP_STATE_EDITING, AppStateTracker
from src.util.cached_data import CachedData
from src.util.validation import assert_valid_index


class LayerStack(Layer):
    """Represents a group of linked image layers that can be manipulated as one in limited ways."""

    bounds_changed = pyqtSignal(Layer, QRect)
    layer_added = pyqtSignal(Layer)
    layer_removed = pyqtSignal(Layer)

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
            child_bounds = child.transformed_bounds
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
        copy.transform = self.transform
        copy.opacity = self.opacity
        copy.composition_mode = self.composition_mode
        for layer in self._layers:
            child_layer_copy = layer.copy()
            copy.insert_layer(child_layer_copy, copy.count)
        return copy

    def cut_masked(self, image_mask: QImage) -> None:
        """Clear the contents of an area in the parent image."""
        assert image_mask.size() == self.local_bounds.size(), 'Mask should be pre-converted to image size'
        for layer in self._layers:
            transformed_mask = QImage(layer.size, QImage.Format_ARGB32_Premultiplied)
            transformed_mask.fill(Qt.transparent)
            painter_transform = layer.transform.inverted()[0]
            painter = QPainter(transformed_mask)
            painter.setTransform(painter_transform)
            painter.drawImage(layer.local_bounds, image_mask)
            painter.end()
            layer.cut_masked(transformed_mask)

    def get_qimage(self) -> QImage:
        """Returns combined visible layer content as a QImage object."""
        if self._image_cache.valid:
            return self._image_cache.data
        image_bounds = self.local_bounds
        image = QImage(image_bounds.size(), QImage.Format.Format_ARGB32_Premultiplied)
        if not image_bounds.isEmpty():
            image.fill(Qt.transparent)
            painter = QPainter(image)
            for layer in reversed(self._layers):
                if not layer.visible:
                    continue
                layer_image, layer_translate = layer.transformed_image()
                if layer_image is not None:
                    painter.setOpacity(layer.opacity)
                    painter.setCompositionMode(layer.composition_mode)
                    painter.setTransform(layer_translate, False)
                    painter.drawImage(QRect(-image_bounds.topLeft(), layer_image.size()), layer_image)
            painter.end()
        self._image_cache.data = image
        return image

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
            elif isinstance(layer, LayerStack):
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
            parent = parent.layer_parent
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
        layer.transform_changed.disconnect(self._layer_bounds_change_slot)
        layer.size_changed.disconnect(self._layer_bounds_change_slot)

        index = self.get_layer_index(layer)
        assert index is not None
        self._layers.pop(index)
        layer.layer_parent = None
        if layer.visible:
            self.invalidate_pixmap()
            self._image_cache.invalidate()
            self.content_changed.emit(self)
        self._get_local_bounds()  # Ensure size is correct
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
        layer.transform_changed.connect(self._layer_bounds_change_slot)
        layer.size_changed.connect(self._layer_bounds_change_slot)
        self._layers.insert(index, layer)
        layer.layer_parent = self
        if len(self._layers) == 1 and AppStateTracker.app_state() == APP_STATE_NO_IMAGE:
            AppStateTracker.set_app_state(APP_STATE_EDITING)
        if layer.visible and not empty_image:
            self._image_cache.invalidate()
            self.invalidate_pixmap()
            self.content_changed.emit(self)
        self._get_local_bounds()  # Ensure size is correct
        self.layer_added.emit(layer)

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
        self.set_transform(saved_state.transform)
        restore_list = list(saved_state.child_states.keys())
        for layer in self._layers:
            if layer.id in saved_state.child_states:
                layer.restore_state(saved_state.child_states[layer.id])
                restore_list.remove(layer.id)
            else:
                raise RuntimeError(f'Found extra layer {layer.name}:{layer.id} when restoring {self.name}:{self.id}')
        if len(restore_list) > 0:
            raise RuntimeError(f'Missing {len(restore_list)} layers when restoring {self.name}:{self.id}')

    def set_visible(self, visible: bool, send_signals: bool = True) -> None:
        super().set_visible(visible, send_signals)
        for layer in self.recursive_child_layers:
            layer.visibility_changed.emit(layer, layer.visible)

    def _is_empty(self) -> bool:
        if any(layer.empty for layer in self._layers):
            return False
        return True

    def _layer_content_change_slot(self, layer: ImageLayer, _=None) -> None:
        if layer.visible and layer in self._layers:
            self._image_cache.invalidate()
            self.invalidate_pixmap()
            self._get_local_bounds()  # Ensure size is correct

    def _layer_visibility_change_slot(self, layer: ImageLayer, _) -> None:
        if layer in self._layers:
            self._image_cache.invalidate()
            self.invalidate_pixmap()

    def _layer_bounds_change_slot(self, layer: ImageLayer, _) -> None:
        if layer in self._layers:
            self._image_cache.invalidate()
            self.invalidate_pixmap()
            self.content_changed.emit(self)
            self._get_local_bounds()  # Ensure size is correct


class LayerStackState:
    """Preserves a copy of a layer stack's state."""

    def __init__(self, layer: LayerStack) -> None:
        self.name = layer.name
        self.id = layer.id
        self.visible = layer.visible
        self.opacity = layer.opacity
        self.mode = layer.composition_mode
        self.transform = layer.transform
        self.child_states: Dict[int, ImageLayerState | LayerStackState] = {}
        for i in range(layer.count):
            child = layer.get_layer_by_index(i)
            self.child_states[child.id] = child.save_state()
