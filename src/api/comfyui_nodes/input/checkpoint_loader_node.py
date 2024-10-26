"""A ComfyUI node used to load a Stable-Diffusion model, plus associated CLIP and VAE models.

Outputs are [model, vae, clip]
"""
from typing import TypedDict, cast, Any, Dict

from src.api.comfyui_nodes.comfy_node import ComfyNode

NODE_NAME = 'CheckpointLoader'


class CheckpointInputs(TypedDict):
    """Stable-Diffusion model loader inputs."""
    config_name: str
    ckpt_name: str


class CheckpointLoaderNode(ComfyNode):
    """A ComfyUI node used to load a Stable-Diffusion model, plus associated CLIP and VAE models.

Outputs are [model, vae, clip]
"""

    # Output indexes
    IDX_MODEL = 0
    IDX_CLIP = 1
    IDX_VAE = 2

    def __init__(self, model_name: str, config_name: str) -> None:
        data: CheckpointInputs = {'ckpt_name': model_name, 'config_name': config_name}
        super().__init__(NODE_NAME, cast(Dict[str, Any], data), set(), 3)
