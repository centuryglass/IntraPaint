"""A ComfyUI node used to scale an image using a basic pixel scaling algorithm."""
from typing import TypedDict, NotRequired, Literal, cast

from src.api.comfyui.nodes.comfy_node import NodeConnection, ComfyNode

NODE_NAME = 'ImageScaleBy'

UPSCALE_METHODS = {'nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'}
DEFAULT_UPSCALE_METHOD = 'lanczos'


class ScaleNodeInputs(TypedDict):
    """Scaling parameters."""
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos']
    scale_by: float
    image: NotRequired[NodeConnection]


class BasicScalingNode(ComfyNode):
    """A ComfyUI node used to scale an image using a basic pixel scaling algorithm."""

    # Connection keys:
    IMAGE = 'image'

    # Output indexes:
    IDX_IMAGE = 0

    def __init__(self, scale_by: float, upscale_method=DEFAULT_UPSCALE_METHOD) -> None:
        connection_params = {BasicScalingNode.IMAGE}
        data: ScaleNodeInputs = {
            'upscale_method': upscale_method,  # type: ignore
            'scale_by': scale_by
        }
        super().__init__(NODE_NAME, cast(dict[str, str], data), connection_params, 1)
