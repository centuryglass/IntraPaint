"""A ComfyUI node used to load a LoRA extension model.
"""
from typing import TypedDict, NotRequired, cast, Any

from src.api.comfyui.nodes.comfy_node import NodeConnection, ComfyNode

NODE_NAME = 'LoraLoader'


class LoraLoaderInputs(TypedDict):
    """Inputs for LoRA model loading."""
    lora_name: str
    strength_model: float
    strength_clip: float
    model: NotRequired[NodeConnection]
    clip: NotRequired[NodeConnection]


class LoraLoaderNode(ComfyNode):
    """A ComfyUI node used to load a LoRA extension model."""

    # Connection keys:
    MODEL = 'model'
    CLIP = 'clip'

    # Output indexes:
    IDX_MODEL = 0
    IDX_CLIP = 1

    def __init__(self, lora_name: str, strength_model: float, strength_clip: float) -> None:
        connection_params = {
            LoraLoaderNode.MODEL,
            LoraLoaderNode.CLIP
        }
        data: LoraLoaderInputs = {
            'lora_name': lora_name,
            'strength_model': strength_model,
            'strength_clip': strength_clip
        }
        super().__init__(NODE_NAME, cast(dict[str, Any], data), connection_params, 2)
