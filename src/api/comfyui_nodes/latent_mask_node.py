"""A ComfyUI node used to apply a mask to latent image data."""
from typing import TypedDict, NotRequired

from src.api.comfyui_nodes.comfy_node import NodeConnection, ComfyNode

NODE_NAME = 'SetLatentNoiseMask'


class LatentMaskInputs(TypedDict):
    """Latent image mask application parameters."""
    samples: NotRequired[NodeConnection]  # latent image data, e.g. from VAEEncodeNode.
    mask: NotRequired[NodeConnection]  # mask data, e.g. from LoadImageMask.


class LatentMaskNode(ComfyNode):
    """A ComfyUI node used to apply a mask to latent image data."""

    # Connection keys:
    SAMPLES = 'samples'
    MASK = 'mask'

    def __init__(self) -> None:
        connection_params = {LatentMaskNode.SAMPLES, LatentMaskNode.MASK}
        super().__init__(NODE_NAME, {}, connection_params, 1)
