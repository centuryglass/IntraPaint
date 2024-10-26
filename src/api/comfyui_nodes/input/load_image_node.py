"""A ComfyUI node used to load image data."""
from typing import TypedDict, Literal, Dict, cast, Any

from src.api.comfyui_nodes.comfy_node import ComfyNode

NODE_NAME = 'LoadImage'


class LoadImageInputs(TypedDict):
    """LoadImage input parameters."""
    image: str
    upload: Literal['image']


class LoadImageNode(ComfyNode):
    """A ComfyUI node used to load image data."""

    # Output indexes:
    IDX_IMAGE = 0

    def __init__(self, image_name: str) -> None:
        data: LoadImageInputs = {
            'image': image_name,
            'upload': 'image'
        }
        super().__init__(NODE_NAME, cast(Dict[str, Any], data), set(), 1)
