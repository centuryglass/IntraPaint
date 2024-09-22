"""Interface for performing drawing operations on an image layer."""
from typing import Optional

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from src.image.layers.image_layer import ImageLayer
from src.ui.modal.modal_utils import show_error_dialog
from src.util.visual.image_utils import image_is_fully_transparent

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'image.brush.layer_brush'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


ERROR_TITLE_EDIT_FAILED = _tr('Editing failed')
ERROR_MESSAGE_LAYER_LOCKED = _tr('The selected layer is locked, unlock it or select a different layer.')
ERROR_MESSAGE_LAYER_HIDDEN = _tr('The selected layer is hidden, un-hide it before trying to edit it.')
ERROR_MESSAGE_LAYER_NONE = _tr('The selected layer is not an image layer, select an image layer first.')
ERROR_MESSAGE_EMPTY_MASK = _tr('Changes are restricted to selected content only, but nothing is selected in this layer.'
                               ' Select layer content or enable changes in unselected areas.')


class LayerBrush:
    """Draws content to an image layer."""

    def __init__(self, layer: Optional[ImageLayer] = None) -> None:
        self._layer: Optional[ImageLayer] = None
        self._mask: Optional[QImage] = None
        self._eraser = False
        self._color = QColor(0, 0, 0)
        self._brush_size = 1
        self._drawing = False
        if layer is not None:
            self.connect_to_layer(layer)

    def connect_to_layer(self, new_layer: Optional[ImageLayer]):
        """Disconnects from the current layer, and connects to a new one."""
        assert new_layer is None or isinstance(new_layer, ImageLayer)
        if self._drawing:
            self.end_stroke()
        self._layer = new_layer

    @property
    def eraser(self) -> bool:
        """Returns whether the brush is acting as an eraser."""
        return self._eraser

    @eraser.setter
    def eraser(self, should_erase: bool) -> None:
        """Sets whether the active brush should work as an eraser."""
        self._set_is_eraser(should_erase)

    @property
    def brush_size(self) -> int:
        """Gets the current brush size."""
        return self._brush_size

    @brush_size.setter
    def brush_size(self, size: int):
        """Sets the base brush size.

        Parameters
        ----------
        size : int
            Base brush blot diameter in pixels.
        """
        self._set_brush_size(size)

    @property
    def brush_color(self) -> QColor:
        """Returns the current brush color."""
        return self._color

    @brush_color.setter
    def brush_color(self, new_color: QColor) -> None:
        """Updates the active brush color."""
        self._set_brush_color(new_color)

    @property
    def drawing(self) -> bool:
        """Returns whether the stroke is still in-progress."""
        return self._drawing

    @property
    def layer(self) -> Optional[ImageLayer]:
        """Returns the active ImageLayer, or None if no ImageLayer is active."""
        return self._layer

    @property
    def input_mask(self) -> Optional[QImage]:
        """Access the optional input mask image."""
        return self._mask

    def start_stroke(self) -> None:
        """Signals the start of a brush stroke, to be called once whenever user input starts or resumes."""
        if self._layer is None or not self._layer.visible or self._layer.locked:
            return
        if self._drawing:
            self.end_stroke()
        self._drawing = True

    def stroke_to(self, x: float, y: float, pressure: Optional[float], x_tilt: Optional[float],
                  y_tilt: Optional[float]) -> None:
        """Continue a brush stroke with optional tablet inputs."""
        error_message: Optional[str] = None
        if self._layer is None:
            error_message = ERROR_MESSAGE_LAYER_NONE
        elif not self._layer.visible:
            error_message = ERROR_MESSAGE_LAYER_HIDDEN
        elif self._layer.locked:
            error_message = ERROR_MESSAGE_LAYER_LOCKED
        elif self._mask is not None:
            if image_is_fully_transparent(self._mask):
                error_message = ERROR_MESSAGE_EMPTY_MASK
        if error_message is not None:
            show_error_dialog(None, ERROR_TITLE_EDIT_FAILED, error_message)
            return
        if not self._drawing:
            self.start_stroke()
        self._draw(x, y, pressure, x_tilt, y_tilt)

    def end_stroke(self) -> None:
        """Finishes a brush stroke, copying it back to the layer."""
        self._drawing = False

    def set_input_mask(self, mask_image: Optional[QImage]) -> None:
        """Sets a mask image, restricting brush changes to areas covered by non-transparent mask areas"""
        self._mask = mask_image

    def _set_brush_size(self, new_size: int) -> None:
        self._brush_size = new_size

    def _set_brush_color(self, new_color: QColor) -> None:
        """Updates the brush color."""
        self._color = new_color

    def _set_is_eraser(self, should_erase: bool) -> None:
        """Sets whether the active brush should work as an eraser."""
        self._eraser = should_erase

    def _draw(self, x: float, y: float, pressure: Optional[float], x_tilt: Optional[float],
              y_tilt: Optional[float]) -> None:
        """Use active settings to use the brush with the given inputs."""
        raise NotImplementedError()
