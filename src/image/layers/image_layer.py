"""Manages an edited image layer."""
from collections.abc import Generator
from contextlib import contextmanager
from typing import Optional, Any, Tuple

from PIL import Image
from PyQt6.QtCore import QRect, QSize, QPoint, pyqtSignal, QObject
from PyQt6.QtGui import QImage, QPainter, QPixmap, QTransform

from src.image.layers.transform_layer import TransformLayer
from src.ui.modal.modal_utils import show_error_dialog
from src.undo_stack import commit_action
from src.util.image_utils import image_content_bounds, create_transparent_image
from src.util.validation import assert_type

CROP_TO_CONTENT_ERROR_TITLE = 'Layer cropping failed'
CROP_TO_CONTENT_ERROR_MESSAGE_EMPTY = 'Layer has no image content.'
CROP_TO_CONTENT_ERROR_MESSAGE_FULL = 'Layer is already cropped to fit image content.'


class ImageLayer(TransformLayer):
    """Represents an edited image layer."""

    alpha_lock_changed = pyqtSignal(QObject, bool)

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
            qimage = create_transparent_image(image_data)
            self.set_image(qimage)
        else:
            raise TypeError(f'Invalid layer image data: {image_data}')
        self._alpha_locked = False

    @property
    def alpha_locked(self) -> bool:
        """Return whether changes to transparent content in this layer are blocked."""
        return self._alpha_locked

    @alpha_locked.setter
    def alpha_locked(self, lock: bool) -> None:
        if lock == self._alpha_locked:
            return

        def _update_lock(locked=lock) -> None:
            self._alpha_locked = locked
            self.alpha_lock_changed.emit(self, locked)

        def _undo(locked=not lock) -> None:
            self._alpha_locked = locked
            self.alpha_lock_changed.emit(self, locked)

        commit_action(_update_lock, _undo, 'src.layers.image_layer.alpha_locked')

    def get_qimage(self) -> QImage:
        """Return layer image data as an ARGB32 formatted QImage."""
        return self._image

    def set_qimage(self, image: QImage) -> None:
        """Replaces the layer's QImage content."""
        assert not self.locked, 'Tried to change image in a locked layer'
        initial_image = self._image
        if image.format() != QImage.Format.Format_ARGB32_Premultiplied:
            self._image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        else:
            self._image = image.copy()
        self._handle_content_change(self._image, initial_image)

    # LAYER/IMAGE FUNCTIONS:

    def copy(self) -> 'ImageLayer':
        """Creates a copy of this layer."""
        layer = ImageLayer(self._image.copy(), self.name + ' copy')
        layer.set_opacity(self.opacity)
        layer.set_visible(self.visible)
        layer.set_composition_mode(self.composition_mode)
        layer.set_transform(self.transform)
        return layer

    def _image_prop_setter(self, new_image: QImage | Tuple[QImage, QPoint]) -> None:
        """Replaces the layer's QImage content.  Unlike other setters, subsequent changes won't be combined in the
           undo history."""
        assert not self.locked, f'Tried to change image in a locked layer'
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

    def set_image(self, new_image: QImage, offset: Optional[QPoint] = None) -> None:
        """Updates the layer image."""
        assert not self.locked, f'Tried to change image in a locked layer'
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

    @contextmanager
    def borrow_image(self, change_bounds: Optional[QRect] = None) -> Generator[Optional[QImage], None, None]:
        """Provides direct access to the image for editing, automatically marking it as changed when complete."""
        assert not self.locked, f'Tried to change image in a locked layer'
        if self.alpha_locked:
            initial_image = self.image.copy()
        else:
            initial_image = self._image
        try:
            yield self._image
        finally:
            self._pixmap.invalidate()
            self._handle_content_change(self._image, initial_image, change_bounds)
            self.content_changed.emit(self)

    def adjust_local_bounds(self, relative_bounds: QRect, register_to_undo_history: bool = True) -> None:
        """Changes local image bounds, cropping or extending the layer image.

        - All image content within the new bounds will remain at the same position and scale within the image.
        - Content outside the bounds will be removed.
        - Areas where the bounds don't intersect with the existing image will be filled with transparency.
        - The top-left position of layer.local_bounds will *not* change. If the new bounds do not have the same
          top left point, the layer translation will be adjusted.

        Parameters:
        ----------
        new_bounds: QRect
            The area the layer should occupy. This is relative to the local coordinate system, i.e. transformations
            do not apply.
        register_to_undo_history: bool, default=True
            Whether the resize operation should be registered to the undo history.
        """
        new_image = create_transparent_image(relative_bounds.size())
        painter = QPainter(new_image)
        painter.drawImage(-relative_bounds.x(), -relative_bounds.y(), self._image)
        painter.end()
        offset = relative_bounds.topLeft()
        if register_to_undo_history:
            source_image = self.image
            source_offset = -offset

            def _resize(img=new_image, off=offset):
                self.set_image(img, off)

            def _restore(img=source_image, off=source_offset):
                self.set_image(img, off)

            commit_action(_resize, _restore, 'ImageLayer.adjust_local_bounds')
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
        layer_bounds = self.bounds
        if not layer_bounds.contains(bounds_rect):
            merged_bounds = layer_bounds.united(bounds_rect)
            updated_image = create_transparent_image(merged_bounds.size())
            painter = QPainter(updated_image)
            painter.drawImage(layer_bounds.topLeft() - merged_bounds.topLeft(), self.get_qimage())
            painter.end()
            offset = QPoint()
            if merged_bounds.left() < layer_bounds.left():
                offset.setX(merged_bounds.left() - layer_bounds.left())
            if merged_bounds.top() < layer_bounds.top():
                offset.setY(merged_bounds.top() - layer_bounds.top())
            bounds_rect = QRect(bounds_rect.topLeft() - merged_bounds.topLeft(), bounds_rect.size())
            assert QRect(QPoint(), updated_image.size()).contains(bounds_rect)
        elif register_to_undo_history:
            # Used instead of self.image to ensure post-processing is restricted to the change bounds:
            src_image = self.get_qimage().copy(bounds_rect)

            def _update(img=image_data, bounds=bounds_rect, mode=composition_mode):
                with self.borrow_image(bounds) as layer_image:
                    layer_painter = QPainter(layer_image)
                    layer_painter.setCompositionMode(mode)
                    layer_painter.drawImage(bounds, img)
                    layer_painter.end()

            def _undo(img=src_image, bounds=bounds_rect):
                with self.borrow_image(bounds) as layer_image:
                    layer_painter = QPainter(layer_image)
                    layer_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
                    layer_painter.drawImage(bounds, img)
                    layer_painter.end()

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
            self.set_image(updated_image, offset)

    def clear(self, save_to_undo_history: bool = True):
        """Replaces all image content with transparency."""
        cleared_image = create_transparent_image(self.size)
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

    def set_alpha_locked(self, locked: bool) -> None:
        """Locks or unlocks layer alpha content."""
        if locked != self._alpha_locked:
            self._alpha_locked = locked
            self.alpha_lock_changed.emit(self, locked)

    def _handle_content_change(self, image: QImage, last_image: QImage, change_bounds: Optional[QRect] = None) -> None:
        """Preserve alpha channel if alpha is locked. Child classes should override to handle changes that they need to
         make before sending update signals."""
        if not hasattr(self, 'alpha_locked'):
            return
        if self.alpha_locked:
            painter = QPainter(image)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            painter.drawImage(QRect(0, 0, last_image.width(), last_image.height()), last_image)
            painter.end()

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
        painter.drawImage(self.bounds, image_mask)
        painter.end()
        self.set_image(layer_image)

    def save_state(self) -> Any:
        """Export the current layer state, so it can be restored later."""
        return ImageLayerState(self.name,
                               self.visible,
                               self.opacity,
                               self.composition_mode,
                               self.transform,
                               self.image,
                               self.locked,
                               self.alpha_locked)

    def restore_state(self, saved_state: Any) -> None:
        """Restore the layer state from a previous saved state."""
        assert isinstance(saved_state, ImageLayerState)
        self.set_name(saved_state.name)
        self.set_visible(saved_state.visible)
        self.set_opacity(saved_state.opacity)
        self.set_composition_mode(saved_state.mode)
        self.set_transform(saved_state.transform)
        self.set_image(saved_state.image)
        self.set_alpha_locked(saved_state.alpha_locked)
        self.set_locked(saved_state.locked)

    # INTERNAL:

    def _validate_bounds(self, bounds_rect: QRect):
        assert_type(bounds_rect, QRect)
        if not self.bounds.contains(bounds_rect):
            raise ValueError(f'{bounds_rect} not within {self.bounds}')


class ImageLayerState:
    """Preserves a copy of an image layer's state."""

    def __init__(self, name: str, visible: bool, opacity: float, mode: QPainter.CompositionMode,
                 transform: QTransform, image: QImage, locked: bool, alpha_locked: bool) -> None:
        self.name = name
        self.visible = visible
        self.opacity = opacity
        self.mode = mode
        self.transform = transform
        self.image = image
        self.locked = locked
        self.alpha_locked = alpha_locked
