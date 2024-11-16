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
    MASK = 'mask'

    # Output indexes:
    IDX_IMAGE = 0

    def __init__(self, node_name: str, node_inputs: dict[str, Any], has_image_input: bool = True,
                 has_mask_input: bool = False) -> None:
        inputs: set[str] = set()
        if has_image_input:
            inputs.add(DynamicPreprocessorNode.IMAGE)
        if has_mask_input:
            inputs.add(DynamicPreprocessorNode.MASK)
        self._has_image_input = has_image_input
        self._has_mask_input = has_mask_input
        super().__init__(node_name, node_inputs, inputs, 1)

    def __deepcopy__(self, memo: dict[int, Any]) -> 'DynamicPreprocessorNode':
        data_dict = self.get_dict()
        node_copy = DynamicPreprocessorNode(data_dict['class_type'], data_dict['inputs'], self.has_image_input,
                                            self.has_mask_input)
        memo[id(self)] = node_copy
        return node_copy

    @property
    def has_image_input(self) -> bool:
        """Returns whether this node requires an image input."""
        return self._has_image_input

    @property
    def has_mask_input(self) -> bool:
        """Returns whether this node requires a mask input."""
        return self._has_mask_input
