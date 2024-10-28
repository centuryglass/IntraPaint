"""A ComfyUI node used to pre-process image data for ControlNet. Rather than a specific node type, this class can
   stand in for nearly any preprocessor node type, as long as it only has one input connection (type IMAGE) and one
   output connection (also type IMAGE)."""
from typing import Any

from src.api.comfyui.nodes.comfy_node import ComfyNode


class DynamicPreprocessorNode(ComfyNode):
    """A ComfyUI node used to pre-process image data for ControlNet. Rather than a specific node type, this class can
   stand in for nearly any preprocessor node type, as long as it only has one input connection (type IMAGE) and one
   output connection (also type IMAGE)."""

    # Connection keys:
    IMAGE = 'image'

    # Output indexes:
    IDX_IMAGE = 0

    def __init__(self, node_name: str, node_inputs: dict[str, Any]) -> None:
        super().__init__(node_name, node_inputs, {DynamicPreprocessorNode.IMAGE}, 1)
