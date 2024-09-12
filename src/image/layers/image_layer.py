"""Manages an edited image layer."""
from collections.abc import Generator
from contextlib import contextmanager
from typing import Optional, Any, Tuple

import numpy as np
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRect, QSize, QPoint, Signal, QObject
from PySide6.QtGui import QImage, QPainter, QPixmap, QTransform

from src.image.composite_mode import CompositeMode
from src.image.layers.transform_layer import TransformLayer
from src.ui.modal.modal_utils import show_error_dialog
from src.undo_stack import UndoStack
from src.util.visual.image_utils import image_content_bounds, create_transparent_image, image_data_as_numpy_8bit, \
    numpy_intersect, numpy_bounds_index

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'image.layers.image_layer'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


CROP_TO_CONTENT_ERROR_TITLE = _tr('Layer cropping failed')
CROP_TO_CONTENT_ERROR_MESSAGE_EMPTY = _tr('Layer has no image content.')
CROP_TO_CONTENT_ERROR_MESSAGE_FULL = _tr('Layer is already cropped to fit image content.')


class ImageLayer(TransformLayer):
    """Represents an edited image layer."""

    alpha_lock_changed = Signal(QObject, bool)

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

        UndoStack().commit_action(_update_lock, _undo, 'src.layers.image_layer.alpha_locked')

    @contextmanager
    def with_alpha_lock_disabled(self) -> Generator[None, None, None]:
        """Temporarily disables transparency locking while the context is held."""
        alpha_lock_state = self._alpha_locked
        self._alpha_locked = False
        yield
        self._alpha_locked = alpha_lock_state

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
        assert not self.locked, 'Tried to change image in a locked layer'
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

        UndoStack().commit_action(_update_image, _undo_image, 'Layer.image')

    def set_image(self, new_image: QImage, offset: Optional[QPoint] = None) -> None:
        """Updates the layer image."""
        assert self.locked is not True, 'Tried to change image in a locked layer'
        assert not new_image.isNull()
        size_changed = new_image.size() != self._size
        send_size_change_signal = size_changed and not self._size.isNull()
        if size_changed:
            new_size = new_image.size()
            self.set_size(new_size, False)
        if offset is not None and not offset.isNull():
            transform = self.transform
            transform.translate(offset.x(), offset.y())
            self.set_transform(transform)
        self.set_qimage(new_image)
        self._pixmap.invalidate()
        self.content_changed.emit(self, self.bounds)
        if send_size_change_signal:
            self.size_changed.emit(self, self.size)

    @contextmanager
    def borrow_image(self, change_bounds: Optional[QRect] = None) -> Generator[Optional[QImage], None, None]:
        """Provides direct access to the image for editing, automatically marking it as changed when complete."""
        assert self.locked is not True, 'Tried to change image in a locked layer'
        if change_bounds is None or change_bounds.isEmpty():
            change_bounds = self.bounds
        if not self.bounds.contains(change_bounds):
            raise ValueError(f'Change bounds {change_bounds} not within layer bounds {self.bounds}')
        initial_image = self.image
        try:
            yield self._image
        finally:
            self.invalidate_pixmap()
            self._handle_content_change(self._image, initial_image, change_bounds)
            if change_bounds is None:
                change_bounds = self.bounds
            initial_bounds_content = initial_image if change_bounds == self.bounds \
                else initial_image.copy(change_bounds)
            updated_content = self._image.copy(change_bounds)

            def _apply_change(content: QImage, bounds: QRect) -> None:
                init_image = QImage(self._image.size(), QImage.Format.Format_ARGB32_Premultiplied)
                np_init_img = numpy_bounds_index(image_data_as_numpy_8bit(init_image), bounds)
                np_layer_image = numpy_bounds_index(image_data_as_numpy_8bit(self._image), bounds)
                np_content = image_data_as_numpy_8bit(content)
                np.copyto(np_init_img, np_layer_image)
                np.copyto(np_layer_image, np_content)
                self.invalidate_pixmap()
                self._handle_content_change(self._image, init_image, bounds)
                self.content_changed.emit(self, bounds)

            def _apply(c: QImage = updated_content, b: QRect = change_bounds) -> None:
                _apply_change(c, b)

            def _undo(c: QImage = initial_bounds_content, b: QRect = change_bounds) -> None:
                _apply_change(c, b)
                self.content_changed.emit(self, change_bounds)

            UndoStack().commit_action(_apply, _undo, 'ImageLayer.borrow_image', skip_initial_call=True)

            self.content_changed.emit(self, change_bounds)

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

            UndoStack().commit_action(_resize, _restore, 'ImageLayer.adjust_local_bounds')
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
            Image data to draw into the layer. If the size of the image doesn't match the size of the
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
        assert isinstance(image_data, QImage)
        assert isinstance(bounds_rect, QRect)
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
            assert QRect(QPoint(), updated_image.size()).contains(bounds_rect), (f'{bounds_rect} not contained within'
                                                                                 f' {updated_image.size()} image')
        elif register_to_undo_history:
            # Used instead of self.image to ensure post-processing is restricted to the change bounds:
            with self.borrow_image(bounds_rect) as layer_image:
                layer_painter = QPainter(layer_image)
                layer_painter.setCompositionMode(composition_mode)
                layer_painter.drawImage(bounds_rect, image_data)
                layer_painter.end()
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
            np_source = image_data_as_numpy_8bit(last_image)
            np_dst = image_data_as_numpy_8bit(image)
            source_intersect, dst_intersect = numpy_intersect(np_source, np_dst)
            if source_intersect is None or dst_intersect is None:
                return
            dst_intersect[:, :, 3] = source_intersect[:, :, 3]

    def crop_to_content(self, show_warnings: bool = True):
        """Crops the layer to remove transparent areas."""
        full_bounds = QRect(QPoint(), self.size)
        cropped_bounds = image_content_bounds(self._image)
        if cropped_bounds.isNull():
            if show_warnings:
                show_error_dialog(None, CROP_TO_CONTENT_ERROR_TITLE, CROP_TO_CONTENT_ERROR_MESSAGE_EMPTY)
        elif cropped_bounds.size() == full_bounds.size():
            if show_warnings:
                show_error_dialog(None, CROP_TO_CONTENT_ERROR_TITLE, CROP_TO_CONTENT_ERROR_MESSAGE_FULL)
        else:
            full_image = self._image.copy()
            cropped_image = full_image.copy(cropped_bounds)
            transform = self.transform
            crop_transform = QTransform(transform)
            crop_transform.translate(float(cropped_bounds.x()), float(cropped_bounds.y()))

            def _do_crop(img=cropped_image, matrix=crop_transform):
                with self.with_alpha_lock_disabled():
                    self.set_image(img)
                    self.set_transform(matrix)

            def _undo_crop(img=full_image, matrix=transform):
                with self.with_alpha_lock_disabled():
                    self.set_image(img)
                    self.set_transform(matrix)

            UndoStack().commit_action(_do_crop, _undo_crop, 'ImageLayer.crop_to_content')

    def cut_masked(self, image_mask: QImage) -> None:
        """Clear the contents of an area in the parent image."""
        layer_image = self.image
        assert image_mask.size() == layer_image.size(), 'Mask should be pre-converted to image size'
        painter = QPainter(layer_image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
        painter.drawImage(self.bounds, image_mask)
        painter.end()
        self.image = layer_image

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
        with self.with_alpha_lock_disabled():
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
        assert isinstance(bounds_rect, QRect)
        if not self.bounds.contains(bounds_rect):
            raise ValueError(f'{bounds_rect} not within {self.bounds}')


class ImageLayerState:
    """Preserves a copy of an image layer's state."""

    def __init__(self, name: str, visible: bool, opacity: float, mode: CompositeMode,
                 transform: QTransform, image: QImage, locked: bool, alpha_locked: bool) -> None:
        self.name = name
        self.visible = visible
        self.opacity = opacity
        self.mode = mode
        self.transform = transform
        self.image = image
        self.locked = locked
        self.alpha_locked = alpha_locked
