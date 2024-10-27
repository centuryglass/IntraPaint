"""A ComfyUI node used to save image data."""
from typing import TypedDict, NotRequired, cast, Dict, Any

from src.api.comfyui.nodes.comfy_node import NodeConnection, ComfyNode

NODE_NAME = 'SaveImage'


class SaveImageInputs(TypedDict):
    """SaveImage input parameters."""
    filename_prefix: str
    images: NotRequired[NodeConnection]  # Image source, e.g. VAE decoder


class SaveImageNode(ComfyNode):
    """A ComfyUI node used to save image data."""

    # Connection keys:
    IMAGES = 'images'

    def __init__(self, filename_prefix: str) -> None:
        data: SaveImageInputs = {
            'filename_prefix': filename_prefix
        }
        super().__init__(NODE_NAME, cast(Dict[str, Any], data), {SaveImageNode.IMAGES}, 0)
