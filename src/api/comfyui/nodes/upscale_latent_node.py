"""A ComfyUI node used to scale a latent image to an arbitrary resolution."""
from typing import TypedDict, NotRequired, Literal, cast

from src.api.comfyui.nodes.comfy_node import NodeConnection, ComfyNode

NODE_NAME = 'LatentUpscale'


class UpscaleLatentInputs(TypedDict):
    """Scaling parameters."""
    samples: NotRequired[NodeConnection]
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'bislerp']
    width: int
    height: int
    crop: Literal['disabled', 'center']


DEFAULT_UPSCALE_METHOD = 'nearest-exact'


class UpscaleLatentNode(ComfyNode):
    """A ComfyUI node used to scale a latent image using a basic pixel scaling algorithm."""

    # Connection keys:
    SAMPLES = 'samples'

    # Output indexes:
    IDX_LATENT = 0

    def __init__(self, width: int, height: int, upscale_method=DEFAULT_UPSCALE_METHOD) -> None:
        connection_params = {UpscaleLatentNode.SAMPLES}
        data: UpscaleLatentInputs = {
            'upscale_method': upscale_method,  # type: ignore
            'width': width,
            'height': height,
            'crop': 'disabled'
        }
        super().__init__(NODE_NAME, cast(dict[str, str], data), connection_params, 1)
