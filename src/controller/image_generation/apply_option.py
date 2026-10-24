"""Writes a generated image option into the image stack. Shared by every route that applies an option.

The function raises no dialogs, so callers decide how to tell the user about a blocked layer.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from PIL import Image
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QImage, QPainter

from src.config.application_config import AppConfig
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.util.shared_constants import EDIT_MODE_INPAINT
from src.util.visual.pil_image_utils import pil_image_to_qimage


class ApplyResult(Enum):
    """Whether an option reached the requested layer, and if not, why."""
    APPLIED = 'applied'
    BLOCKED_NOT_IMAGE_LAYER = 'not_image_layer'
    BLOCKED_LOCKED = 'locked'
    BLOCKED_HIDDEN = 'hidden'


@dataclass(frozen=True)
class ApplyOutcome:
    """Result of `apply_generated_image`. `layer` is the layer the content was written to, which is a new layer when
    `result` is not `APPLIED`."""
    result: ApplyResult
    layer: Layer


def blocking_result(layer: Layer) -> ApplyResult:
    """Returns the reason generated content can't be written to `layer`, or `APPLIED` if it can."""
    if not isinstance(layer, ImageLayer):
        return ApplyResult.BLOCKED_NOT_IMAGE_LAYER
    if layer.locked or layer.parent_locked:
        return ApplyResult.BLOCKED_LOCKED
    if not layer.shown:
        return ApplyResult.BLOCKED_HIDDEN
    return ApplyResult.APPLIED


def apply_generated_image(image_stack: ImageStack,
                          option: Image.Image | QImage,
                          layer: Layer,
                          generation_area: QRect,
                          edit_mode: str,
                          mask_image: Optional[QImage],
                          fallback_layer_name: str,
                          clear_context_pins: bool = False) -> ApplyOutcome:
    """Writes `option` into `generation_area` of `layer` as one undoable edit and makes that layer active.

    Parameters
    ----------
    image_stack: ImageStack
        The image being edited.
    option: Image.Image | QImage
        Generated image, scaled to `generation_area` if its size differs.
    layer: Layer
        Requested target. When it is locked, hidden or not an image layer, a new layer named `fallback_layer_name`
        receives the content instead, and the outcome's result says why.
    generation_area: QRect
        The generation area the option was made for. It is restored on the image stack, so applying an old batch
        doesn't write to the current area.
    edit_mode: str
        Untranslated edit mode value, as `Cache.EDIT_MODE` holds it. Only `EDIT_MODE_INPAINT` uses the mask.
    mask_image: QImage | None
        Mask whose alpha clips the option in inpainting mode, or None to apply the option unclipped.
    fallback_layer_name: str
        Name for the layer created when `layer` is blocked.
    clear_context_pins: bool, default=False
        Clears the selection's context pins after the edit when `AppConfig.CLEAR_CONTEXT_PINS_AFTER_GENERATING` is set.
        Callers that apply an option as the final choice pass True. Callers that apply it as a side copy leave it off.
    """
    if isinstance(option, Image.Image):
        image = pil_image_to_qimage(option).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    else:
        image = option.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    if edit_mode == EDIT_MODE_INPAINT and mask_image is not None:
        painter = QPainter(image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(QRect(QPoint(0, 0), image.size()), mask_image)
        painter.end()
    result = blocking_result(layer)
    if result is not ApplyResult.APPLIED:
        layer = image_stack.create_layer(layer_name=fallback_layer_name)
    image_stack.generation_area = generation_area
    image_stack.set_generation_area_content(image, layer)
    if image_stack.active_layer != layer:
        image_stack.active_layer = layer
    if clear_context_pins and AppConfig().get(AppConfig.CLEAR_CONTEXT_PINS_AFTER_GENERATING):
        image_stack.selection_layer.clear_context_pins()
    return ApplyOutcome(result, layer)
