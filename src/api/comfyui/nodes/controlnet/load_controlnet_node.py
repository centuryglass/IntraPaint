"""A ComfyUI node used to load a ControlNet model."""
from typing import TypedDict, cast, Any

from src.api.comfyui.nodes.comfy_node import ComfyNode

NODE_NAME = 'ControlNetLoader'


class LoadControlNetInputs(TypedDict):
    """ControlNet loader input parameters."""
    control_net_name: str  # model name


class LoadControlNetNode(ComfyNode):
    """A ComfyUI node used to load a ControlNet Model"""

    # Output indexes:
    IDX_CONTROLNET = 0

    def __init__(self, model_name: str) -> None:
        data: LoadControlNetInputs = {
            'control_net_name': model_name
        }
        super().__init__(NODE_NAME, cast(dict[str, Any], data), set(), 1)
