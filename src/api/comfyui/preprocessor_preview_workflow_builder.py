"""Creates a minimal ComfyUI workflow used to preview a ControlNet preprocessor."""
from typing import Optional

from src.api.comfyui.comfyui_types import ImageFileReference
from src.api.comfyui.nodes.comfy_node_graph import ComfyNodeGraph
from src.api.comfyui.nodes.controlnet.dynamic_preprocessor_node import DynamicPreprocessorNode
from src.api.comfyui.nodes.input.load_image_mask_node import LoadImageMaskNode
from src.api.comfyui.nodes.input.load_image_node import LoadImageNode
from src.api.comfyui.nodes.save_image_node import SaveImageNode
from src.api.comfyui.workflow_builder_utils import image_ref_to_str
from src.api.controlnet.controlnet_preprocessor import ControlNetPreprocessor


class PreprocessorPreviewWorkflowBuilder:
    """Unified class for building text to image, image to image, and inpainting ComfyUI workflows."""

    def __init__(self, preprocessor: ControlNetPreprocessor) -> None:
        self._preprocessor = preprocessor
        control_inputs = {}
        for parameter in preprocessor.parameters:
            control_inputs[parameter.key] = parameter.value
        self._preprocessor_node = DynamicPreprocessorNode(preprocessor.name, control_inputs,
                                                          preprocessor.has_image_input,
                                                          preprocessor.has_mask_input)

    def build_workflow(self, source_image: Optional[ImageFileReference],
                       mask: Optional[ImageFileReference] = None) -> ComfyNodeGraph:
        """Use the provided parameters to build a complete workflow graph."""
        workflow = ComfyNodeGraph()

        if self._preprocessor_node.has_image_input:
            assert source_image is not None
            load_image_node = LoadImageNode(image_ref_to_str(source_image))
            workflow.connect_nodes(self._preprocessor_node, DynamicPreprocessorNode.IMAGE,
                                   load_image_node, LoadImageNode.IDX_IMAGE)
        if mask is not None and self._preprocessor_node.has_mask_input:
            mask_node = LoadImageMaskNode(image_ref_to_str(mask))
            workflow.connect_nodes(self._preprocessor_node, DynamicPreprocessorNode.MASK,
                                   mask_node, LoadImageMaskNode.IDX_MASK)

        # Save preview image:
        filename_prefix = f'{self._preprocessor.name}_preview'
        save_image_node = SaveImageNode(filename_prefix)
        workflow.connect_nodes(save_image_node, SaveImageNode.IMAGES,
                               self._preprocessor_node, DynamicPreprocessorNode.IDX_IMAGE)
        return workflow
