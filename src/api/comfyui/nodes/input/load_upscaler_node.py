"""A ComfyUI node used to load an image upscaling model."""
from typing import TypedDict, cast, Any

from src.api.comfyui.nodes.comfy_node import ComfyNode

NODE_NAME = 'UpscaleModelLoader'


class LoadUpscalerInputs(TypedDict):
    """Stable-Diffusion model loader inputs."""
    model_name: str


class LoadUpscalerNode(ComfyNode):
    """A ComfyUI node used to load an image upscaling model."""

    # Output indexes
    IDX_UPSCALE_MODEL = 0

    def __init__(self, model_name: str) -> None:
        data: LoadUpscalerInputs = {'model_name': model_name}
        super().__init__(NODE_NAME, cast(dict[str, Any], data), set(), 1)
