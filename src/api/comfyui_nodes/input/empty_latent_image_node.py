"""A ComfyUI node used to initialize a batch of latent images."""
from typing import TypedDict, cast, Dict, Any

from PySide6.QtCore import QSize

from src.api.comfyui_nodes.comfy_node import ComfyNode

NODE_NAME = 'EmptyLatentImage'


class EmptyLatentInputs(TypedDict):
    """Empty latent image loader inputs."""
    batch_size: int
    height: int
    width: int


class EmptyLatentNode(ComfyNode):
    """Creates an empty latent image or image batch."""

    def __init__(self, batch_size: int, image_size: QSize) -> None:
        data: EmptyLatentInputs = {
            'batch_size': batch_size,
            'height': image_size.height(),
            'width': image_size.width()
        }
        super().__init__(NODE_NAME, cast(Dict[str, Any], data), set(), 1)
