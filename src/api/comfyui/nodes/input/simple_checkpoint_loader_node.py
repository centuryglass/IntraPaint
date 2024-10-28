"""A ComfyUI node used to load a basic Stable-Diffusion model."""
from typing import TypedDict, cast, Any

from src.api.comfyui.nodes.comfy_node import ComfyNode

NODE_NAME = 'CheckpointLoaderSimple'


class SimpleCheckpointInputs(TypedDict):
    """Stable-Diffusion model loader inputs."""
    ckpt_name: str


class SimpleCheckpointLoaderNode(ComfyNode):
    """Loads a Stable-Diffusion model."""

    # Output indexes
    IDX_MODEL = 0
    IDX_CLIP = 1
    IDX_VAE = 2

    def __init__(self, model_name: str) -> None:
        data: SimpleCheckpointInputs = {'ckpt_name': model_name}
        super().__init__(NODE_NAME, cast(dict[str, Any], data), set(), 3)
