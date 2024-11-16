"""A ComfyUI node used to apply an upscaling model."""
from typing import TypedDict, NotRequired

from src.api.comfyui.nodes.comfy_node import NodeConnection, ComfyNode

NODE_NAME = 'ImageUpscaleWithModel'


class ImageUpscaleInputs(TypedDict):
    """Upscaling parameters."""
    upscale_model: NotRequired[NodeConnection]
    image: NotRequired[NodeConnection]


class ApplyUpscalerNode(ComfyNode):
    """A ComfyUI node used to apply an upscaling model."""

    # Connection keys:
    UPSCALE_MODEL = 'upscale_model'
    IMAGE = 'image'

    # Output indexes:
    IDX_IMAGE = 0

    def __init__(self) -> None:
        connection_params = {ApplyUpscalerNode.UPSCALE_MODEL, ApplyUpscalerNode.IMAGE}
        super().__init__(NODE_NAME, {}, connection_params, 1)
