"""Interface for any entity that can exist within an image layer stack."""
import datetime
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, Signal, QRect, QPoint, QSize
from PySide6.QtGui import QImage, QPixmap, QPainter

from src.config.application_config import AppConfig
from src.image.composite_mode import CompositeMode
from src.undo_stack import UndoStack, _UndoAction, _UndoGroup
from src.util.cached_data import CachedData
from src.util.image_utils import image_data_as_numpy_8bit, is_fully_transparent, create_transparent_image


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
    content_changed = Signal(QObject)
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
            self._locked = locked
            self.lock_changed.emit(self, locked)

        def _undo(locked=not lock) -> None:
            self._locked = locked
            self.lock_changed.emit(self, locked)

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

    @property
    def size(self) -> QSize:
        """Returns the layer size in pixels as a QSize object."""
        return self._size

    @size.setter
    def size(self, new_size: QSize):
        """Updates the layer size."""
        assert new_size.width() >= self.get_qimage().width() and new_size.height() >= self.get_qimage().height()
        self.size = new_size

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
        self._apply_combinable_change(visible, self._visible, self.set_visible, 'layer.visibility')

    def is_empty(self, bounds: Optional[QRect] = None) -> bool:
        """Returns whether this layer contains only fully transparent pixels, optionally restricting the check to a
           bounding rectangle."""
        image = self.get_qimage()
        if bounds is None:
            bounds = QRect(QPoint(), image.size())
        if bounds.isEmpty():
            return True
        image_array = image_data_as_numpy_8bit(self.get_qimage())
        image_array = image_array[bounds.y():bounds.y() + bounds.height(),
                                  bounds.x():bounds.x() + bounds.width(), :]
        return is_fully_transparent(image_array)

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
    def pixmap(self) -> QPixmap:
        """Returns the layer's pixmap content."""
        if not self._pixmap.valid:
            image = self.get_qimage()
            if not image.isNull():
                self._pixmap.data = QPixmap.fromImage(image)
            else:
                self._pixmap.data = QPixmap()
        return self._pixmap.data

    # Function interface:
    # Unlike the property interface, these changes are not registered in the undo history. Broadcasting changes through
    # signals is optional, enabled by default, and will never occur if the new value parameter matches the old value.

    def set_name(self, new_name: str, send_signals: bool = True) -> None:
        """Set the layer's display name."""
        if new_name != self._name:
            self._name = new_name
            if send_signals:
                self.name_changed.emit(self, new_name)

    def set_opacity(self, opacity: float, send_signals: bool = True) -> None:
        """Set the layer's opacity."""
        if opacity != self._opacity:
            self._opacity = opacity
            if send_signals:
                self.opacity_changed.emit(self, opacity)

    def set_composition_mode(self, mode: CompositeMode, send_signals: bool = True) -> None:
        """Set the layer's composition mode."""
        if mode != self._mode:
            self._mode = mode
            if send_signals:
                self.composition_mode_changed.emit(self, mode)

    def set_visible(self, visible: bool, send_signals: bool = True) -> None:
        """Sets whether this layer is visible."""
        if visible != self._visible:
            self._visible = visible
            if send_signals:
                self.visibility_changed.emit(self, visible)

    def set_size(self, new_size: QSize, send_signals: bool = True) -> None:
        """Updates the layer's size."""
        if self._size != QSize:
            self._size = QSize(new_size)
            self._pixmap.invalidate()
            if send_signals:
                self.size_changed.emit(self, new_size)

    def set_locked(self, locked: bool) -> None:
        """Locks or unlocks the layer."""
        if locked != self._locked:
            self._locked = locked
            self.lock_changed.emit(self, locked)

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

    # Misc. utility:
    def render(self, base_image: Optional[QImage] = None,
               paint_param_adjuster: Optional[Callable[[int, QImage, QRect, QPainter], Optional[QImage]]]
               = None) -> QImage:
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
        layer_image = self.get_qimage()
        if not self.visible or self.opacity == 0.0 or image_bounds.isEmpty() or layer_image is None \
                or layer_image.isNull():
            return base_image
        painter = QPainter(base_image)
        painter.setOpacity(self.opacity)
        layer_bounds = self.bounds
        if paint_param_adjuster is not None:
            new_image = paint_param_adjuster(self.id, layer_image, layer_bounds, painter)
            if new_image is not None:
                layer_image = new_image
        qt_composite_mode = self.composition_mode.qt_composite_mode()
        if qt_composite_mode is None:
            qt_composite_mode = CompositeMode.NORMAL.qt_composite_mode()
            composite_op = self.composition_mode.custom_composite_op()
            layer_image = layer_image.copy()
            composite_op(layer_image, base_image, QRect(), layer_bounds, painter.transform())
        painter.setCompositionMode(qt_composite_mode)
        painter.drawImage(layer_bounds, layer_image)
        painter.end()
        return base_image

    def cropped_image_content(self, bounds_rect: QRect) -> QImage:
        """Returns the contents of a bounding QRect as a QImage."""
        return self.get_qimage().copy(bounds_rect)

    def invalidate_pixmap(self) -> None:
        """Mark the cached pixmap as invalid to ensure it gets recreated when needed next."""
        self._pixmap.invalidate()

    def refresh_pixmap(self) -> None:
        """Regenerate the image pixmap cache and notify self.content_changed subscribers."""
        self._pixmap.data = QPixmap.fromImage(self.get_qimage())
        self.content_changed.emit(self)

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
