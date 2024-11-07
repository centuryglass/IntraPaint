"""Creates a ComfyUI workflow used to apply an upscaling model."""
from typing import Optional

from src.api.comfyui.comfyui_types import ImageFileReference
from src.api.comfyui.nodes.apply_upscaler_node import ApplyUpscalerNode
from src.api.comfyui.nodes.comfy_node_graph import ComfyNodeGraph
from src.api.comfyui.nodes.input.load_image_node import LoadImageNode
from src.api.comfyui.nodes.input.load_upscaler_node import LoadUpscalerNode
from src.api.comfyui.nodes.save_image_node import SaveImageNode
from src.api.comfyui.workflow_builder_utils import image_ref_to_str


def build_basic_upscaling_workflow(source_image: Optional[ImageFileReference],
                                   upscale_model_name: str) -> ComfyNodeGraph:
    """Creates a ComfyUI workflow used to apply an upscaling model."""
    workflow = ComfyNodeGraph()
    load_image_node = LoadImageNode(image_ref_to_str(source_image))
    load_upscaler_node = LoadUpscalerNode(upscale_model_name)
    apply_upscaler_node = ApplyUpscalerNode()
    workflow.connect_nodes(apply_upscaler_node, ApplyUpscalerNode.UPSCALE_MODEL,
                           load_upscaler_node, LoadUpscalerNode.IDX_UPSCALE_MODEL)
    workflow.connect_nodes(apply_upscaler_node, ApplyUpscalerNode.IMAGE,
                           load_image_node, LoadImageNode.IDX_IMAGE)
    save_image_node = SaveImageNode('')
    workflow.connect_nodes(save_image_node, SaveImageNode.IMAGES,
                           apply_upscaler_node, ApplyUpscalerNode.IDX_IMAGE)
    return workflow
