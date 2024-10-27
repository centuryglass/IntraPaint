"""A ComfyUI node used to encode latent image data."""
from typing import TypedDict, NotRequired

from src.api.comfyui.nodes.comfy_node import NodeConnection, ComfyNode

NODE_NAME = 'VAEEncode'


class VAEEncodeInputs(TypedDict):
    """Latent image encoding input parameter object definition."""
    pixels: NotRequired[NodeConnection]  # raw image data, e.g. from LoadImage.
    vae: NotRequired[NodeConnection]  # VAE model used for encoding. May be baked-in to a regular SD model.


class VAEEncodeNode(ComfyNode):
    """A ComfyUI node used to encode images into latent image space."""

    # Connection keys:
    PIXELS = 'pixels'
    VAE = 'vae'

    # Output indexes:
    IDX_LATENT = 0

    def __init__(self) -> None:
        connection_params = {
            VAEEncodeNode.PIXELS,
            VAEEncodeNode.VAE
        }
        super().__init__(NODE_NAME, {}, connection_params, 1)
