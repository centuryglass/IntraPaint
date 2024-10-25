"""A ComfyUI node used to load image mask data."""
from typing import TypedDict, Literal, cast, Dict, Any

from src.api.comfyui_nodes.comfy_node import ComfyNode

NODE_NAME = 'LoadImageMask'


class LoadImageMaskInputs(TypedDict):
    """LoadImageMask input parameters."""
    image: str
    channel: Literal['alpha', 'red', 'green', 'blue']
    upload: Literal['image']


class LoadImageMaskNode(ComfyNode):
    """A ComfyUI node used to load image data."""

    def __init__(self, image_name: str) -> None:
        data: LoadImageMaskInputs = {
            'image': image_name,
            'channel': 'alpha',
            'upload': 'image'
        }
        super().__init__(NODE_NAME, cast(Dict[str, Any], data), set(), 1)
