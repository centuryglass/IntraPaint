"""A ComfyUI node used to apply a ControlNet model to diffusion conditioning data."""
from typing import TypedDict, NotRequired, cast, Any

from src.api.comfyui.nodes.comfy_node import NodeConnection, ComfyNode

NODE_NAME = 'ControlNetApplyAdvanced'

CONTROLNET_COMFTUI_CONTROL_WEIGHT_KEY = 'strength'
CONTROLNET_COMFYUI_START_STEP_KEY = 'start_percent'
CONTROLNET_COMFYUI_END_STEP_KEY = 'end_percent'


class ApplyControlNetInputs(TypedDict):
    """ControlNet loader input parameters."""
    positive: NotRequired[NodeConnection]  # Usually CLIPTextEncode
    negative: NotRequired[NodeConnection]  # Usually CLIPTextEncode
    control_net: NotRequired[NodeConnection]
    image: NotRequired[NodeConnection]
    vae: NotRequired[NodeConnection]
    strength: float
    start_percent: float
    end_percent: float


class ApplyControlNetNode(ComfyNode):
    """A ComfyUI node used to apply a ControlNet model to diffusion conditioning data."""

    # Connection keys:
    POSITIVE = 'positive'
    NEGATIVE = 'negative'
    CONTROLNET = 'control_net'
    IMAGE = 'image'
    VAE = 'vae'

    # Output indexes:
    IDX_POSITIVE = 0
    IDX_NEGATIVE = 1

    def __init__(self, strength: float, start_percent: float, end_percent: float) -> None:
        data: ApplyControlNetInputs = {
            'strength': strength,
            'start_percent': start_percent,
            'end_percent': end_percent
        }
        connections = {
            ApplyControlNetNode.POSITIVE,
            ApplyControlNetNode.NEGATIVE,
            ApplyControlNetNode.CONTROLNET,
            ApplyControlNetNode.IMAGE,
            ApplyControlNetNode.VAE,
        }
        super().__init__(NODE_NAME, cast(dict[str, Any], data), connections, 2)
