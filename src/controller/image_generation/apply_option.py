"""Writes a generated image option into the image stack. Shared by every route that applies an option.

The function raises no dialogs, so callers decide how to tell the user about a blocked layer.

A generated result describes the whole composite in the generation area, so it is only correct as the target layer's
own pixels when the layer renders Normal at full opacity, every group around it passes that through, and no layer above
it draws in the area. `blocking_result` checks this, and a layer that fails goes to a new layer at the top of the stack.
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
from src.image.composite_mode import CompositeMode
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.layers.transform_layer import TransformLayer
from src.util.shared_constants import EDIT_MODE_INPAINT
from src.util.visual.pil_image_utils import pil_image_to_qimage


class ApplyResult(Enum):
    """Whether an option reached the requested layer, and if not, why."""
    APPLIED = 'applied'
    BLOCKED_NOT_IMAGE_LAYER = 'not_image_layer'
    BLOCKED_LOCKED = 'locked'
    BLOCKED_HIDDEN = 'hidden'
    NEEDS_TOP_LAYER_BLENDING = 'blending'
    NEEDS_TOP_LAYER_COVERED = 'covered'


@dataclass(frozen=True)
class ApplyOutcome:
    """Result of `apply_generated_image`. `layer` is the layer the content was written to, which is a new layer when
    `result` is not `APPLIED`."""
    result: ApplyResult
    layer: Layer


def _draws_in_area(layer: Layer, area: QRect) -> bool:
    """Returns whether `layer` is shown and has any non-transparent pixel in `area`, given in image coordinates."""
    if not layer.visible:
        return False
    if isinstance(layer, LayerGroup):
        return any(_draws_in_area(child, area) for child in layer.child_layers)
    if isinstance(layer, TransformLayer):
        area = layer.map_rect_from_image(area).intersected(layer.bounds)
    return not layer.is_empty(area)


def _renders_over_target(layer: Layer, generation_area: QRect) -> Optional[ApplyResult]:
    """Returns `NEEDS_TOP_LAYER_BLENDING` if `layer` or a group around it alters how its pixels combine with the
    content below, `NEEDS_TOP_LAYER_COVERED` if a layer above it draws in `generation_area`, and None otherwise."""
    if layer.composition_mode != CompositeMode.NORMAL or layer.opacity < 1.0:
        return ApplyResult.NEEDS_TOP_LAYER_BLENDING
    covered = False
    child: Layer = layer
    parent = layer.layer_parent
    while isinstance(parent, LayerGroup):
        index = parent.get_layer_index(child)
        if index is not None and any(_draws_in_area(above, generation_area)
                                     for above in parent.child_layers[:index]):
            covered = True
        if parent.layer_parent is not None and (parent.renders_isolated or parent.opacity < 1.0
                                                or parent.composition_mode != CompositeMode.NORMAL):
            return ApplyResult.NEEDS_TOP_LAYER_BLENDING
        child = parent
        parent = parent.layer_parent
    return ApplyResult.NEEDS_TOP_LAYER_COVERED if covered else None


def blocking_result(layer: Layer, generation_area: Optional[QRect] = None) -> ApplyResult:
    """Returns the reason generated content shouldn't be written to `layer`, or `APPLIED` if it can be.

    Locked, hidden and non-image layers can't take it at all. A layer whose blending, opacity, groups or overlying
    layers change how its pixels show can take it but would display the wrong result, so those return a
    `NEEDS_TOP_LAYER_*` reason when `generation_area` is given.
    """
    if not isinstance(layer, ImageLayer):
        return ApplyResult.BLOCKED_NOT_IMAGE_LAYER
    if layer.locked or layer.parent_locked:
        return ApplyResult.BLOCKED_LOCKED
    if not layer.shown:
        return ApplyResult.BLOCKED_HIDDEN
    if generation_area is not None:
        return _renders_over_target(layer, generation_area) or ApplyResult.APPLIED
    return ApplyResult.APPLIED


def create_top_layer(image_stack: ImageStack, name: str) -> ImageLayer:
    """Creates a new layer at the top of the stack, outside every group, where it shows exactly what it holds."""
    return image_stack.create_layer(layer_name=name, layer_parent=image_stack.layer_stack, layer_index=0)


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
        Requested target. When it is locked, hidden or not an image layer, or would not display the content correctly
        (see `blocking_result`), a new top layer named `fallback_layer_name` receives the content instead, and the
        outcome's result says why.
    generation_area: QRect
        The generation area the option was made for. It is restored on the image stack, so applying an old batch
        doesn't write to the current area.
    edit_mode: str
        Untranslated edit mode value, as `Cache.EDIT_MODE` holds it. Only `EDIT_MODE_INPAINT` uses the mask.
    mask_image: QImage | None
        Mask whose alpha clips the option in inpainting mode, or None to apply the option unclipped.
    fallback_layer_name: str
        Name for the layer created when `layer` is blocked or can't display the content.
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
    result = blocking_result(layer, generation_area)
    if result is not ApplyResult.APPLIED:
        layer = create_top_layer(image_stack, fallback_layer_name)
    image_stack.generation_area = generation_area
    image_stack.set_generation_area_content(image, layer)
    if image_stack.active_layer != layer:
        image_stack.active_layer = layer
    if clear_context_pins and AppConfig().get(AppConfig.CLEAR_CONTEXT_PINS_AFTER_GENERATING):
        image_stack.selection_layer.clear_context_pins()
    return ApplyOutcome(result, layer)
