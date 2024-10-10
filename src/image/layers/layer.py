"""Interface for any entity that can exist within an image layer stack."""
import datetime
from contextlib import contextmanager
from typing import Any, Callable, Optional, Set, Generator

from PySide6.QtCore import QObject, Signal, QRect, QPoint, QSize, QRectF
from PySide6.QtGui import QImage, QPixmap, QPainter, QTransform, QPainterPath, QPolygonF
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.image.composite_mode import CompositeMode
from src.ui.modal.modal_utils import show_error_dialog
from src.undo_stack import UndoStack, _UndoAction, _UndoGroup
from src.util.cached_data import CachedData
from src.util.visual.geometry_utils import map_rect_precise
from src.util.visual.image_utils import (create_transparent_image, NpAnyArray, image_data_as_numpy_8bit_readonly,
                                         image_is_fully_transparent)

# The QCoreApplication.translate context for strings in this file
TR_ID = 'image.layer.layer'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


ERROR_TITLE_SHOW_LAYER_FAILED = _tr('Showing layer failed')
ERROR_MESSAGE_LOCKED_PARENT = _tr('Cannot show layer "{layer_name}", parent layer "{parent_name}" is locked and'
                                  ' hidden.')


class LayerParent:
    """Defines the interface expected within layer parents.  LayerParent classes should also be Layers."""

    def get_layer_index(self, layer: 'Layer | int') -> Optional[int]:
        """Returns a layer's index in the stack, or None if it isn't found."""
        raise NotImplementedError

    def get_layer_by_index(self, index: int) -> 'Layer':
        """Returns a layer within the parent."""
        raise NotImplementedError()

    def get_layer_by_id(self, layer_id: Optional[int]) -> Optional['Layer']:
        """Returns a layer within the parent, or None if no matching layer was found."""
        raise NotImplementedError()

    def contains(self, child_layer: 'Layer') -> bool:
        """Returns whether this parent contains a given child layer."""
        raise NotImplementedError()

    def contains_recursive(self, child_layer: 'Layer') -> bool:
        """Returns whether child_layer is underneath this parent in the layer tree."""
        raise NotImplementedError()

    def remove_layer(self, layer: 'Layer') -> None:
        """Removes a layer."""
        raise NotImplementedError()

    def insert_layer(self, layer: 'Layer', index: Optional[int]) -> None:
        """Insert a layer within this parent."""
        raise NotImplementedError()


class Layer(QObject):
    """Interface for any entity that can exist within an image layer stack."""

    name_changed = Signal(QObject, str)
    visibility_changed = Signal(QObject, bool)
    content_changed = Signal(QObject, QRect)
    opacity_changed = Signal(QObject, float)
    size_changed = Signal(QObject, QSize)
    composition_mode_changed = Signal(QObject, CompositeMode)
    z_value_changed = Signal(QObject, int)
    lock_changed = Signal(QObject, bool)

    _next_layer_id = 0

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = str(name)
        self._visible = True
        self._opacity = 1.0
        self._size = QSize()
        self._mode = CompositeMode.NORMAL
        self._pixmap = CachedData(None)
        self._id = Layer._next_layer_id
        self._parent: Optional[LayerParent] = None
        self._locked = False
        self._z_value = 0
        self._content_change_timestamp = 0.0
        Layer._next_layer_id += 1

    # PROPERTY DEFINITIONS:
    # All changes made through property setters are registered in the undo history, and are broadcast through
    # appropriate signals.

    @property
    def name(self) -> str:
        """Returns the layer's name string."""
        return self._name

    @name.setter
    def name(self, new_name: str):
        """Updates the layer's name string."""
        self._apply_combinable_change(new_name, self._name, self.set_name, 'layer.name')

    @property
    def layer_parent(self) -> Optional[LayerParent]:
        """Gets the layer this layer is contained within, if any."""
        return self._parent

    @layer_parent.setter
    def layer_parent(self, new_parent: Optional[LayerParent]) -> None:
        """Sets or clears this layer's parent layer."""
        if new_parent is None and self._parent is not None:
            assert isinstance(self._parent, Layer)
            assert not self._parent.contains(self), (f'Layer {self.name}:{self.id} not removed from '
                                                     f'parent {self._parent.name}:{self._parent.id} before clearing'
                                                     ' parent property.')
        if new_parent is not None:
            assert new_parent != self
            assert isinstance(new_parent, Layer)
            assert new_parent.contains(self), (f'Layer {self.name}:{self.id} parent set'
                                               f' to {new_parent.name}:{new_parent.id}), but that layer does not '
                                               'contain this one.')
        self._parent = new_parent

    @property
    def locked(self) -> bool:
        """Returns whether changes to this layer are blocked."""
        return self._locked

    @locked.setter
    def locked(self, lock: bool) -> None:
        if lock == self._locked:
            return

        def _update_lock(locked=lock) -> None:
            self.set_locked(locked)

        def _undo(locked=not lock) -> None:
            self.set_locked(locked)

        UndoStack().commit_action(_update_lock, _undo, 'src.layers.layer.locked')

    @property
    def parent_locked(self) -> bool:
        """Return whether any of this layer's parents are locked."""
        parent_iter = self.layer_parent
        while parent_iter is not None:
            assert isinstance(parent_iter, Layer)
            if parent_iter.locked:
                return True
            parent_iter = parent_iter.layer_parent
        return False

    @property
    def z_value(self) -> int:
        """Represents this layer's depth within a scene."""
        return self._z_value

    @z_value.setter
    def z_value(self, new_z_value: int) -> None:
        if new_z_value != self._z_value:
            self._z_value = new_z_value
            self.z_value_changed.emit(self, new_z_value)

    @property
    def id(self) -> int:
        """Gets this layer's unique identifier"""
        return self._id

    @property
    def opacity(self) -> float:
        """Returns the layer opacity."""
        return self._opacity

    @opacity.setter
    def opacity(self, new_opacity) -> None:
        """Updates the layer opacity."""
        self._apply_combinable_change(new_opacity, self._opacity, self.set_opacity, 'layer.opacity')

    @property
    def composition_mode(self) -> CompositeMode:
        """Access the layer's rendering mode."""
        return self._mode

    @composition_mode.setter
    def composition_mode(self, new_mode: CompositeMode) -> None:
        assert isinstance(new_mode, CompositeMode)
        self._apply_combinable_change(new_mode, self._mode, self.set_composition_mode, 'layer.composition_mode')

    def _get_local_bounds(self) -> QRect:
        return QRect(QPoint(), self.size)

    @property
    def bounds(self) -> QRect:
        """Returns the layer's bounds."""
        return self._get_local_bounds()

    def _get_size(self) -> QSize:
        return self._size

    @property
    def size(self) -> QSize:
        """Returns the layer size in pixels as a QSize object."""
        return self._get_size()

    @property
    def width(self) -> int:
        """Returns the layer width in pixels."""
        return self.size.width()

    @property
    def height(self) -> int:
        """Returns the layer height in pixels."""
        return self.size.height()

    @property
    def visible(self) -> bool:
        """Returns whether this layer is marked as visible."""
        if not self._visible:
            return False
        parent = self.layer_parent
        if parent is not None:
            assert isinstance(parent, Layer)
            return parent.visible
        return True

    @visible.setter
    def visible(self, visible: bool):
        """Sets whether this layer is marked as visible."""
        if visible == self.visible:
            return
        if visible:  # Un-hide hidden parents without making other child layers visible:
            toggled_layers: Set[Layer] = set()
            if not self._visible:
                toggled_layers.add(self)
            parent = self.layer_parent
            while parent is not None:
                assert isinstance(parent, Layer)
                if not parent._visible:
                    if parent.locked or parent.parent_locked:
                        error_message = ERROR_MESSAGE_LOCKED_PARENT.format(layer_name=self.name,
                                                                           parent_name=parent.name)
                        show_error_dialog(None, ERROR_TITLE_SHOW_LAYER_FAILED, error_message)
                        return
                    toggled_layers.add(parent)
                    i = 0
                    while True:
                        try:
                            assert isinstance(parent, LayerParent)
                            child = parent.get_layer_by_index(i)
                            i += 1
                            if child._visible and not child.locked and child != self:
                                toggled_layers.add(child)
                        except ValueError:
                            break
                assert isinstance(parent, Layer)
                parent = parent.layer_parent

            def _toggle_all():
                for layer in toggled_layers:
                    layer.set_visible(not layer._visible)

            UndoStack().commit_action(_toggle_all, _toggle_all, 'layer.visible')
        else:
            self._apply_combinable_change(visible, self._visible, self.set_visible, 'layer.visibility')

    def is_empty(self, bounds: Optional[QRect] = None) -> bool:
        """Returns whether this layer contains only fully transparent pixels, optionally restricting the check to a
           bounding rectangle."""
        image = self.get_qimage()
        if bounds is None:
            bounds = QRect(QPoint(), image.size())
        if bounds.isEmpty():
            return True
        image_array = self.image_bits_readonly
        image_array = image_array[bounds.y():bounds.y() + bounds.height(),
                                  bounds.x():bounds.x() + bounds.width(), :]
        return image_is_fully_transparent(image_array)

    @property
    def empty(self) -> bool:
        """Returns whether this layer contains only fully transparent pixels."""
        return self.is_empty()

    def _image_prop_setter(self, _) -> None:
        raise NotImplementedError()

    @property
    def image(self) -> QImage:
        """Returns a copy of the layer content as a QImage object"""
        return self.get_qimage().copy()

    @image.setter
    def image(self, new_image: Any) -> None:
        """Unimplemented, replaces the layer's QImage content."""
        self._image_prop_setter(new_image)

    @property
    def image_bits_readonly(self) -> NpAnyArray:
        """Provide direct access to a read-only numpy array of the layer's image data."""
        return image_data_as_numpy_8bit_readonly(self.get_qimage())

    @property
    def pixmap(self) -> QPixmap:
        """Returns the layer's pixmap content."""
        if not self._pixmap.valid:
            image = self.get_qimage()
            if not image.isNull():
                self._pixmap.data = QPixmap.fromImage(image)
            else:
                self._pixmap.data = QPixmap()
        return self._pixmap.data

    @property
    def content_change_timestamp(self) -> float:
        """Returns the timestamp from the last content_changed signal emitted by this layer."""
        return self._content_change_timestamp

    # Function interface:
    # Unlike the property interface, these changes are not registered in the undo history. Broadcasting changes through
    # signals is optional, enabled by default, and will never occur if the new value parameter matches the old value.

    def set_name(self, new_name: str) -> None:
        """Set the layer's display name."""
        if new_name != self._name:
            self._name = new_name
            self.name_changed.emit(self, new_name)

    def set_opacity(self, opacity: float) -> None:
        """Set the layer's opacity."""
        if opacity != self._opacity:
            self._opacity = opacity
            self.opacity_changed.emit(self, opacity)
            if self.visible:
                self.signal_content_changed(self.bounds)

    def set_composition_mode(self, mode: CompositeMode) -> None:
        """Set the layer's composition mode."""
        if mode != self._mode:
            self._mode = mode
            self.composition_mode_changed.emit(self, mode)
            if self.visible and self.opacity > 0.0:
                self.signal_content_changed(self.bounds)

    def set_visible(self, visible: bool) -> None:
        """Sets whether this layer is visible."""
        if visible != self._visible:
            self._visible = visible
            self.visibility_changed.emit(self, visible)
            self.signal_content_changed(self.bounds)

    def get_visible(self) -> None:
        """Returns whether this layer is set to visible. Unlike the visible property, this ignores parent visibility."""
        return self._visible

    def set_size(self, new_size: QSize) -> None:
        """Updates the layer's size."""
        if self._size != QSize:
            self._size = QSize(new_size)
            self._pixmap.invalidate()
            self.size_changed.emit(self, new_size)
            if self.visible and self.opacity > 0.0:
                self.signal_content_changed(self.bounds)

    def set_locked(self, locked: bool) -> None:
        """Locks or unlocks the layer."""
        if locked != self._locked:
            self._locked = locked
            self.lock_changed.emit(self, locked)

    @contextmanager
    def with_lock_disabled(self) -> Generator[None, None, None]:
        """Temporarily disables layer locking while the context is held."""
        lock_state = self._locked
        self._locked = False
        yield
        self._locked = lock_state

    # Unimplemented interface:

    def get_qimage(self) -> QImage:
        """Return layer image data as an ARGB32 formatted QImage."""
        raise NotImplementedError()

    def set_qimage(self, image: QImage) -> None:
        """Update the layer image data."""
        raise NotImplementedError()

    def copy(self) -> 'Layer':
        """Returns a copy of this layer."""
        raise NotImplementedError()

    def cut_masked(self, image_mask: QImage) -> None:
        """Clear the contents of an area in the parent image."""
        raise NotImplementedError()

    def save_state(self) -> Any:
        """Export the current layer state, so it can be restored later."""
        raise NotImplementedError()

    def restore_state(self, saved_state: Any) -> None:
        """Restore the layer state from a previous saved state."""
        raise NotImplementedError()

    def contains(self, child_layer: 'Layer') -> bool:
        """Returns whether this layer contains a given child layer."""
        return False

    def contains_recursive(self, child_layer: 'Layer') -> bool:
        """Returns whether this layer recursively contains a given child layer."""
        return False

    # Misc. utility:

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
            Optional transformation to apply to image content before rendering.
        image_bounds: QRect, optional, default=None.
            Optional bounds that should be rendered within the base image. If None, the intersection of the base and the
            transformed layer will be used.
        z_max: int, optional, default=None
            If not None, rendering will be blocked at z-levels above this number.
        image_adjuster: Callable[[Layer, QImage], QImage], optional, default=None
            If not None, apply this final transformation function to the rendered image before compositing it onto
            the base.
        returned_mask: QImage, optional, default=None
            If not None, draw the rendered bounds onto this image, to use when determining what parts of the base image
            were rendered onto.
        """
        if self.render_would_be_empty(base_image, transform, image_bounds, z_max):
            return

        # Find the final bounds of all changes within base_image:
        if image_bounds is not None:
            final_bounds = QRect(image_bounds)
        else:
            if transform is not None:
                final_bounds = map_rect_precise(self.bounds, transform).toAlignedRect()
            else:
                final_bounds = self.bounds
        base_image_bounds = QRect(QPoint(), base_image.size())
        final_bounds = final_bounds.intersected(base_image_bounds)
        clip_path = QPainterPath()

        # find source bounds: the rectangle within the layer image painted in the final painting operation
        if transform is not None:
            # Minimize unnecessary transformation: find the smallest area within the source that we can transform
            # without excluding any transformed layer content that should render into the base image.
            final_bounds = image_bounds if image_bounds is not None else base_image_bounds

            # Use the inverse to find the smallest rectangle that completely covers the final bounds once transformed:
            inverse = transform.inverted()[0]
            source_bounds = map_rect_precise(final_bounds, inverse).toAlignedRect()

            # Any part of source_bounds that doesn't intersect with the layer can also be excluded:
            source_bounds = source_bounds.intersected(self.bounds)

            clip_path.addPolygon(inverse.map(QPolygonF(QRectF(final_bounds))))
        else:  # transform is None
            source_bounds = self.bounds.intersected(final_bounds)
            clip_path.addRect(final_bounds)

        layer_image = self.get_qimage()
        if layer_image is not None and not layer_image.isNull():
            if image_adjuster is not None:
                layer_image = image_adjuster(self, layer_image.copy())
            qt_composite_mode = self.composition_mode.qt_composite_mode()
            if qt_composite_mode is None:
                if transform is not None:
                    composite_transform = transform
                else:
                    composite_transform = QTransform.fromTranslate(final_bounds.x(), final_bounds.y())
                composite_op = self.composition_mode.custom_composite_op()
                composite_op(layer_image, base_image, self.opacity, composite_transform, final_bounds)
            else:
                painter = QPainter(base_image)
                painter.setOpacity(self.opacity)
                painter.setCompositionMode(qt_composite_mode)
                if transform is not None:
                    painter.setTransform(transform)
                painter.setClipPath(clip_path)
                painter.drawImage(source_bounds, layer_image, source_bounds)
                painter.end()

        if returned_mask is not None:
            assert returned_mask.size() == base_image.size()
            bounds_painter = QPainter(returned_mask)
            if transform is not None:
                bounds_painter.setTransform(transform)
            bounds_painter.setClipPath(clip_path)
            bounds_painter.drawImage(source_bounds, layer_image, source_bounds)
            bounds_painter.end()

    def render_to_new_image(self, transform: Optional[QTransform] = None,
                            inner_bounds: Optional[QRect] = None, z_max: Optional[int] = None,
                            image_adjuster: Optional[Callable[['Layer', QImage], QImage]] = None) -> QImage:
        """Render the layer to a new image, adjusting offset so that layer content fits exactly into the image."""

        bounds = self.bounds
        if transform is not None:
            bounds = map_rect_precise(bounds, transform).toAlignedRect()
        if inner_bounds is not None:
            bounds = bounds.intersected(inner_bounds)
        if not bounds.topLeft().isNull():
            if transform is None:
                transform = QTransform.fromTranslate(-bounds.x(), -bounds.y())
            else:
                transform = transform * QTransform.fromTranslate(-bounds.x(), -bounds.y())

        base_image = create_transparent_image(bounds.size())

        self.render(base_image, transform, image_bounds=bounds.translated(-bounds.x(), -bounds.y()),
                    z_max=z_max,
                    image_adjuster=image_adjuster)
        return base_image

    def render_would_be_empty(self, base_image: QImage, transform: Optional[QTransform] = None,
                              image_bounds: Optional[QRect] = None, z_max: Optional[int] = None) -> bool:
        """Given a set of rendering parameters, return True if nothing would be rendered."""
        base_image_bounds = QRect(QPoint(), base_image.size())

        # Exit early in any of the cases where nothing would render:
        # - If the layer is hidden or has opacity 0.0
        # - If z_max is defined, and this layer has a higher z-value
        # - If image_bounds is completely outside the base image
        # - If the layer transformation places the layer completely outside the base image.
        if (not self.visible or self.opacity == 0.0 or (z_max is not None and self.z_value > z_max) or
                (image_bounds is not None and not QRect(QPoint(), base_image.size()).intersects(image_bounds))):
            return True
        if transform is not None:
            transformed_bounds = map_rect_precise(self.bounds, transform).toAlignedRect()
            intersect_test_bounds = image_bounds if image_bounds is not None else base_image_bounds
            if not intersect_test_bounds.intersects(transformed_bounds):
                return True
        return False

    def cropped_image_content(self, bounds_rect: QRect) -> QImage:
        """Returns the contents of a bounding QRect as a QImage."""
        return self.get_qimage().copy(bounds_rect)

    def signal_content_changed(self, change_bounds: QRect) -> None:
        """Send the content change signal, saving the timestamp."""
        self._content_change_timestamp = datetime.datetime.now().timestamp()
        self.content_changed.emit(self, change_bounds)

    def invalidate_pixmap(self) -> None:
        """Mark the cached pixmap as invalid to ensure it gets recreated when needed next."""
        self._pixmap.invalidate()

    def _apply_combinable_change(self,
                                 new_value: Any,
                                 last_value: Any,
                                 value_setter: Callable[[Any], None],
                                 change_type: str) -> None:
        assert not self.locked and not self.parent_locked, f'Tried to change {change_type} in a locked layer'
        if last_value == new_value:
            return

        def _update(value=new_value, setter=value_setter):
            setter(value)

        def _undo(value=last_value, setter=value_setter):
            setter(value)

        prev_action: Optional[_UndoAction | _UndoGroup]
        timestamp = datetime.datetime.now().timestamp()
        merge_interval = AppConfig().get(AppConfig.UNDO_MERGE_INTERVAL)
        with UndoStack().last_action(change_type) as prev_action:
            if isinstance(prev_action, _UndoAction) and prev_action.type == change_type \
                    and prev_action.action_data is not None \
                    and prev_action.action_data['layer'] == self \
                    and timestamp - prev_action.action_data['timestamp'] < merge_interval:
                prev_action.redo = _update
                prev_action.redo()
                return
        UndoStack().commit_action(_update, _undo, change_type, {'layer': self, 'timestamp': timestamp})
