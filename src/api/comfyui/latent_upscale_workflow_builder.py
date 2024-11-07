"""Creates a ComfyUI workflow for tiled latent upscaling, using the Ultimate SD Upscale script, the ControlNet tile
   model, and a secondary upscaling model when possible."""
from copy import deepcopy
from typing import Optional

from PySide6.QtCore import QSize

from src.api.comfyui.comfyui_types import ImageFileReference
from src.api.comfyui.diffusion_workflow_builder import DiffusionWorkflowBuilder
from src.api.comfyui.nodes.basic_scaling_node import BasicScalingNode
from src.api.comfyui.nodes.comfy_node import ComfyNode
from src.api.comfyui.nodes.comfy_node_graph import ComfyNodeGraph
from src.api.comfyui.nodes.controlnet.apply_controlnet_node import ApplyControlNetNode
from src.api.comfyui.nodes.controlnet.dynamic_preprocessor_node import DynamicPreprocessorNode
from src.api.comfyui.nodes.controlnet.load_controlnet_node import LoadControlNetNode
from src.api.comfyui.nodes.input.checkpoint_loader_node import CheckpointLoaderNode
from src.api.comfyui.nodes.input.clip_text_encode_node import ClipTextEncodeNode
from src.api.comfyui.nodes.input.load_image_node import LoadImageNode
from src.api.comfyui.nodes.input.load_upscaler_node import LoadUpscalerNode
from src.api.comfyui.nodes.input.simple_checkpoint_loader_node import SimpleCheckpointLoaderNode
from src.api.comfyui.nodes.ksampler_node import KSamplerNode
from src.api.comfyui.nodes.model_extensions.hypernet_loader_node import HypernetLoaderNode
from src.api.comfyui.nodes.model_extensions.lora_loader_node import LoraLoaderNode
from src.api.comfyui.nodes.save_image_node import SaveImageNode
from src.api.comfyui.nodes.ultimate_upscale_node import UltimateUpscaleCoreInputs, UltimateUpscaleNode
from src.api.comfyui.nodes.upscale_latent_node import UpscaleLatentNode
from src.api.comfyui.nodes.vae.vae_decode_tiled_node import VAEDecodeTiledNode
from src.api.comfyui.nodes.vae.vae_encode_tiled_node import TILE_MIN, TILE_STEP, TILE_MAX, VAEEncodeTiledNode
from src.api.comfyui.workflow_builder_utils import image_ref_to_str
from src.api.controlnet.controlnet_preprocessor import ControlNetPreprocessor

DEFAULT_UPSCALE_PARAMS: UltimateUpscaleCoreInputs = {
    'seed': 0,
    'steps': 20,
    'cfg': 8.0,
    'sampler_name': 'euler',
    'scheduler': 'normal',
    'denoise': 0.35,
    'mode_type': 'Linear',
    'tile_width': 512,
    'tile_height': 512,
    'mask_blur': 8,
    'tile_padding': 32,
    'force_uniform_tiles': False,
    'tiled_decode': True
}

# If there's no ultimate sd upscale script and no ControlNet tile model, denoising shouldn't exceed this value:
MINIMAL_MODE_DENOISING_LIMIT = 0.2


class LatentUpscaleWorkflowBuilder(DiffusionWorkflowBuilder):
    """Creates a ComfyUI workflow for tiled latent upscaling, using the Ultimate SD Upscale script, the ControlNet tile
       model, and a secondary upscaling model when possible."""

    def __init__(self,
                 source_image: ImageFileReference,
                 upscale_by: float,
                 final_image_size: QSize,
                 tile_size: QSize,
                 ultimate_upscale_script_available: bool,
                 upscale_model: Optional[str] = None,
                 controlnet_tile_preprocessor: Optional[ControlNetPreprocessor] = None,
                 controlnet_tile_model: Optional[str] = None) -> None:
        super().__init__()
        self.source_image = image_ref_to_str(source_image)
        self._upscale_multiplier = upscale_by
        self._final_image_size = final_image_size
        self._ultimate_sd_upscale = ultimate_upscale_script_available
        self._upscale_model_name = upscale_model
        self._tile_size = QSize(tile_size)
        if controlnet_tile_preprocessor is not None and controlnet_tile_model is not None:
            self.add_controlnet_unit(controlnet_tile_model, controlnet_tile_preprocessor, source_image, 1.0,
                                     0.0, 1.0)

    @property
    def tile_size(self) -> QSize:
        """Access the tile size used for latent upscaling."""
        return self._tile_size

    @tile_size.setter
    def tile_size(self, size: QSize) -> None:
        self._tile_size = QSize(size)

    def build_workflow(self) -> ComfyNodeGraph:
        """Use the provided parameters to build a complete workflow graph."""
        # TODO: lots of code duplication here, and no opportunity to specify particular values for a lot of the
        #       upscaler options.  Both of those things should be fixed.
        workflow = ComfyNodeGraph()

        # Load model(s):
        if self.model_config_path is None:
            model_loading_node: ComfyNode = SimpleCheckpointLoaderNode(self.sd_model)
            model_out_index = SimpleCheckpointLoaderNode.IDX_MODEL
            vae_out_index = SimpleCheckpointLoaderNode.IDX_VAE
            clip_out_index = SimpleCheckpointLoaderNode.IDX_CLIP
        else:
            model_loading_node = CheckpointLoaderNode(self.sd_model, self.model_config_path)
            model_out_index = CheckpointLoaderNode.IDX_MODEL
            vae_out_index = CheckpointLoaderNode.IDX_VAE
            clip_out_index = CheckpointLoaderNode.IDX_CLIP
        sd_model_node = model_loading_node
        vae_model_node = model_loading_node
        clip_model_node = model_loading_node

        for extension_node in self._extension_model_nodes:
            if isinstance(extension_node, LoraLoaderNode):
                workflow.connect_nodes(extension_node, LoraLoaderNode.CLIP,
                                       clip_model_node, clip_out_index)
                workflow.connect_nodes(extension_node, LoraLoaderNode.MODEL,
                                       sd_model_node, model_out_index)
                clip_model_node = extension_node
                clip_out_index = LoraLoaderNode.IDX_CLIP
                sd_model_node = extension_node
                model_out_index = LoraLoaderNode.IDX_MODEL
            else:
                assert isinstance(extension_node, HypernetLoaderNode)
                workflow.connect_nodes(extension_node, HypernetLoaderNode.MODEL,
                                       sd_model_node, model_out_index)
                sd_model_node = extension_node
                model_out_index = HypernetLoaderNode.IDX_MODEL

        # Load starting image:
        image_node = LoadImageNode(self.source_image)
        image_out_index = LoadImageNode.IDX_IMAGE

        # Load prompt conditioning:
        prompt_node = ClipTextEncodeNode(self.prompt)
        negative_prompt_node = ClipTextEncodeNode(self.negative_prompt)
        for text_encoding_node in (prompt_node, negative_prompt_node):
            workflow.connect_nodes(text_encoding_node, ClipTextEncodeNode.CLIP,
                                   clip_model_node, clip_out_index)
        positive_node: ComfyNode = prompt_node
        positive_out_idx = ClipTextEncodeNode.IDX_CONDITIONING
        negative_node: ComfyNode = negative_prompt_node
        negative_out_idx = ClipTextEncodeNode.IDX_CONDITIONING

        # Load tile ControlNet unit, if available:
        controlnet_units = self.controlnet_unit_nodes
        assert len(controlnet_units) <= 1, f'Expected at most one controlNet unit, found {len(controlnet_units)}'
        if len(controlnet_units) > 0:
            tile_control_unit = controlnet_units[0]
            tile_preprocessor_node = tile_control_unit.preprocessor_node
            tile_model_node = tile_control_unit.model_node
            tile_control_apply_node = tile_control_unit.control_apply_node
            assert tile_preprocessor_node is not None
            assert tile_preprocessor_node.has_image_input
            assert tile_model_node is not None

            workflow.connect_nodes(tile_preprocessor_node, DynamicPreprocessorNode.IMAGE,
                                   image_node, image_out_index)

            workflow.connect_nodes(tile_control_apply_node, ApplyControlNetNode.IMAGE,
                                   tile_preprocessor_node, DynamicPreprocessorNode.IDX_IMAGE)
            workflow.connect_nodes(tile_control_apply_node, ApplyControlNetNode.CONTROLNET,
                                   tile_model_node, LoadControlNetNode.IDX_CONTROLNET)
            workflow.connect_nodes(tile_control_apply_node, ApplyControlNetNode.VAE,
                                   vae_model_node, vae_out_index)
            workflow.connect_nodes(tile_control_apply_node, ApplyControlNetNode.POSITIVE,
                                   positive_node, positive_out_idx)
            workflow.connect_nodes(tile_control_apply_node, ApplyControlNetNode.NEGATIVE,
                                   negative_node, negative_out_idx)
            positive_node = tile_control_apply_node
            positive_out_idx = ApplyControlNetNode.IDX_POSITIVE
            negative_node = tile_control_apply_node
            negative_out_idx = ApplyControlNetNode.IDX_NEGATIVE

        # Load upscale model node, if available:
        upscale_model_node: Optional[LoadUpscalerNode] = None
        if self._upscale_model_name is not None and self._upscale_model_name != '':
            upscale_model_node = LoadUpscalerNode(self._upscale_model_name)
        elif self._ultimate_sd_upscale:
            # Use a basic scaling node to get the image to the right size instead.  If we're not using the
            # "Ultimate SD Upscale" script this can be skipped, since we'll end up using latent image scaling anyway.
            basic_scaling_node = BasicScalingNode(self._upscale_multiplier)
            workflow.connect_nodes(basic_scaling_node, BasicScalingNode.IMAGE,
                                   image_node, image_out_index)
            image_node = basic_scaling_node
            image_out_index = BasicScalingNode.IDX_IMAGE

        # Set up ultimate upscale script, if available:
        if self._ultimate_sd_upscale:
            upscale_node_params = deepcopy(DEFAULT_UPSCALE_PARAMS)
            upscale_node_params['seed'] = self.seed
            upscale_node_params['steps'] = self.steps
            upscale_node_params['cfg'] = self.cfg_scale
            upscale_node_params['sampler_name'] = self.sampler
            upscale_node_params['scheduler'] = self.scheduler
            upscale_node_params['denoise'] = self.denoising_strength
            upscale_node_params['tile_width'] = self.tile_size.width()
            upscale_node_params['tile_height'] = self.tile_size.height()
            if upscale_model_node is not None:
                upscale_node_params['upscale_by'] = self._upscale_multiplier
            assert upscale_node_params['tile_width'] == 640

            ultimate_upscale_node = UltimateUpscaleNode(upscale_node_params, upscale_model_node is not None)
            workflow.connect_nodes(ultimate_upscale_node, UltimateUpscaleNode.IMAGE,
                                   image_node, image_out_index)
            workflow.connect_nodes(ultimate_upscale_node, UltimateUpscaleNode.MODEL,
                                   sd_model_node, model_out_index)
            workflow.connect_nodes(ultimate_upscale_node, UltimateUpscaleNode.POSITIVE,
                                   positive_node, positive_out_idx)
            workflow.connect_nodes(ultimate_upscale_node, UltimateUpscaleNode.NEGATIVE,
                                   negative_node, negative_out_idx)
            workflow.connect_nodes(ultimate_upscale_node, UltimateUpscaleNode.VAE,
                                   vae_model_node, vae_out_index)
            if upscale_model_node is not None:
                workflow.connect_nodes(ultimate_upscale_node, UltimateUpscaleNode.UPSCALE_MODEL,
                                       upscale_model_node, LoadUpscalerNode.IDX_UPSCALE_MODEL)
            image_node = ultimate_upscale_node
            image_out_index = UltimateUpscaleNode.IDX_IMAGE

        else:  # No ultimate SD upscale, we'll try to get by with img2img with tiled VAE encoding/decoding.
            vae_tile_size = min(self._tile_size.width(), self._tile_size.height())
            vae_tile_size -= (vae_tile_size % TILE_STEP)
            if vae_tile_size < TILE_MIN:
                vae_tile_size = TILE_MIN
            elif vae_tile_size > TILE_MAX:
                vae_tile_size = TILE_MAX
            vae_encode_node = VAEEncodeTiledNode(vae_tile_size)
            workflow.connect_nodes(vae_encode_node, VAEEncodeTiledNode.PIXELS,
                                   image_node, image_out_index)
            workflow.connect_nodes(vae_encode_node, VAEEncodeTiledNode.VAE,
                                   vae_model_node, vae_out_index)

            latent_scaling_node = UpscaleLatentNode(self._final_image_size.width(), self._final_image_size.height())
            workflow.connect_nodes(latent_scaling_node, UpscaleLatentNode.SAMPLES,
                                   vae_encode_node, VAEEncodeTiledNode.IDX_LATENT)

            denoising = self.denoising_strength
            if len(controlnet_units) == 0:
                denoising = min(denoising, MINIMAL_MODE_DENOISING_LIMIT)
            sampler_node = KSamplerNode(self.cfg_scale, self.steps, self.sampler, denoising, self.scheduler, self.seed)
            workflow.connect_nodes(sampler_node, KSamplerNode.LATENT_IMAGE,
                                   latent_scaling_node, UpscaleLatentNode.IDX_LATENT)
            workflow.connect_nodes(sampler_node, KSamplerNode.MODEL,
                                   sd_model_node, model_out_index)
            workflow.connect_nodes(sampler_node, KSamplerNode.POSITIVE,
                                   positive_node, positive_out_idx)
            workflow.connect_nodes(sampler_node, KSamplerNode.NEGATIVE,
                                   negative_node, negative_out_idx)

            vae_decode_node = VAEDecodeTiledNode(vae_tile_size)
            workflow.connect_nodes(vae_decode_node, VAEDecodeTiledNode.VAE,
                                   vae_model_node, vae_out_index)
            workflow.connect_nodes(vae_decode_node, VAEDecodeTiledNode.SAMPLES,
                                   sampler_node, KSamplerNode.IDX_LATENT)
            image_node = vae_decode_node
            image_out_index = VAEDecodeTiledNode.IDX_IMAGE

        save_image_node = SaveImageNode(self.filename_prefix)
        workflow.connect_nodes(save_image_node, SaveImageNode.IMAGES,
                               image_node, image_out_index)
        # Changes to the returned graph shouldn't affect the workflow builder, so create a deep copy to return:
        final_workflow = deepcopy(workflow)

        # Before returning the copy, clear all connections in saved nodes to prevent potential issues if the
        # workflow is built more than once:
        for node in self._extension_model_nodes:
            node.clear_connections()
        for controlnet_unit in self._controlnet_units:
            if controlnet_unit.preprocessor_node is not None:
                controlnet_unit.preprocessor_node.clear_connections()
            if controlnet_unit.model_node is not None:
                controlnet_unit.model_node.clear_connections()
            controlnet_unit.control_apply_node.clear_connections()
        return final_workflow
