"""A ComfyUI node used to apply the 'CLIP skip' option to prompt conditioning."""
from typing import TypedDict, NotRequired, cast

from src.api.comfyui.nodes.comfy_node import NodeConnection, ComfyNode

NODE_NAME = 'CLIPSetLastLayer'


class CLIPSkipInputs(TypedDict):
    """CLIP skip parameters."""
    clip: NotRequired[NodeConnection]
    stop_at_clip_layer: int


class CLIPSkipNode(ComfyNode):
    """A ComfyUI node used to apply the 'CLIP skip' option to prompt conditioning."""

    # Connection keys:
    CLIP = 'clip'

    # Output indexes:
    IDX_CLIP = 0

    def __init__(self, stop_layer: int) -> None:
        if stop_layer > 0:
            stop_layer *= -1  # CLIP skip is positive elsewhere, but this node expects a negative index.
        connection_params = {CLIPSkipNode.CLIP}
        data: CLIPSkipInputs = {
            'stop_at_clip_layer': stop_layer
        }
        super().__init__(NODE_NAME, cast(dict[str, str], data), connection_params, 1)
