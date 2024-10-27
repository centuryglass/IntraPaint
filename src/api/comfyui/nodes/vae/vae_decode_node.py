"""A ComfyUI node used to decode latent image data."""
from typing import TypedDict, NotRequired

from src.api.comfyui.nodes.comfy_node import NodeConnection, ComfyNode

NODE_NAME = 'VAEDecode'


class VAEDecodeInputs(TypedDict):
    """Latent image decoding input parameter object definition."""
    samples: NotRequired[NodeConnection]  # Latent image data, e.g. from KSampler.
    vae: NotRequired[NodeConnection]  # VAE model used for decoding. May be baked-in to a regular SD model.


class VAEDecodeNode(ComfyNode):
    """A ComfyUI node used to decode latent image data."""

    # Connection keys:
    SAMPLES = 'samples'
    VAE = 'vae'

    # Output indexes:
    IDX_IMAGE = 0

    def __init__(self) -> None:
        connection_params = {
            VAEDecodeNode.SAMPLES,
            VAEDecodeNode.VAE
        }
        super().__init__(NODE_NAME, {}, connection_params, 1)
