"""Represents a layer in the image holding text data."""
from typing import Any, List, Optional

from PySide6.QtCore import Signal, QPoint, QPointF
from PySide6.QtGui import QImage, QPainter, QTransform
from PySide6.QtWidgets import QApplication

from src.image.layers.image_layer import ImageLayer
from src.image.layers.transform_layer import TransformLayer
from src.image.text_rect import TextRect
from src.ui.modal.modal_utils import request_confirmation
from src.undo_stack import UndoStack
from src.util.cached_data import CachedData
from src.util.geometry_utils import extract_transform_parameters, combine_transform_parameters

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'image.layers.text_layer'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


CONFIRM_SINGLE_CONVERT_TO_IMAGE_TITLE = _tr('Convert text layer to image?')
CONFIRM_SINGLE_CONVERT_TO_IMAGE_MESSAGE = _tr('Attempted action: {action_name]. To complete this action,'
                                              ' layer "{layer_name}" must be converted to an image layer, and you will'
                                              ' no longer be able to edit it with the text tool. Continue?')

CONFIRM_MULTI_CONVERT_TO_IMAGE_TITLE = _tr('Convert text layers to image?')
CONFIRM_MULTI_CONVERT_TO_IMAGE_MESSAGE = _tr('Attempted action: {action_name]. To complete this action,'
                                              '{num_text_layers} text layers must be converted to image'
                                             ' layers, and you will no longer be able to edit them with the text tool.'
                                             ' Continue?')

MAX_NAME_LENGTH_BEFORE_TRUNC = 10


class TextLayer(TransformLayer):
    """Represents a layer in the image holding text data."""

    text_data_changed = Signal(TextRect)

    def __init__(self, text_rect: Optional[TextRect]):
        """
        Initializes a new layer with text data.

        Parameters
        ----------
        text_rect: TextRect, optional
            New text rendering data.
        """
        super().__init__(self._get_name_from_text(text_rect))
        self._text_rect = text_rect if text_rect is not None else TextRect()
        self._image_cache = CachedData(self._text_rect.render_to_image())
        self.set_size(text_rect.size)

    @staticmethod
    def confirm_or_cancel_render_to_image(layer_names: List[str], action_name: str) -> bool:
        """Request confirmation before converting text layers to image, returning the user's choice."""
        assert len(layer_names) > 0
        if len(layer_names) == 1:
            title = CONFIRM_SINGLE_CONVERT_TO_IMAGE_TITLE
            message = CONFIRM_SINGLE_CONVERT_TO_IMAGE_MESSAGE.format(action_name=action_name,
                                                                     layer_name=layer_names[0])
        else:
            title = CONFIRM_MULTI_CONVERT_TO_IMAGE_TITLE
            message = CONFIRM_MULTI_CONVERT_TO_IMAGE_MESSAGE.format(action_name=action_name,
                                                                    num_text_layers=len(layer_names))
        return request_confirmation(None, title, message)

    @property
    def offset(self) -> QPointF:
        """Access the offset component of the layer transformation."""
        x_off, y_off, _, _, _ = extract_transform_parameters(self.transform)
        return QPointF(x_off, y_off)

    @offset.setter
    def offset(self, new_offset: QPoint | QPointF) -> None:
        _, _, x_scale, y_scale, angle = extract_transform_parameters(self.transform)
        self.transform = combine_transform_parameters(new_offset.x(), new_offset.y(), x_scale, y_scale, angle)

    @property
    def text_rect(self) -> TextRect:
        """Returns text and text placement data for the layer."""
        return TextRect(self._text_rect)

    @text_rect.setter
    def text_rect(self, new_text: TextRect) -> None:
        """Updates the layer text content, adding the change to the undo history."""
        if self._text_rect != new_text:
            self._apply_combinable_change(new_text, self._text_rect, self.set_text_rect,
                                          'text_layer.text_rect')

    def get_qimage(self) -> QImage:
        """Return layer image data as an ARGB32 formatted QImage."""
        if self._image_cache.valid:
            return self._image_cache.data

        image = self._text_rect.render_to_image()
        self._image_cache.data = image
        return image

    def set_text_rect(self, new_text: TextRect) -> None:
        """Updates the layer text content without adding the change to the undo history."""
        if self._text_rect != new_text:
            new_text = TextRect(new_text)
            self._text_rect = new_text
            self._image_cache.invalidate()
            self.invalidate_pixmap()
            self.set_name(self._get_name_from_text())
            self.set_size(new_text.size)
            self.content_changed.emit(self)
            self.text_data_changed.emit(new_text)

    def set_qimage(self, image: QImage) -> None:
        """Throw an error when attempting to directly set this layer's image data."""
        raise RuntimeError('Tried to apply image data to a text layer, must convert to image layer first')

    # LAYER/IMAGE FUNCTIONS:

    def copy(self) -> 'TextLayer':
        """Creates a copy of this layer."""
        layer = TextLayer(self._text_rect)
        layer.set_opacity(self.opacity)
        layer.set_visible(self.visible)
        layer.set_composition_mode(self.composition_mode)
        layer.set_transform(super()._get_transform())
        return layer

    def copy_as_image_layer(self) -> ImageLayer:
        """Creates a copy of this layer, rendered as an image layer."""
        layer = ImageLayer(self.get_qimage(), self.name + ' copy')
        layer.set_opacity(self.opacity)
        layer.set_visible(self.visible)
        layer.set_composition_mode(self.composition_mode)
        layer.set_transform(self.transform)
        return layer

    def replace_with_image_layer(self) -> ImageLayer:
        """Replace this layer within its parent with an equivalent image layer, returning the replacement."""
        parent = self.layer_parent
        assert parent is not None

        image_layer = self.copy_as_image_layer()
        text_layer = self

        def _swap_in_image_layer():
            layer_index = parent.get_layer_index(text_layer)
            assert layer_index > 0
            parent.remove_layer(text_layer)
            parent.insert_layer(image_layer, layer_index)

        def _swap_back():
            layer_index = parent.get_layer_index(image_layer)
            assert layer_index > 0
            parent.remove_layer(image_layer)
            parent.insert_layer(text_layer, layer_index)

        UndoStack().commit_action(_swap_in_image_layer, _swap_back, 'TextLayer.replace_with_image_layer')
        return image_layer

    def cut_masked(self, image_mask: QImage) -> None:
        """Throw an error when attempting to cut mask content from a text layer."""
        raise RuntimeError('Tried to apply image data to a text layer, must convert to image layer first')

    def save_state(self) -> Any:
        """Export the current layer state, so it can be restored later."""
        return TextLayerState(self.name,
                               self.visible,
                               self.opacity,
                               self.composition_mode,
                               super()._get_transform(),
                               self.locked,
                               self.text_rect)

    def restore_state(self, saved_state: Any) -> None:
        """Restore the layer state from a previous saved state."""
        assert isinstance(saved_state, TextLayerState)
        self.set_name(saved_state.name)
        self.set_visible(saved_state.visible)
        self.set_opacity(saved_state.opacity)
        self.set_composition_mode(saved_state.mode)
        self.set_transform(saved_state.transform)
        self.set_text_rect(saved_state.text_rect)
        self.set_locked(saved_state.locked)

    # INTERNAL:

    def _get_name_from_text(self, text_rect: Optional[TextRect] = None) -> str:
        if not hasattr(self, '_text_rect'):
            name = '' if text_rect is None else text_rect.text
        else:
            name = self._text_rect.text if text_rect is None else text_rect.text
        if len(name) > MAX_NAME_LENGTH_BEFORE_TRUNC:
            name = f'{name[MAX_NAME_LENGTH_BEFORE_TRUNC:]}...'
        return f'"{name}"'


class TextLayerState:
    """Preserves a copy of a text layer's state."""

    def __init__(self, name: str, visible: bool, opacity: float, mode: QPainter.CompositionMode,
                 transform: QTransform, locked: bool, text_rect: TextRect) -> None:
        self.name = name
        self.visible = visible
        self.opacity = opacity
        self.mode = mode
        self.transform = transform
        self.locked = locked
        self.text_rect = text_rect
