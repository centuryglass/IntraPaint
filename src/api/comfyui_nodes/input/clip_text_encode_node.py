"""A ComfyUI node used to encode text using CLIP."""
from typing import TypedDict, NotRequired, cast, Dict, Any

from src.api.comfyui_nodes.comfy_node import NodeConnection, ComfyNode

NODE_NAME = 'CLIPTextEncode'


class ClipTextInputs(TypedDict):
    """CLIP Text input parameter object definition."""
    text: str
    clip:  NotRequired[NodeConnection]


class ClipTextEncodeNode(ComfyNode):
    """A ComfyUI node used to encode text using CLIP."""

    # Connection keys:
    CLIP = 'clip'

    def __init__(self, text: str) -> None:
        data: ClipTextInputs = {
            'text': text
        }
        super().__init__(NODE_NAME, cast(Dict[str, Any], data), {ClipTextEncodeNode.CLIP}, 1)
