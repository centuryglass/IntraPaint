"""Manages an edited image layer."""
from sys import version_info
if version_info[1] >= 11:
    from typing import Self, Optional
else:
    from typing import Optional
    from typing_extensions import Self
from collections.abc import Generator
from contextlib import contextmanager
from PyQt5.QtGui import QImage, QPainter, QPixmap
from PyQt5.QtCore import Qt, QObject, QRect, QPoint, QSize, pyqtSignal
from PIL import Image
from src.ui.modal.modal_utils import show_error_dialog
from src.util.image_utils import pil_image_to_qimage, image_content_bounds
from src.util.validation import assert_type, assert_types
from src.util.cached_data import CachedData
from src.undo_stack import commit_action, last_action

CROP_TO_CONTENT_ERROR_TITLE = 'Layer cropping failed'
CROP_TO_CONTENT_ERROR_MESSAGE_EMPTY = 'Layer has no image content.'
CROP_TO_CONTENT_ERROR_MESSAGE_FULL = 'Layer is already cropped to fit image content.'


class ImageLayer(QObject):
    """Represents an edited image layer."""

    visibility_changed = pyqtSignal(QObject, bool)
    content_changed = pyqtSignal(QObject)
    opacity_changed = pyqtSignal(QObject, float)
    bounds_changed = pyqtSignal(QObject, QRect)

    _next_layer_id = 0

    def __init__(
            self,
            image_data: Image.Image | QImage | QSize,
            name: str,
            saved: bool = True):
        """
        Initializes a new layer with image data.

        Parameters
        ----------
        image_data: PIL Image or QImage or QSize
            Initial image data, or size of initial transparent image to create.
        name: str
            Name string to assign to this layer.
        saved: bool, default=True
            Whether this layer's data should be included when saving image data.
        """
        super().__init__()
        self._name = str(name)
        self._saved = bool(saved)
        self._visible = True
        self._image = QImage()
        self._opacity = 1.0
        self._pixmap = CachedData(None)
        self._position = QPoint(0, 0)
        self._id = ImageLayer._next_layer_id
        ImageLayer._next_layer_id += 1
        if isinstance(image_data, Image.Image):
            self.qimage = pil_image_to_qimage(image_data)
        elif isinstance(image_data, QImage):
            self.qimage = image_data
        elif isinstance(image_data, QSize):
            qimage = QImage(image_data, QImage.Format.Format_ARGB32_Premultiplied)
            qimage.fill(Qt.transparent)
            self.qimage = qimage
        else:
            raise TypeError(f'Invalid layer image data: {image_data}')

    # PROPERTY DEFINITIONS:
    @property
    def id(self) -> int:
        """Gets this layer's unique identifier"""
        return self._id

    @property
    def opacity(self) -> float:
        """Returns the layer opacity."""
        return self._opacity  # TODO: apply when saving

    @opacity.setter
    def opacity(self, new_opacity) -> None:
        """Updates the layer opacity."""
        self._opacity = new_opacity
        self.opacity_changed.emit(self, new_opacity)

    @property
    def position(self) -> QPoint:
        """Returns the layer placement relative to the full image."""
        return self._position

    @position.setter
    def position(self, position: QPoint) -> None:
        """Updates the layer placement relative to the full image."""
        last_position = self.position

        def _apply_move(pos: QPoint):
            self._position = pos
            self.bounds_changed.emit(self, self.geometry)

        # Merge position change operations in the undo history:
        action_type = 'image_layer.position'
        with last_action() as prev_action:
            if prev_action is not None and prev_action.type == action_type and prev_action.action_data is not None \
                    and prev_action.action_data['layer'] == self:
                prev_action.redo = lambda: _apply_move(position)
                prev_action.redo()
                return

        commit_action(lambda: _apply_move(position), lambda: _apply_move(last_position), action_type, {'layer': self})

    @property
    def qimage(self) -> QImage:
        """Returns a copy of the layer content as a QImage object"""
        return self._image.copy()

    @qimage.setter
    def qimage(self, new_image: QImage) -> None:
        """Replaces the layer's QImage content."""
        size_changed = new_image.size() != self.size
        if new_image.format() != QImage.Format_ARGB32_Premultiplied:
            self._image = new_image.convertToFormat(QImage.Format_ARGB32_Premultiplied)
        else:
            self._image = new_image.copy()
        self._handle_content_change(self._image)
        self._pixmap.invalidate()
        self.content_changed.emit(self)
        if size_changed:
            self.bounds_changed.emit(self, self.geometry)

    @property
    def pixmap(self) -> QPixmap:
        """Returns the layer's pixmap content."""
        if not self._pixmap.valid:
            self._pixmap.data = QPixmap.fromImage(self._image)
        return self._pixmap.data

    @property
    def size(self) -> QSize:
        """Returns the layer size in pixels as a QSize object."""
        return QSize(0, 0) if self._image is None else self._image.size()

    @size.setter
    def size(self, new_size: QSize) -> None:
        """Updates the layer size. Scales existing content, or creates with transparency if not initialized."""
        if self._image.isNull():
            self._image = QImage(new_size, QImage.Format.Format_ARGB32_Premultiplied)
            self._image.fill(Qt.transparent)
        elif new_size != self.size:
            self._image = self._image.scaled(new_size)
        else:
            return
        self._pixmap.invalidate()
        self._handle_content_change(self._image)
        self.content_changed.emit(self)
        self.bounds_changed.emit(self, self.geometry)

    @property
    def geometry(self) -> QRect:
        """Returns the layer's position and size."""
        return QRect(self.position, self.size)

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
        if self._visible != bool(visible):
            self._visible = bool(visible)
            self.visibility_changed.emit(self, self._visible)

    @property
    def name(self) -> str:
        """Returns the layer's name string."""
        return self._name

    @name.setter
    def name(self, new_name: str):
        """Updates the layer's name string."""
        assert_type(new_name, str)
        self._name = new_name

    @property
    def saved(self) -> bool:
        """Returns whether layer content is included when saving image data.  Non-visible layers are never saved."""
        return self._saved and self.visible

    @saved.setter
    def saved(self, saved: bool):
        """Sets whether this layer is saved when visible and image data is saved."""
        self._saved = saved

    # LAYER/IMAGE FUNCTIONS:

    def copy(self) -> Self:
        """Creates a copy of this layer."""
        layer = ImageLayer(self._image.copy(), self.name + ' copy', self.saved)
        layer.opacity = self.opacity
        return layer

    def set_position(self, position: QPoint, allow_undo=True):
        """Updates the layer placement relative to the full image, with the option to not register to change history."""
        if allow_undo:
            self.position = position
        else:
            self._position = position
            self.bounds_changed.emit(self, self.geometry)

    @contextmanager
    def borrow_image(self) -> Generator[Optional[QImage], None, None]:
        """Provides direct access to the image for editing, automatically marking it as changed when complete."""
        try:
            yield self._image
        finally:
            self._pixmap.invalidate()
            self._handle_content_change(self._image)
            self.content_changed.emit(self)

    def refresh_pixmap(self) -> None:
        """Regenerate the image pixmap cache and notify self.content_changed subscribers."""
        self._pixmap.data = QPixmap.fromImage(self._image)
        self.content_changed.emit(self)

    def resize_canvas(self, new_size: QSize, x_offset: int, y_offset: int):
        """
        Changes the layer size without scaling existing image content.

        Parameters
        ----------
        new_size: QSize
            New layer size in pixels.
        x_offset: int
            X offset where existing image content will be placed in the adjusted layer
        y_offset: int
            Y offset where existing image content will be placed in the adjusted layer
        """
        assert_type(new_size, QSize)
        assert_types((x_offset, y_offset), int)
        if new_size == self.size and x_offset == 0 and y_offset == 0:
            return
        new_image = QImage(new_size, QImage.Format.Format_ARGB32_Premultiplied)
        new_image.fill(Qt.transparent)
        painter = QPainter(new_image)
        painter.drawImage(x_offset, y_offset, self._image)
        painter.end()
        self._image = new_image
        self._pixmap.invalidate()
        self._handle_content_change(self._image)
        self.content_changed.emit(self)
        self.bounds_changed.emit(self, self.geometry)

    def cropped_image_content(self, bounds_rect: QRect) -> QImage:
        """Returns the contents of a bounding QRect as a QImage object."""
        assert_type(bounds_rect, QRect)
        try:
            self._validate_bounds(bounds_rect)
        except ValueError:
            return self._image.copy()
        return self._image.copy(bounds_rect)

    def insert_image_content(
            self,
            image_data: Image.Image | QImage | QPixmap,
            bounds_rect: QRect,
            composition_mode: QPainter.CompositionMode = QPainter.CompositionMode.CompositionMode_Source):
        """
        Replaces the contents of an area within the image with new image content.

        Parameters
        ----------
        image_data: PIL Image or QImage or QPixmap
            Image data to draw into the image generation area. If the size of the image doesn't match the size of the
            bounds_rect, it will be scaled to fit.
        bounds_rect: QRect
            Area where image data will be inserted. This must be within the edited image bounds.
        composition_mode: QPainter.CompositionMode, default=Source
            Mode used to insert image content. Default behavior is for the new image content to completely replace the
            old content.
        """
        assert_type(image_data, (QImage, QPixmap, Image.Image))
        assert_type(bounds_rect, QRect)
        self._validate_bounds(bounds_rect)
        with self.borrow_image() as layer_image:
            painter = QPainter(layer_image)
            painter.setCompositionMode(composition_mode)
            if isinstance(image_data, QPixmap):
                painter.drawPixmap(bounds_rect, image_data)
            elif isinstance(image_data, (Image.Image, QImage)):
                qimage = image_data if isinstance(image_data, QImage) else pil_image_to_qimage(image_data)
                painter.drawImage(bounds_rect, qimage)
            painter.end()

    def clear(self):
        """Replaces all image content with transparency."""
        self._image.fill(Qt.transparent)
        self.qimage = self._image

    def flip_horizontal(self):
        """Mirrors layer content horizontally, saving the change to the undo history."""

        def _flip():
            self.qimage = self._image.mirrored(horizontal=True, vertical=False)
        commit_action(_flip, _flip)

    def flip_vertical(self):
        """Mirrors layer content vertically, saving the change to the undo history."""

        def _flip():
            self.qimage = self._image.mirrored(horizontal=False, vertical=True)
        commit_action(_flip, _flip)

    def _handle_content_change(self, image: QImage) -> None:
        """Child classes should override to handle changes that they need to make before sending update signals."""

    def crop_to_content(self):
        """Crops the layer to remove transparent areas."""
        full_bounds = QRect(self.position, self.size)
        cropped_bounds = image_content_bounds(self._image)
        if cropped_bounds.isNull():
            show_error_dialog(None, CROP_TO_CONTENT_ERROR_TITLE, CROP_TO_CONTENT_ERROR_MESSAGE_EMPTY)
        elif cropped_bounds.size() == full_bounds.size():
            show_error_dialog(None, CROP_TO_CONTENT_ERROR_TITLE, CROP_TO_CONTENT_ERROR_MESSAGE_FULL)
        else:
            full_image = self._image.copy()
            cropped_image = full_image.copy(cropped_bounds)

            def _do_crop():
                self.qimage = cropped_image
                self.set_position(full_bounds.topLeft() + cropped_bounds.topLeft(), False)

            def _undo_crop():
                self.qimage = full_image
                self.set_position(full_bounds.topLeft(), False)
            commit_action(_do_crop, _undo_crop)

    # INTERNAL:

    def _validate_bounds(self, bounds_rect: QRect):
        assert_type(bounds_rect, QRect)
        layer_bounds = QRect(QPoint(0, 0), self.size)
        if not layer_bounds.contains(bounds_rect):
            raise ValueError(f'{bounds_rect} not within {layer_bounds}')
