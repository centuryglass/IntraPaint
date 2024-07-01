"""Interface for any entity that can exist within an image layer stack."""
from typing import Any, Callable, Optional

from PyQt5.QtCore import QObject, pyqtSignal, QRect, QPoint, QSize
from PyQt5.QtGui import QPainter, QImage, QPixmap

from src.image.mypaint.numpy_image_utils import image_data_as_numpy_8bit, is_fully_transparent
from src.undo_stack import commit_action, last_action, _UndoAction
from src.util.cached_data import CachedData


class Layer(QObject):
    """Interface for any entity that can exist within an image layer stack."""

    name_changed = pyqtSignal(QObject, str)
    visibility_changed = pyqtSignal(QObject, bool)
    content_changed = pyqtSignal(QObject)
    opacity_changed = pyqtSignal(QObject, float)
    bounds_changed = pyqtSignal(QObject, QRect)
    composition_mode_changed = pyqtSignal(QObject, QPainter.CompositionMode)

    _next_layer_id = 0

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = str(name)
        self._visible = True
        self._opacity = 1.0
        self._position = QPoint(0, 0)
        self._mode = QPainter.CompositionMode.CompositionMode_SourceOver
        self._pixmap = CachedData(None)
        self._id = Layer._next_layer_id
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
    def position(self) -> QPoint:
        """Returns the layer placement relative to the full image."""
        return QPoint(self._position)

    @position.setter
    def position(self, position: QPoint) -> None:
        """Updates the layer placement relative to the full image."""
        self._apply_combinable_change(position, self._position, self.set_position, 'layer.position')

    @property
    def size(self) -> QSize:
        """Returns the layer size in pixels as a QSize object."""
        return QSize(self.get_qimage().size())

    @property
    def bounds(self) -> QRect:
        """Returns the layer's position and size."""
        return QRect(self._position, self.size)

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
        return self._visible

    @visible.setter
    def visible(self, visible: bool):
        """Sets whether this layer is marked as visible."""
        self._apply_combinable_change(visible, self._visible, self.set_visible, 'layer.visibility')

    @property
    def empty(self) -> bool:
        """Returns whether this layer contains only fully transparent pixels."""
        if self.bounds.isEmpty():
            return True
        image_array = image_data_as_numpy_8bit(self.get_qimage())
        return is_fully_transparent(image_array)

    @property
    def image(self) -> QImage:
        """Returns a copy of the layer content as a QImage object"""
        return self.get_qimage().copy()

    @image.setter
    def image(self, new_image: QImage) -> None:
        """Replaces the layer's QImage content.  Unlike other setters, subsequent changes won't be combined in the
           undo history."""
        last_image = self.image

        def _update_image(img=new_image) -> None:
            self.set_image(img)

        def _undo_image(img=last_image) -> None:
            self.set_image(img)
        commit_action(_update_image, _undo_image)

    @property
    def pixmap(self) -> QPixmap:
        """Returns the layer's pixmap content."""
        if not self._pixmap.valid:
            self._pixmap.data = QPixmap.fromImage(self.get_qimage())
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

    def set_position(self, pos: QPoint, send_signals: bool = True) -> None:
        """Set the layer's saved offset value."""
        if pos != self._position:
            self._position = QPoint(pos)
            if send_signals:
                self.bounds_changed.emit(self, self.bounds)

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

    def set_image(self, new_image: QImage, send_signals: bool = True) -> None:
        """Updates the layer image."""
        size_changed = new_image.size() != self.get_qimage().size()
        self.set_qimage(new_image)
        self._pixmap.invalidate()
        if send_signals:
            if size_changed:
                self.bounds_changed.emit(self, self.bounds)
            self.content_changed.emit(self)

    # Unimplemented interface:

    def get_qimage(self) -> QImage:
        """Return layer image data as an ARGB32 formatted QImage."""
        raise NotImplementedError()

    def set_qimage(self, image: QImage) -> None:
        """Update the layer image data."""
        raise NotImplementedError()

    # Misc. utility:

    def refresh_pixmap(self) -> None:
        """Regenerate the image pixmap cache and notify self.content_changed subscribers."""
        self._pixmap.data = QPixmap.fromImage(self.get_qimage())
        self.content_changed.emit(self)

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
        with last_action() as prev_action:
            if prev_action is not None and prev_action.type == change_type and prev_action.action_data is not None \
                    and prev_action.action_data['layer'] == self:
                prev_action.redo = _update
                prev_action.redo()
                return
        commit_action(_update, _undo, change_type, {'layer': self})

