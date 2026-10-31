"""Base class for layers that render their image from source data and refuse pixel edits until converted.

A subclass supplies `get_qimage()`. Every destructive operation (merging, cropping, filtering, clearing, resizing the
canvas) asks the user to convert such a layer to an `ImageLayer` first; see `confirm_or_cancel_render_to_image`.
"""
from typing import Optional

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from src.image.layers.image_layer import ImageLayer
from src.image.layers.transform_layer import TransformLayer
from src.image.ora_extensions import OraWriteContext
from src.ui.modal.modal_utils import request_confirmation

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'image.layers.non_destructive_layer'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


CONFIRM_SINGLE_CONVERT_TO_IMAGE_TITLE = _tr('Convert layer to image?')
CONFIRM_SINGLE_CONVERT_TO_IMAGE_MESSAGE = _tr('Attempted action: <b>{action_name}</b>. To complete this action,'
                                              ' layer "{layer_name}" must be converted to an image layer, and you will'
                                              ' no longer be able to edit its original content. Continue?')

CONFIRM_MULTI_CONVERT_TO_IMAGE_TITLE = _tr('Convert layers to image?')
CONFIRM_MULTI_CONVERT_TO_IMAGE_MESSAGE = _tr('Attempted action: <b>{action_name}</b>. To complete this action,'
                                             ' {num_layers} layers must be converted to image layers, and you will'
                                             ' no longer be able to edit their original content. Continue?')


class NonDestructiveLayer(TransformLayer):
    """A layer whose image is rendered on demand from source data.

    Subclasses implement `get_qimage()`, `copy()`, `save_state()` and `restore_state()`. Pixel edits raise
    `RuntimeError`; callers convert with `ImageStack.replace_layer_with_image` after
    `confirm_or_cancel_render_to_image`.
    """

    @staticmethod
    def confirm_or_cancel_render_to_image(layer_names: list[str], action_name: str) -> bool:
        """Request confirmation before converting non-destructive layers to image layers, returning the choice."""
        assert len(layer_names) > 0
        if len(layer_names) == 1:
            title = CONFIRM_SINGLE_CONVERT_TO_IMAGE_TITLE
            message = CONFIRM_SINGLE_CONVERT_TO_IMAGE_MESSAGE.format(action_name=action_name,
                                                                     layer_name=layer_names[0])
        else:
            title = CONFIRM_MULTI_CONVERT_TO_IMAGE_TITLE
            message = CONFIRM_MULTI_CONVERT_TO_IMAGE_MESSAGE.format(action_name=action_name,
                                                                    num_layers=len(layer_names))
        return request_confirmation(None, title, message, discards_work=True)

    def set_qimage(self, image: QImage) -> None:
        """Raises RuntimeError: pixel data can't be applied until the layer is converted to an image layer."""
        raise RuntimeError(f'Tried to apply image data to a {type(self).__name__}, must convert to image layer first')

    def cut_masked(self, image_mask: QImage) -> None:
        """Raises RuntimeError: pixel data can't be cut until the layer is converted to an image layer."""
        raise RuntimeError(f'Tried to cut image data from a {type(self).__name__}, must convert to image layer first')

    def copy_as_image_layer(self) -> ImageLayer:
        """Creates a copy of this layer, rendered as an image layer."""
        layer = ImageLayer(self.get_qimage(), self.name)
        layer.set_opacity(self.opacity)
        layer.set_visible(self.visible)
        layer.set_composition_mode(self.composition_mode)
        layer.set_transform(self.transform)
        return layer

    def ora_extension_data(self, context: OraWriteContext) -> dict[str, str]:  # pylint: disable=unused-argument
        """Returns the attributes this layer adds to its `extended_data.xml` entry when saved to .ora.

        The layer's PNG and `stack.xml` entry are written as for an image layer, so other editors show the rendered
        layer. Keys must not collide with the attributes `open_raster` writes itself. Files go through
        `context.write_file`. A matching loader is registered with `ora_extensions.register_layer_loader`; without
        one, the layer loads as an image layer. The default saves nothing extra.
        """
        return {}
