"""Manages an edited image layer."""
from sys import version_info

from src.image.layer import Layer

if version_info[1] >= 11:
    from typing import Self, Optional
else:
    from typing import Optional
    from typing_extensions import Self
from collections.abc import Generator
from contextlib import contextmanager
from PyQt5.QtGui import QImage, QPainter, QPixmap
from PyQt5.QtCore import Qt, QRect, QPoint, QSize
from PIL import Image
from src.ui.modal.modal_utils import show_error_dialog
from src.util.image_utils import pil_image_to_qimage, image_content_bounds
from src.util.validation import assert_type, assert_types
from src.undo_stack import commit_action

CROP_TO_CONTENT_ERROR_TITLE = 'Layer cropping failed'
CROP_TO_CONTENT_ERROR_MESSAGE_EMPTY = 'Layer has no image content.'
CROP_TO_CONTENT_ERROR_MESSAGE_FULL = 'Layer is already cropped to fit image content.'


class ImageLayer(Layer):
    """Represents an edited image layer."""
    def __init__(self, image_data: Image.Image | QImage | QSize, name: str):
        """
        Initializes a new layer with image data.

        Parameters
        ----------
        image_data: PIL Image or QImage or QSize
            Initial image data, or size of initial transparent image to create.
        name: str
            Name string to assign to this layer.
        """
        super().__init__(name)
        self._image = QImage()
        if isinstance(image_data, Image.Image):
            self.set_image(pil_image_to_qimage(image_data), False)
        elif isinstance(image_data, QImage):
            self.set_image(image_data, False)
        elif isinstance(image_data, QSize):
            qimage = QImage(image_data, QImage.Format.Format_ARGB32_Premultiplied)
            qimage.fill(Qt.transparent)
            self.set_image(qimage, False)
        else:
            raise TypeError(f'Invalid layer image data: {image_data}')

    def get_qimage(self) -> QImage:
        """Return layer image data as an ARGB32 formatted QImage."""
        return self._image

    def set_qimage(self, image: QImage) -> None:
        """Replaces the layer's QImage content."""
        if image.format() != QImage.Format_ARGB32_Premultiplied:
            self._image = image.convertToFormat(QImage.Format_ARGB32_Premultiplied)
        else:
            self._image = image.copy()
        self._handle_content_change(self._image)

    # LAYER/IMAGE FUNCTIONS:

    def copy(self) -> Self:
        """Creates a copy of this layer."""
        layer = ImageLayer(self._image.copy(), self.name + ' copy')
        layer.set_opacity(self.opacity)
        layer.set_visible(self.visible)
        layer.set_composition_mode(self.composition_mode)
        layer.set_position(self.position)
        return layer

    @contextmanager
    def borrow_image(self) -> Generator[Optional[QImage], None, None]:
        """Provides direct access to the image for editing, automatically marking it as changed when complete."""
        try:
            yield self._image
        finally:
            self._pixmap.invalidate()
            self._handle_content_change(self._image)
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
        self.image = new_image

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
            composition_mode: QPainter.CompositionMode = QPainter.CompositionMode.CompositionMode_Source,
            register_to_undo_history: bool = True) -> None:
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
        register_to_undo_history: bool, default=True
            Whether the change should be saved to the undo history.
        """
        assert_type(image_data, (QImage, QPixmap, Image.Image))
        assert_type(bounds_rect, QRect)
        self._validate_bounds(bounds_rect)
        updated_image = self.image
        painter = QPainter(updated_image)
        painter.setCompositionMode(composition_mode)
        if isinstance(image_data, QPixmap):
            painter.drawPixmap(bounds_rect, image_data)
        elif isinstance(image_data, (Image.Image, QImage)):
            qimage = image_data if isinstance(image_data, QImage) else pil_image_to_qimage(image_data)
            painter.drawImage(bounds_rect, qimage)
        painter.end()
        if register_to_undo_history:
            self.image = updated_image
        else:
            self.set_image(updated_image)

    def clear(self, save_to_undo_history: bool = True):
        """Replaces all image content with transparency."""
        cleared_image = QImage(self.size, QImage.Format_ARGB32_Premultiplied)
        cleared_image.fill(Qt.transparent)
        if save_to_undo_history:
            self.image = cleared_image
        else:
            self.set_image(cleared_image)

    def flip_horizontal(self):
        """Mirrors layer content horizontally, saving the change to the undo history."""
        self.image = self._image.mirrored(horizontal=True, vertical=False)

    def flip_vertical(self):
        """Mirrors layer content vertically, saving the change to the undo history."""
        self.image = self._image.mirrored(horizontal=False, vertical=True)

    def _handle_content_change(self, image: QImage, change_bounds: Optional[QRect] = None) -> None:
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
                self.set_image(cropped_image, False)
                self.set_position(full_bounds.topLeft() + cropped_bounds.topLeft(), False)
                self.bounds_changed.emit(self, self.bounds)
                self.content_changed.emit(self)

            def _undo_crop():
                self.set_image(full_image, False)
                self.set_position(full_bounds.topLeft(), False)
                self.bounds_changed.emit(self, self.bounds)
                self.content_changed.emit(self)
            commit_action(_do_crop, _undo_crop)

    # INTERNAL:

    def _validate_bounds(self, bounds_rect: QRect):
        assert_type(bounds_rect, QRect)
        layer_bounds = QRect(QPoint(0, 0), self.size)
        if not layer_bounds.contains(bounds_rect):
            raise ValueError(f'{bounds_rect} not within {layer_bounds}')
