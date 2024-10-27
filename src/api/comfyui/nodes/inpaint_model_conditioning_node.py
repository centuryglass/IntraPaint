"""A ComfyUI node used to adjust conditioning for a dedicated inpainting model.

Output slots are [positive_conditioning, negative_conditioning, latent_image]
"""
from typing import TypedDict, NotRequired

from src.api.comfyui.nodes.comfy_node import NodeConnection, ComfyNode

NODE_NAME = 'InpaintModelConditioning'


class InpaintModelConditioningInputs(TypedDict):
    """Inputs for adjusting conditioning for an inpainting model."""
    positive: NotRequired[NodeConnection]  # Usually CLIPTextEncode
    negative: NotRequired[NodeConnection]  # Usually CLIPTextEncode
    vae: NotRequired[NodeConnection]  # VAE model used for encoding. May be baked-in to a regular SD model.
    pixels: NotRequired[NodeConnection]  # raw image data, e.g. from LoadImage.
    mask: NotRequired[NodeConnection]  # Inpainting mask.


class InpaintModelConditioningNode(ComfyNode):
    """A ComfyUI node used to adjust conditioning for a dedicated inpainting model."""

    # Connection keys:
    POSITIVE = 'positive'
    NEGATIVE = 'negative'
    VAE = 'vae'
    PIXELS = 'pixels'
    MASK = 'mask'

    # Output indexes
    IDX_POSITIVE = 0
    IDX_NEGATIVE = 1
    IDX_LATENT = 2

    def __init__(self) -> None:
        connection_params = {
            InpaintModelConditioningNode.POSITIVE,
            InpaintModelConditioningNode.NEGATIVE,
            InpaintModelConditioningNode.VAE,
            InpaintModelConditioningNode.PIXELS,
            InpaintModelConditioningNode.MASK
        }
        super().__init__(NODE_NAME, {}, connection_params, 3)
