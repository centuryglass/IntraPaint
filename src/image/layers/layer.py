"""Interface for any entity that can exist within an image layer stack."""
import datetime
from typing import Any, Callable, Optional, Tuple

from PyQt5.QtCore import QObject, pyqtSignal, QRect, QPoint, QSize, QRectF, Qt
from PyQt5.QtGui import QPainter, QImage, QPixmap, QTransform, QPolygonF

from src.config.application_config import AppConfig
from src.image.mypaint.numpy_image_utils import image_data_as_numpy_8bit, is_fully_transparent
from src.undo_stack import commit_action, last_action, _UndoAction
from src.util.cached_data import CachedData


class Layer(QObject):
    """Interface for any entity that can exist within an image layer stack."""

    name_changed = pyqtSignal(QObject, str)
    visibility_changed = pyqtSignal(QObject, bool)
    content_changed = pyqtSignal(QObject)
    opacity_changed = pyqtSignal(QObject, float)
    size_changed = pyqtSignal(QObject, QSize)
    transform_changed = pyqtSignal(QObject, QTransform)
    composition_mode_changed = pyqtSignal(QObject, QPainter.CompositionMode)
    z_value_changed = pyqtSignal(QObject, int)

    _next_layer_id = 0

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = str(name)
        self._visible = True
        self._opacity = 1.0
        self._size = QSize()
        self._transform = QTransform()
        self._mode = QPainter.CompositionMode.CompositionMode_SourceOver
        self._pixmap = CachedData(None)
        self._id = Layer._next_layer_id
        self._parent: Optional[Layer] = None
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
    def parent(self) -> Optional['Layer']:
        """Gets the layer this layer is contained within, if any."""
        return self._parent

    @parent.setter
    def parent(self, new_parent: Optional['Layer']) -> None:
        """Sets or clears this layer's parent layer."""
        if new_parent is None and self._parent is not None:
            assert not self._parent.contains(self), (f'Layer {self.name}:{self.id} not removed from '
                                                     f'parent {self._parent.name}:{self._parent.id} before clearing'
                                                     ' parent property.')
        if new_parent is not None:
            assert new_parent.contains(self), (f'Layer {self.name}:{self.id} parent set'
                                               f' to {new_parent.name}:{new_parent.id}), but that layer does not '
                                                'contain this one.')
        self._parent = new_parent

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
    def composition_mode(self) -> QPainter.CompositionMode:
        """Access the layer's rendering mode."""
        return self._mode

    @composition_mode.setter
    def composition_mode(self, new_mode: QPainter.CompositionMode) -> None:
        assert isinstance(new_mode, QPainter.CompositionMode)
        self._apply_combinable_change(new_mode, self._mode, self.set_composition_mode, 'layer.composition_mode')

    @property
    def transform(self) -> QTransform:
        """Returns the layer's matrix transformation."""
        return QTransform(self._transform)

    @transform.setter
    def transform(self, new_transform: QTransform) -> None:
        self._apply_combinable_change(new_transform, self._transform, self.set_transform, 'layer.transform')

    def _get_local_bounds(self) -> QRect:
        return QRect(QPoint(), self.size)

    @property
    def local_bounds(self) -> QRect:
        """Returns the layer's bounds with no transformations applied."""
        return self._get_local_bounds()

    @property
    def transformed_bounds(self) -> QRect:
        """Returns the layer's bounds after applying its transformation."""
        bounds = self.local_bounds
        return self._transform.map(QPolygonF(QRectF(bounds))).boundingRect().toAlignedRect()

    @property
    def full_image_bounds(self) -> QRect:
        """Returns the layer's bounds within the uppermost layer, with all transforms applied."""
        bounds = self.local_bounds
        return self.map_rect_to_image(bounds)

    @property
    def full_image_transform(self) -> QTransform:
        """Returns this layers transformation combined with all parent transformation."""
        stack_iter = self
        transform = QTransform()
        while stack_iter is not None:
            transform = transform * stack_iter._transform
            stack_iter = stack_iter.parent
        return transform

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
        stack_iter = self
        while stack_iter is not None:
            if not stack_iter._visible:
                return False
            stack_iter = stack_iter.parent
        return True

    @visible.setter
    def visible(self, visible: bool):
        """Sets whether this layer is marked as visible."""
        self._apply_combinable_change(visible, self._visible, self.set_visible, 'layer.visibility')

    def _is_empty(self) -> bool:
        if self.size.isEmpty():
            return True
        image_array = image_data_as_numpy_8bit(self.get_qimage())
        return is_fully_transparent(image_array)

    @property
    def empty(self) -> bool:
        """Returns whether this layer contains only fully transparent pixels."""
        return self._is_empty()

    @property
    def image(self) -> QImage:
        """Returns a copy of the layer content as a QImage object"""
        return self.get_qimage().copy()

    @image.setter
    def image(self, new_image: QImage | Tuple[QImage, QPoint]) -> None:
        """Replaces the layer's QImage content.  Unlike other setters, subsequent changes won't be combined in the
           undo history."""
        if isinstance(new_image, tuple):
            new_image, offset = new_image
            undo_offset = None if offset is None else -offset
        else:
            offset = None
            undo_offset = None
        last_image = self.image

        def _update_image(img=new_image, off=offset) -> None:
            self.set_image(img, off)

        def _undo_image(img=last_image, off=undo_offset) -> None:
            self.set_image(img, off)

        commit_action(_update_image, _undo_image, 'Layer.image')

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

    def set_transform(self, transform: QTransform, send_signals: bool = True) -> None:
        """Updates the layer's matrix transformation."""
        if transform != self._transform:
            assert transform.isInvertible(), f'layer {self.name}:{self.id} given non-invertible transform'
            self._transform = transform
            if send_signals:
                self.transform_changed.emit(self, transform)

    def set_opacity(self, opacity: float, send_signals: bool = True) -> None:
        """Set the layer's opacity."""
        if opacity != self._opacity:
            self._opacity = opacity
            if send_signals:
                self.opacity_changed.emit(self, opacity)

    def set_composition_mode(self, mode: QPainter.CompositionMode, send_signals: bool = True) -> None:
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

    def set_image(self, new_image: QImage, offset: Optional[QPoint] = None) -> None:
        """Updates the layer image."""
        size_changed = new_image.size() != self._size
        if size_changed:
            new_size = new_image.size()
            self.set_size(new_size)
        if offset is not None and not offset.isNull():
            transform = self.transform
            transform.translate(offset.x(), offset.y())
            self.set_transform(transform)
        self.set_qimage(new_image)
        self._pixmap.invalidate()
        self.content_changed.emit(self)

    def set_size(self, new_size: QSize, send_signals: bool = True) -> None:
        """Updates the layer's size."""
        if self._size != QSize:
            self._size = QSize(new_size)
            self._pixmap.invalidate()
            if send_signals:
                self.size_changed.emit(self, new_size)

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

    def transformed_image(self, full_transform: bool = False) -> Tuple[QImage, QTransform]:
        """Apply all non-translating transformations to a copy of the image, returning it with the final translation."""
        bounds = self.full_image_bounds if full_transform else self.transformed_bounds
        layer_transform = self.full_image_transform if full_transform else self.transform
        offset = bounds.topLeft()
        final_transform = QTransform()
        final_transform.translate(offset.x(), offset.y())
        if final_transform == layer_transform:
            return self.image, self.transform
        image = QImage(bounds.size(), QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        paint_transform = layer_transform * QTransform.fromTranslate(-offset.x(), -offset.y())
        painter.setTransform(paint_transform)
        painter.drawImage(self.local_bounds, self.get_qimage())
        painter.end()
        return image, final_transform

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

    def map_from_image(self, image_point: QPoint) -> QPoint:
        """Map a top level image point to the appropriate spot in the layer image."""
        inverse, invert_success = self.full_image_transform.inverted()
        assert invert_success
        assert isinstance(inverse, QTransform)
        return inverse.map(image_point)

    def map_rect_from_image(self, image_rect: QRect) -> QRect:
        """Map a top level image rectangle to the appropriate spot in the layer image."""
        inverse, invert_success = self.full_image_transform.inverted()
        assert invert_success
        assert isinstance(inverse, QTransform)
        return inverse.map(QPolygonF(QRectF(image_rect))).boundingRect().toAlignedRect()

    def map_to_image(self, layer_point: QPoint) -> QPoint:
        """Map a point in the layer image to its final spot in the top level image."""
        return self.full_image_transform.map(layer_point)

    def map_rect_to_image(self, layer_rect: QRect) -> QRect:
        """Map a rectangle in the layer image to its final spot in the top level image."""
        return self.full_image_transform.map(QPolygonF(QRectF(layer_rect))).boundingRect().toAlignedRect()

    def _apply_combinable_change(self,
                                    new_value: Any,
                                    last_value: Any,
                                    value_setter: Callable[[Any], None],
                                    change_type: str) -> None:
        if last_value == new_value:
            return

        def _update(value=new_value, setter=value_setter):
            setter(value)

        def _undo(value=last_value, setter=value_setter):
            setter(value)

        prev_action: Optional[_UndoAction]
        timestamp = datetime.datetime.now().timestamp()
        merge_interval = AppConfig().get(AppConfig.UNDO_MERGE_INTERVAL)
        with last_action() as prev_action:
            if prev_action is not None and prev_action.type == change_type and prev_action.action_data is not None \
                    and prev_action.action_data['layer'] == self \
                    and timestamp - prev_action.action_data['timestamp'] < merge_interval:
                prev_action.redo = _update
                prev_action.redo()
                return
        commit_action(_update, _undo, change_type, {'layer': self, 'timestamp': timestamp})

