"""Manages an edited image layer."""
from sys import version_info

from src.image.layers.layer import Layer

if version_info[1] >= 11:
    from typing import Self, Optional, Any
else:
    from typing import Optional, Any
    from typing_extensions import Self
from collections.abc import Generator
from contextlib import contextmanager
from PyQt5.QtGui import QImage, QPainter, QPixmap, QTransform
from PyQt5.QtCore import Qt, QRect, QSize, QPoint
from PIL import Image
from src.ui.modal.modal_utils import show_error_dialog
from src.util.image_utils import image_content_bounds
from src.util.validation import assert_type, assert_types
from src.undo_stack import commit_action

CROP_TO_CONTENT_ERROR_TITLE = 'Layer cropping failed'
CROP_TO_CONTENT_ERROR_MESSAGE_EMPTY = 'Layer has no image content.'
CROP_TO_CONTENT_ERROR_MESSAGE_FULL = 'Layer is already cropped to fit image content.'


class ImageLayer(Layer):
    """Represents an edited image layer."""
    def __init__(self, image_data: QImage | QSize, name: str):
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
        if isinstance(image_data, QImage):
            self.set_image(image_data)
        elif isinstance(image_data, QSize):
            qimage = QImage(image_data, QImage.Format.Format_ARGB32_Premultiplied)
            qimage.fill(Qt.transparent)
            self.set_image(qimage)
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
        layer.set_transform(self.transform)
        return layer

    @contextmanager
    def borrow_image(self, change_bounds: Optional[QRect] = None) -> Generator[Optional[QImage], None, None]:
        """Provides direct access to the image for editing, automatically marking it as changed when complete."""
        try:
            yield self._image
        finally:
            self._pixmap.invalidate()
            self._handle_content_change(self._image, change_bounds)
            self.content_changed.emit(self)

    def resize_canvas(self, new_size: QSize, x_offset: int, y_offset: int, register_to_undo_history: bool = True):
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
        register_to_undo_history: bool, default=True
            Whether the resize operation should be registered to the undo history.
        """
        assert_type(new_size, QSize)
        assert_types((x_offset, y_offset), int)
        if new_size == self.size and x_offset == 0 and y_offset == 0:
            return
        offset = QPoint(x_offset, y_offset)
        new_image = QImage(new_size, QImage.Format.Format_ARGB32_Premultiplied)
        new_image.fill(Qt.transparent)
        painter = QPainter(new_image)
        painter.drawImage(-x_offset, -y_offset, self._image)
        painter.end()
        if register_to_undo_history:
            source_image = self.image
            source_offset = -offset

            def _resize(img=new_image, off=offset):
                self.set_image(img, off)

            def _restore(img=source_image, off=source_offset):
                self.set_image(img, off)

            commit_action(_resize, _restore, 'ImageLayer.resize_canvas')
        else:
            self.set_image(new_image, offset)

    def apply_transform(self) -> None:
        """Replace the image with the transformed image, setting the transform to one with only translation."""
        image, transform = self.transformed_image()
        if transform != self.transform:
            self.set_image(image)
            self.set_transform(transform)

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
        image_data: QImage
            Image data to draw into the image generation area. If the size of the image doesn't match the size of the
            bounds_rect, it will be scaled to fit.
        bounds_rect: QRect
            Area where image data will be inserted. if this is not fully contained within the layer bounds, the layer
            bounds will be extended.
        composition_mode: QPainter.CompositionMode, default=Source
            Mode used to insert image content. Default behavior is for the new image content to completely replace the
            old content.
        register_to_undo_history: bool, default=True
            Whether the change should be saved to the undo history.
        """
        assert_type(image_data, QImage)
        assert_type(bounds_rect, QRect)
        layer_bounds = self.local_bounds
        if not layer_bounds.contains(bounds_rect):
            merged_bounds = layer_bounds.intersected(bounds_rect)
            updated_image = QImage(merged_bounds.size(), QImage.Format_ARGB32_Premultiplied)
            updated_image.fill(Qt.transparent)
            painter = QPainter(updated_image)
            painter.drawImage(layer_bounds, self.get_qimage())
            painter.end()
            offset = -merged_bounds.topLeft()
        elif register_to_undo_history:
            # TODO: find a way to inject change bounds when setting self.image so special handling isn't needed
            #       to restrict post-processing to the change bounds:
            src_image = self.image
            def _update(img=image_data, bounds=bounds_rect):
                with self.borrow_image(bounds) as layer_image:
                    layer_painter = QPainter(layer_image)
                    layer_painter.drawImage(bounds, img)
                    layer_painter.end()

            def _undo(img=src_image):
                self.set_image(img)

            commit_action(_update, _undo, 'ImageLayer.insert_image_content')
            return
        else:
            updated_image = self.image
            offset = None
        painter = QPainter(updated_image)
        painter.setCompositionMode(composition_mode)
        painter.drawImage(bounds_rect, image_data)
        painter.end()
        if register_to_undo_history:
            self.image = (updated_image, offset)
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
        full_bounds = QRect(QPoint(), self.size)
        cropped_bounds = image_content_bounds(self._image)
        if cropped_bounds.isNull():
            show_error_dialog(None, CROP_TO_CONTENT_ERROR_TITLE, CROP_TO_CONTENT_ERROR_MESSAGE_EMPTY)
        elif cropped_bounds.size() == full_bounds.size():
            show_error_dialog(None, CROP_TO_CONTENT_ERROR_TITLE, CROP_TO_CONTENT_ERROR_MESSAGE_FULL)
        else:
            full_image = self._image.copy()
            cropped_image = full_image.copy(cropped_bounds)
            transform = self.transform
            crop_transform = QTransform(transform)
            crop_transform.translate(float(cropped_bounds.x()), float(cropped_bounds.y()))

            def _do_crop(img=cropped_image, matrix=crop_transform):
                self.set_image(img)
                self.set_transform(matrix)

            def _undo_crop(img=full_image, matrix=transform):
                self.set_image(img)
                self.set_transform(matrix)

            commit_action(_do_crop, _undo_crop, 'ImageLayer.crop_to_content')

    def cut_masked(self, image_mask: QImage) -> None:
        """Clear the contents of an area in the parent image."""
        layer_image = self.image
        assert image_mask.size() == layer_image.size(), 'Mask should be pre-converted to image size'
        painter = QPainter(layer_image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
        painter.drawImage(self.local_bounds, image_mask)
        painter.end()
        self.set_image(layer_image)

    def save_state(self) -> Any:
        """Export the current layer state, so it can be restored later."""
        return ImageLayerState(self.name, self.visible, self.opacity, self.composition_mode, self.transform, self.image)

    def restore_state(self, saved_state: Any) -> None:
        """Restore the layer state from a previous saved state."""
        assert isinstance(saved_state, ImageLayerState)
        self.set_name(saved_state.name)
        self.set_visible(saved_state.visible)
        self.set_opacity(saved_state.opacity)
        self.set_composition_mode(saved_state.mode)
        self.set_transform(saved_state.transform)
        self.set_image(saved_state.image)

    # INTERNAL:

    def _validate_bounds(self, bounds_rect: QRect):
        assert_type(bounds_rect, QRect)
        if not self.local_bounds.contains(bounds_rect):
            raise ValueError(f'{bounds_rect} not within {self.local_bounds}')


class ImageLayerState:
    """Preserves a copy of an image layer's state."""
    def __init__(self, name: str, visible: bool, opacity: float, mode: QPainter.CompositionMode,
                 transform: QTransform, image: QImage) -> None:
        self.name = name
        self.visible = visible
        self.opacity = opacity
        self.mode = mode
        self.transform = transform
        self.image = image
