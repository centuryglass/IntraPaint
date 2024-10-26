"""A ComfyUI node used to load a LORA extension model.
"""
from typing import TypedDict, NotRequired

from src.api.comfyui_nodes.comfy_node import NodeConnection, ComfyNode

NODE_NAME = 'LoraLoader'


class LoraLoaderInputs(TypedDict):
    """Inputs for LORA model loading."""
    lora_name: str
    strength_model: float
    strength_clip: float
    model: NotRequired[NodeConnection]
    clip: NotRequired[NodeConnection]


class LoraLoaderNode(ComfyNode):
    """A ComfyUI node used to load a LORA extension model."""

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
        super().__init__(NODE_NAME, data, connection_params, 2)
