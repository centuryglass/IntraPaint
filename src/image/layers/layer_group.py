"""Represents a group of linked image layers that can be manipulated as one in limited ways."""
from contextlib import contextmanager, ExitStack
from typing import List, Optional, Dict, Any, TypeAlias, Callable, Generator, Set

from PySide6.QtCore import QRect, Signal, QPoint, QSize, QTimer
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
from src.util.validation import assert_valid_index
from src.util.visual.geometry_utils import map_rect_precise
from src.util.visual.image_utils import create_transparent_image, image_data_as_numpy_8bit

RenderAdjustFn: TypeAlias = Callable[[int, QImage, QRect, QPainter], Optional[QImage]]

RENDER_DELAY_MS = 10


class LayerGroup(Layer, LayerParent):
    """Represents a group of linked image layers that can be manipulated as one in limited ways."""

    bounds_changed = Signal(Layer, QRect)
    isolate_changed = Signal(Layer, bool)
    layer_added = Signal(Layer)
    layer_removed = Signal(Layer)

    def __init__(self, name: str) -> None:
        """Initialize with no layer data."""
        super().__init__(name)
        self._image_cache = CachedData(None)
        self._layers: List[Layer] = []
        self._bounds = QRect()
        self._isolate = False
        self._render_timer = QTimer()
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(RENDER_DELAY_MS)
        self._render_timer.timeout.connect(self._start_render)

    # PROPERTY DEFINITIONS:

    @property
    def isolate(self) -> bool:
        """Access the isolate flag.  When isolate is true, child layer compositing is isolated from the rest of
           the image outside of this layer group."""
        return self._isolate

    @isolate.setter
    def isolate(self, isolate: bool) -> None:
        self._apply_combinable_change(isolate, self._isolate, self.set_isolate, 'layer_group.isolate')

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
        self._bounds = QRect(bounds)
        return bounds

    def flip_horizontal(self) -> None:
        """Flip the group horizontally."""
        if self.locked:
            raise ValueError('Attempted transformation on locked layer group.')
        for layer in self.recursive_child_layers:
            if layer.locked:
                raise ValueError(f'Attempted transformation on layer group containing locked layer {layer.name}.')
        bounds = self.bounds
        right_edge = self.bounds.x() + self.bounds.width()

        with UndoStack().combining_actions('LayerGroup.flip_horizontal') and self.all_signals_delayed():
            for layer in self.recursive_child_layers:
                if isinstance(layer, TransformLayer):
                    initial_bounds = layer.transformed_bounds
                    initial_x_offset = initial_bounds.x() - bounds.x()
                    final_x = right_edge - initial_x_offset - initial_bounds.width()
                    transform = layer.transform * QTransform.fromScale(-1.0, 1.0)
                    intermediate_transform_bounds = map_rect_precise(layer.bounds, transform).toAlignedRect()
                    transform = transform * QTransform.fromTranslate(final_x - intermediate_transform_bounds.x(), 0)
                    layer.transform = transform

    def flip_vertical(self, added_offset: int = 0, top_level=True) -> None:
        """Flip the group vertically."""
        if self.locked:
            raise ValueError('Attempted transformation on locked layer group.')
        for layer in self.recursive_child_layers:
            if layer.locked:
                raise ValueError(f'Attempted transformation on layer group containing locked layer {layer.name}.')
        bounds = self.bounds
        bottom_edge = self.bounds.y() + self.bounds.height()
        with UndoStack().combining_actions('LayerGroup.flip_vertical') and self.all_signals_delayed():
            for layer in self.recursive_child_layers:
                if isinstance(layer, TransformLayer):
                    initial_bounds = layer.transformed_bounds
                    initial_y_offset = initial_bounds.y() - bounds.y()
                    final_y = bottom_edge - initial_y_offset - initial_bounds.height() + added_offset
                    transform = layer.transform * QTransform.fromScale(1.0, -1.0)
                    intermediate_transform_bounds = map_rect_precise(layer.bounds, transform).toAlignedRect()
                    transform = transform * QTransform.fromTranslate(0, final_y - intermediate_transform_bounds.y())
                    layer.transform = transform

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

        def _unpack_layers(layer_stack: LayerGroup):
            for idx in range(layer_stack.count):
                child_layer = layer_stack.get_layer_by_index(idx)
                flattened_stack.append(child_layer)
                if isinstance(child_layer, LayerGroup):
                    _unpack_layers(child_layer)
        _unpack_layers(self)
        return flattened_stack

    def copy(self) -> 'LayerGroup':
        """Returns a copy of this layer, and all the layers within it."""
        copy = LayerGroup(self.name + ' (copy)')
        copy.opacity = self.opacity
        copy.composition_mode = self.composition_mode
        for layer in self._layers:
            child_layer_copy = layer.copy()
            copy.insert_layer(child_layer_copy, copy.count)
        return copy

    def cut_masked(self, image_mask: QImage) -> None:
        """Clear the contents of an area in the parent image."""
        assert image_mask.size() == self.bounds.size(), 'Mask should be pre-converted to layer group size'
        with UndoStack().combining_actions('image.layers.layer_group.cut_masked'):
            for layer in self.recursive_child_layers:
                if isinstance(layer, LayerGroup) or layer.locked or layer.parent_locked:
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

    def crop_to_content(self) -> None:
        """Crops the layer to remove transparent areas."""
        with UndoStack().combining_actions('image.layers.layer_group.crop_to_content'):
            for layer in self.recursive_child_layers:
                if isinstance(layer, (LayerGroup, TextLayer)) or layer.locked or layer.parent_locked:
                    continue
                assert isinstance(layer, (ImageLayer, LayerGroup))
                layer.crop_to_content()

    def set_isolate(self, isolate: bool) -> None:
        """Update the isolate flag.  When isolate is true, child layer compositing is isolated from the rest of
           the image outside of this layer group."""
        if isolate != self._isolate:
            self._isolate = isolate
            self.isolate_changed.emit(self, isolate)
            if self.count > 0:
                self.signal_content_changed(self.bounds)

    def get_qimage(self) -> QImage:
        """Returns combined visible layer content as a QImage object."""
        if self._image_cache.valid:
            return self._image_cache.data
        bounds = self.bounds
        image = create_transparent_image(bounds.size())
        self.render(base_image=image, transform=QTransform.fromTranslate(-bounds.x(), -bounds.y()))
        self._image_cache.data = image
        return image

    def render(self, base_image: QImage, transform: Optional[QTransform] = None,
               image_bounds: Optional[QRect] = None, z_max: Optional[int] = None,
               image_adjuster: Optional[Callable[['Layer', QImage], QImage]] = None,
               returned_mask: Optional[QImage] = None) -> None:
        """Renders the layer to QImage, optionally specifying render bounds, transformation, a z-level cutoff, and/or
           a final image transformation function.

        Parameters
        ----------
        base_image: QImage
            The base image that all layer content will be painted onto.
        transform: QTransform, optional, default=None
            Optional transformation to apply to image content before rendering. Only translations are supported, any
            other sort of transformation applied to a layer group will result in a ValueError
        image_bounds: QRect, optional, default=None.
            Optional bounds that should be rendered within the base image. If None, the intersection of the base and the
            transformed layer will be used.
        z_max: int, optional, default=None
            If not None, rendering will be blocked at z-levels above this number.
        image_adjuster: Callable[[Layer, QImage], QImage], optional, default=None
            Image adjusting function to pass on to child layers when rendering.
        returned_mask: QImage, optional, default=None
            If not None, draw the rendered bounds onto this image, to use when determining what parts of the base image
            were rendered onto.
        """
        if self.render_would_be_empty(base_image, transform, image_bounds, z_max):
            return

        # Validate that transform only contains offset, extract that offset:
        if transform is not None:
            if transform != QTransform.fromTranslate(transform.dx(), transform.dy()):
                raise ValueError('LayerGroup.render called with an incompatible transformation, only translation is '
                                 'supported.')
            transform_offset = QPoint(round(transform.dx()), round(transform.dy()))
        else:
            transform_offset = QPoint()

        # Find the final bounds of all changes within base_image:
        group_bounds = self.bounds
        if image_bounds is not None:
            final_bounds = QRect(image_bounds)
        else:
            final_bounds = group_bounds.translated(transform_offset)
        base_image_bounds = QRect(QPoint(), base_image.size())
        final_bounds = final_bounds.intersected(base_image_bounds)

        # Create an intermediate base to render child layers onto. All layers get rendered here, then that image is
        # rendered to the base with this layer's opacity and composition mode.
        if self.isolate:
            intermediate_base = create_transparent_image(final_bounds.size())
            compositing_mask = None if returned_mask is None else create_transparent_image(final_bounds.size())
        else:
            intermediate_base = base_image.copy(final_bounds)
            compositing_mask = create_transparent_image(final_bounds.size())

        # if there's no cropping, layer content would be translated so that the group bounds are at (0, 0)
        # if there is cropping, translate so that the final bounds are at (0, 0)
        layer_translation = QTransform.fromTranslate(-final_bounds.x() + transform_offset.x(),
                                                     -final_bounds.y() + transform_offset.y())
        for layer in reversed(self._layers):
            layer.render(base_image=intermediate_base, transform=layer_translation, z_max=z_max,
                         image_adjuster=image_adjuster, returned_mask=compositing_mask)
        if not self.isolate:
            assert compositing_mask is not None
            np_base = image_data_as_numpy_8bit(intermediate_base)
            np_mask = image_data_as_numpy_8bit(compositing_mask)
            mask_empty = np_mask[:, :, 3] == 0
            np_base[mask_empty, :] = 0

        qt_composite_mode = self.composition_mode.qt_composite_mode()

        if qt_composite_mode is not None:
            painter = QPainter(base_image)
            painter.setOpacity(self.opacity)
            painter.setCompositionMode(qt_composite_mode)
            painter.drawImage(final_bounds, intermediate_base)
            painter.end()
        else:
            composite_op = self.composition_mode.custom_composite_op()
            composite_transform = QTransform.fromTranslate(final_bounds.x(), final_bounds.y())
            composite_op(intermediate_base, base_image, self.opacity, composite_transform, final_bounds)

        if returned_mask is not None:
            assert compositing_mask is not None
            mask_painter = QPainter(returned_mask)
            mask_painter.drawImage(final_bounds, compositing_mask)
            mask_painter.end()

    def set_qimage(self, image: QImage) -> None:
        raise RuntimeError('Tried to directly assign image content to a LayerGroup')

    # LAYER ACCESS / MANIPULATION FUNCTIONS:

    def get_layer_by_index(self, index: int) -> Layer:
        """Returns a layer from the group"""
        assert_valid_index(index, self._layers)
        return self._layers[index]

    def get_layer_by_id(self, layer_id: Optional[int]) -> Optional[Layer]:
        """Returns a layer from the group, or None if no matching layer was found."""
        if layer_id is None:
            return None
        if layer_id == self.id:
            return self
        for layer in self._layers:
            if layer.id == layer_id:
                return layer
            if isinstance(layer, LayerGroup):
                inner_layer = layer.get_layer_by_id(layer_id)
                if inner_layer is not None:
                    return inner_layer
        return None

    def get_layer_index(self, layer: Layer | int) -> Optional[int]:
        """Returns a layer's index in the group, or None if it isn't found."""
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
        assert layer in self._layers, f'layer {layer.name} is not in the image group.'
        layer.content_changed.disconnect(self._layer_content_change_slot)
        if isinstance(layer, TransformLayer):
            layer.transform_changed.disconnect(self._layer_bounds_change_slot)
        elif isinstance(layer, LayerGroup):
            layer.bounds_changed.disconnect(self._layer_bounds_change_slot)
        layer.size_changed.disconnect(self._layer_bounds_change_slot)

        index = self.get_layer_index(layer)
        assert index is not None
        self._layers.pop(index)
        layer.layer_parent = None
        if layer.visible:
            self._trigger_render()
        last_bounds = self._bounds
        bounds = self._get_local_bounds()  # Ensure size is correct
        if bounds != last_bounds:
            self.bounds_changed.emit(self, bounds)
        if isinstance(layer, LayerGroup):
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
        assert layer not in self._layers, f'layer {layer.name}:{layer.id} is already in the image group.'
        empty_image = layer.empty
        assert_valid_index(index, self._layers, allow_end=True)
        layer.content_changed.connect(self._layer_content_change_slot)
        layer_bounds = layer.bounds
        if isinstance(layer, TransformLayer):
            layer_bounds = layer.transformed_bounds
            layer.transform_changed.connect(self._layer_bounds_change_slot)
        elif isinstance(layer, LayerGroup):
            layer.bounds_changed.connect(self._layer_bounds_change_slot)
        bounds_changing = not layer_bounds.isEmpty() and not self._get_local_bounds().contains(layer_bounds)
        layer.size_changed.connect(self._layer_bounds_change_slot)
        self._layers.insert(index, layer)
        layer.layer_parent = self
        if len(self._layers) == 1 and AppStateTracker.app_state() == APP_STATE_NO_IMAGE:
            AppStateTracker.set_app_state(APP_STATE_EDITING)
        if layer.visible and not empty_image:
            self._trigger_render()
        self.layer_added.emit(layer)
        if bounds_changing:
            self._layer_bounds_change_slot(layer)
        if isinstance(layer, LayerGroup):
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
        self._trigger_render()

    def save_state(self) -> Any:
        """Export the current layer state, so it can be restored later."""
        return LayerGroupState(self)

    def restore_state(self, saved_state: Any) -> None:
        """Restore the layer state from a previous saved state."""
        assert isinstance(saved_state, LayerGroupState)
        assert self.id == saved_state.id, (f'saved state from layer {saved_state.id} applied to layer'
                                           f' {self.name}:{self.id}')
        self.set_name(saved_state.name)
        self.set_visible(saved_state.visible)
        self.set_opacity(saved_state.opacity)
        self.set_composition_mode(saved_state.mode)
        self.set_isolate(saved_state.isolate)
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

    def set_visible(self, visible: bool) -> None:
        super().set_visible(visible)
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

    def set_locked(self, locked: bool) -> None:
        """Locks or unlocks the layer."""
        if locked != self.locked:
            super().set_locked(locked)
            self.propagate_parent_lock_signal(self)

    @contextmanager
    def all_signals_delayed(self) -> Generator[None, None, None]:
        """Blocks signals from this layer and all child layers, sending the delayed signals together when the context
           exits."""
        # Cache all signal-relevant non-image data from this layer and all children, recursive.
        content_change_timestamps: Dict[Layer, float] = {}
        layer_names: Dict[Layer, str] = {}
        visibility_states: Dict[Layer, bool] = {}
        opacity_states: Dict[Layer, float] = {}
        layer_sizes: Dict[Layer, QSize] = {}
        layer_modes: Dict[Layer, CompositeMode] = {}
        layer_z_values: Dict[Layer, int] = {}
        lock_states: Dict[Layer, bool] = {}
        parent_states: Dict[Layer, Optional[LayerGroup]] = {}
        layer_transforms: Dict[TransformLayer, QTransform] = {}
        alpha_lock_states: Dict[ImageLayer, bool] = {}
        isolate_states: Dict[LayerGroup, bool] = {}
        layer_bounds: Dict[LayerGroup, QRect] = {}
        layer_text_data: Dict[TextLayer, str] = {}

        all_layers: Set[Layer] = {self, *self.recursive_child_layers}
        for layer in all_layers:
            content_change_timestamps[layer] = layer.content_change_timestamp
            layer_names[layer] = layer.name
            visibility_states[layer] = layer.visible
            opacity_states[layer] = layer.opacity
            layer_sizes[layer] = layer.size
            layer_modes[layer] = layer.composition_mode
            layer_z_values[layer] = layer.z_value
            lock_states[layer] = layer.locked
            parent = layer.layer_parent
            assert parent is None or isinstance(parent, LayerGroup)
            parent_states[layer] = parent
            if isinstance(layer, TransformLayer):
                layer_transforms[layer] = layer.transform
            if isinstance(layer, ImageLayer):
                alpha_lock_states[layer] = layer.alpha_locked
            if isinstance(layer, LayerGroup):
                isolate_states[layer] = layer.isolate
                layer_bounds[layer] = layer.bounds
            if isinstance(layer, TextLayer):
                layer_text_data[layer] = layer.text_rect.serialize(False)

        try:
            with ExitStack() as stack:
                for layer in all_layers:
                    stack.enter_context(signals_blocked(layer))
                yield
        finally:
            updated_layer_list: Set[Layer] = {self, *self.recursive_child_layers}
            for layer in all_layers:
                old_parent = parent_states[layer]
                new_parent = layer.layer_parent
                if old_parent != new_parent:
                    if isinstance(old_parent, LayerGroup) and old_parent in all_layers:
                        old_parent.layer_removed.emit(layer)
                    if isinstance(new_parent, LayerGroup) and new_parent in all_layers:
                        new_parent.layer_added.emit(layer)
                if layer not in updated_layer_list:
                    assert new_parent not in updated_layer_list
                    continue
                if layer.content_change_timestamp > content_change_timestamps[layer]:
                    layer.content_changed.emit(layer, layer.bounds)
                if layer_names[layer] != layer.name:
                    layer.name_changed.emit(layer, layer.name)
                if visibility_states[layer] != layer.visible:
                    layer.visibility_changed.emit(layer, layer.visible)
                if opacity_states[layer] != layer.opacity:
                    layer.opacity_changed.emit(layer, layer.opacity)
                if layer_modes[layer] != layer.composition_mode:
                    layer.composition_mode_changed.emit(layer, layer.composition_mode)
                if layer_z_values[layer] != layer.z_value:
                    layer.z_value_changed.emit(layer, layer.z_value)
                if lock_states[layer] != layer.locked:
                    layer.lock_changed.emit(layer, layer.locked)
                if isinstance(layer, TransformLayer) and layer_transforms[layer] != layer.transform:
                    layer.transform_changed.emit(layer, layer.transform)
                if isinstance(layer, ImageLayer) and alpha_lock_states[layer] != layer.alpha_locked:
                    layer.alpha_lock_changed.emit(layer, layer.alpha_locked)
                if isinstance(layer, LayerGroup) and isolate_states[layer] != layer.isolate:
                    layer.isolate_changed.emit(layer, layer.isolate)
                if isinstance(layer, LayerGroup) and layer_bounds[layer] != layer.bounds:
                    layer.bounds_changed.emit(layer, layer.bounds)
                if isinstance(layer, TextLayer) and layer_text_data[layer] != layer.text_rect.serialize(False):
                    layer.text_data_changed.emit(layer.text_rect)

    def propagate_parent_lock_signal(self, source: Layer) -> None:
        """Pass on the lock signal from a parent layer through all child layers as appropriate."""
        assert source == self or source.contains_recursive(self)
        if not source.locked and self.locked:
            return
        for layer in self._layers:
            if source.locked or not layer.locked:
                layer.lock_changed.emit(source, source.locked)
            if isinstance(layer, LayerGroup):
                layer.propagate_parent_lock_signal(source)

    def _layer_content_change_slot(self, layer: Layer, _=None) -> None:
        if layer.visible and layer in self._layers and layer.content_change_timestamp > self.content_change_timestamp:
            self._trigger_render()

    def _layer_bounds_change_slot(self, layer: Layer, _=None) -> None:
        if layer in self._layers:
            last_bounds = self._bounds
            bounds = self._get_local_bounds()  # Ensure size is correct
            if bounds != last_bounds:
                self.bounds_changed.emit(self, bounds)
                if bounds.size() != last_bounds.size() and layer.content_change_timestamp \
                        > self.content_change_timestamp:
                    self._trigger_render()

    def _trigger_render(self) -> None:
        if not self._render_timer.isActive():
            self._render_timer.start()

    def _start_render(self) -> None:
        self._render_timer.stop()
        bounds = self._get_local_bounds()  # Ensure size is correct
        self._image_cache.invalidate()
        self.invalidate_pixmap()
        self.signal_content_changed(bounds)


class LayerGroupState:
    """Preserves a copy of a layer group's state."""

    def __init__(self, layer: LayerGroup) -> None:
        self.name = layer.name
        self.id = layer.id
        self.visible = layer.visible
        self.opacity = layer.opacity
        self.mode = layer.composition_mode
        self.isolate = layer.isolate
        self.child_states: Dict[int, ImageLayerState | LayerGroupState] = {}
        self.child_layers: List[Layer] = []
        for i in range(layer.count):
            child = layer.get_layer_by_index(i)
            self.child_layers.append(child)
            self.child_states[child.id] = child.save_state()
