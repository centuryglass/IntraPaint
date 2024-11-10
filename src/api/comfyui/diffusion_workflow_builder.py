"""Unified class for building text to image, image to image, and inpainting ComfyUI workflows."""
import logging
import re
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from PySide6.QtCore import QSize

from src.api.comfyui.comfyui_types import ImageFileReference
from src.api.comfyui.nodes.clip_skip_node import CLIPSkipNode
from src.api.comfyui.nodes.comfy_node import ComfyNode
from src.api.comfyui.nodes.comfy_node_graph import ComfyNodeGraph
from src.api.comfyui.nodes.controlnet.apply_controlnet_node import ApplyControlNetNode
from src.api.comfyui.nodes.controlnet.dynamic_preprocessor_node import DynamicPreprocessorNode
from src.api.comfyui.nodes.controlnet.load_controlnet_node import LoadControlNetNode
from src.api.comfyui.nodes.inpaint_model_conditioning_node import InpaintModelConditioningNode
from src.api.comfyui.nodes.input.checkpoint_loader_node import CheckpointLoaderNode
from src.api.comfyui.nodes.input.clip_text_encode_node import ClipTextEncodeNode
from src.api.comfyui.nodes.input.empty_latent_image_node import EmptyLatentNode
from src.api.comfyui.nodes.input.load_image_mask_node import LoadImageMaskNode
from src.api.comfyui.nodes.input.load_image_node import LoadImageNode
from src.api.comfyui.nodes.input.simple_checkpoint_loader_node import SimpleCheckpointLoaderNode
from src.api.comfyui.nodes.ksampler_node import KSamplerNode
from src.api.comfyui.nodes.latent_mask_node import LatentMaskNode
from src.api.comfyui.nodes.model_extensions.hypernet_loader_node import HypernetLoaderNode
from src.api.comfyui.nodes.model_extensions.lora_loader_node import LoraLoaderNode
from src.api.comfyui.nodes.repeat_latent_node import RepeatLatentNode
from src.api.comfyui.nodes.save_image_node import SaveImageNode
from src.api.comfyui.nodes.vae.vae_decode_node import VAEDecodeNode
from src.api.comfyui.nodes.vae.vae_decode_tiled_node import VAEDecodeTiledNode
from src.api.comfyui.nodes.vae.vae_encode_node import VAEEncodeNode
from src.api.comfyui.nodes.vae.vae_encode_tiled_node import VAEEncodeTiledNode
from src.api.comfyui.workflow_builder_utils import random_seed, image_ref_to_str
from src.api.controlnet.controlnet_constants import CONTROLNET_MODEL_NONE, PREPROCESSOR_NONE
from src.api.controlnet.controlnet_preprocessor import ControlNetPreprocessor
from src.config.cache import Cache
from src.ui.window.extra_network_window import LORA_KEY_PATH
from src.util.shared_constants import EDIT_MODE_TXT2IMG

logger = logging.getLogger(__name__)
DEFAULT_STEP_COUNT = 30
DEFAULT_CFG = 8.0
DEFAULT_SIZE = 512
DEFAULT_SAMPLER = 'euler'
DEFAULT_SCHEDULER = 'normal'
MAX_BATCH_SIZE = 64


class ExtensionModelType(Enum):
    """Distinguishes between the two types of accepted extension model."""
    LORA = 0
    HYPERNETWORK = 1


@dataclass
class ControlNetUnitData:
    """All nodes associated with a single ControlNet input."""
    model_node: Optional[LoadControlNetNode]
    preprocessor_node: Optional[DynamicPreprocessorNode]
    control_apply_node: ApplyControlNetNode
    preprocessor: Optional[ControlNetPreprocessor]
    control_image: str


class DiffusionWorkflowBuilder:
    """Unified class for building text to image, image to image, and inpainting ComfyUI workflows."""

    def __init__(self) -> None:
        self._batch_size = 1
        self._prompt = ''
        self._negative = ''
        self._steps = DEFAULT_STEP_COUNT
        self._cfg_scale = DEFAULT_CFG
        self._size = QSize(DEFAULT_SIZE, DEFAULT_SIZE)
        self._sd_model = ''
        self._denoising = 1.0
        self._sampler: str = DEFAULT_SAMPLER
        self._scheduler: str = DEFAULT_SCHEDULER
        self._seed = random_seed()
        self._filename_prefix = ''

        # Optional params that can be set to alter diffusion behavior:
        self._load_as_inpainting_model = False
        self._clip_skip = 1
        self._vae_tiling = False
        self._vae_tile_size = DEFAULT_SIZE
        self._model_config: Optional[str] = None
        self._source_image: Optional[str] = None
        self._mask: Optional[str] = None

        # model_name, model_strength, clip_strength, model_type
        self._extension_model_nodes: list[LoraLoaderNode | HypernetLoaderNode] = []

        self._controlnet_units: list[ControlNetUnitData] = []

        # TODO: not yet supported:
        # self._is_inpainting_model = False

    @property
    def batch_size(self) -> int:
        """Access the number of images to generate in the diffusion batch."""
        return self._batch_size

    @batch_size.setter
    def batch_size(self, size: int) -> None:
        if size < 1 or size > MAX_BATCH_SIZE:
            raise ValueError(f'Batch size {size} not in range 1-{MAX_BATCH_SIZE}')
        self._batch_size = size

    @property
    def cfg_scale(self) -> float:
        """Accesses the prompt adherence scale value."""
        return self._cfg_scale

    @cfg_scale.setter
    def cfg_scale(self, cfg_scale: float) -> None:
        if cfg_scale < 0.0:
            raise ValueError('cfg_scale must be positive.')
        self._cfg_scale = cfg_scale

    @property
    def clip_skip(self) -> int:
        """Accesses the 'CLIP skip' value: the image generation step (counting from the last step backwards) where the
           CLIP model is disabled."""
        return self._clip_skip

    @clip_skip.setter
    def clip_skip(self, clip_skip: int) -> None:
        self._clip_skip = clip_skip

    @property
    def denoising_strength(self) -> float:
        """Accesses the denoising fraction (0.0 to 1.0). Should only be set below 1.0 when using a source image."""
        return self._denoising

    @denoising_strength.setter
    def denoising_strength(self, denoising: float) -> None:
        if denoising < 0.0 or denoising > 1.0:
            raise ValueError(f'Denoising strength {denoising} out of range 0.0-1.0')
        self._denoising = denoising

    @property
    def sd_model(self) -> str:
        """Accesses the Stable Diffusion model used for image generation."""
        return self._sd_model

    @sd_model.setter
    def sd_model(self, model: str) -> None:
        self._sd_model = model

    @property
    def load_as_inpainting_model(self) -> bool:
        """Accesses whether the workflow should be configured for a dedicated inpainting model."""
        return self._load_as_inpainting_model

    @load_as_inpainting_model.setter
    def load_as_inpainting_model(self, is_inpainting_model: bool) -> None:
        self._load_as_inpainting_model = is_inpainting_model

    @property
    def model_config_path(self) -> Optional[str]:
        """Accesses the config path used for advanced model loading."""
        return self._model_config

    @model_config_path.setter
    def model_config_path(self, path: Optional[str]) -> None:
        self._model_config = path

    @property
    def prompt(self) -> str:
        """Accesses the prompt used to guide image generation."""
        return self._prompt

    @prompt.setter
    def prompt(self, prompt: str) -> None:
        self._prompt = prompt

    @property
    def negative_prompt(self) -> str:
        """Accesses the negative prompt used to guide image generation."""
        return self._negative

    @negative_prompt.setter
    def negative_prompt(self, prompt: str) -> None:
        self._negative = prompt

    @property
    def sampler(self) -> str:
        """Accesses the sampling algorithm used for the diffusion process."""
        return self._sampler

    @sampler.setter
    def sampler(self, sampler: str) -> None:
        self._sampler = sampler

    @property
    def scheduler(self) -> str:
        """Accesses the scheduler used to control the magnitude of individual diffusion steps."""
        return self._scheduler

    @scheduler.setter
    def scheduler(self, scheduler: str) -> None:
        self._scheduler = scheduler

    @property
    def seed(self) -> int:
        """Accesses the seed used to control diffusion randomization.  Setting any value less than zero selects a new
           random seed."""
        return self._seed

    @seed.setter
    def seed(self, seed: int) -> None:
        if seed < 0:
            seed = random_seed()
        self._seed = seed

    @property
    def steps(self) -> int:
        """Accesses the number of diffusion steps to take."""
        return self._steps

    @steps.setter
    def steps(self, steps: int) -> None:
        if steps < 1:
            raise ValueError('Step count must be 1 or greater.')
        self._steps = steps

    @property
    def source_image(self) -> Optional[str]:
        """Accesses the initial image to use as initial latent data. If None, empty latent data is used.  Otherwise,
           this needs to be an image that was already uploaded to ComfyUI."""
        return self._source_image

    @source_image.setter
    def source_image(self, source_image: Optional[str]) -> None:
        self._source_image = source_image

    def set_source_image_from_reference(self, source_image: ImageFileReference) -> None:
        """Converts a ComfyUI API image reference to an appropriate string format and assigns it to source_image."""
        self.source_image = image_ref_to_str(source_image)

    @property
    def mask(self) -> Optional[str]:
        """Accesses the inpainting mask to apply to the source image.  If None, no mask is used. Otherwise, this needs
           to be a mask that was already uploaded to ComfyUI, and source_image should be set to the matching image
           specified when the mask was uploaded."""
        return self._mask

    @mask.setter
    def mask(self, mask: Optional[str]) -> None:
        self._mask = mask

    def set_mask_from_reference(self, mask_reference: ImageFileReference) -> None:
        """Converts a ComfyUI API image reference to an appropriate string format and assigns it to the mask."""
        self.mask = image_ref_to_str(mask_reference)

    @property
    def image_size(self) -> QSize:
        """Accesses the generated image size.  If a source image is provided, this is ignored."""
        return self._size

    @image_size.setter
    def image_size(self, size: QSize) -> None:
        self._size = QSize(size)

    @property
    def filename_prefix(self) -> str:
        """Accesses the prefix used when saving image files."""
        return self._filename_prefix

    @filename_prefix.setter
    def filename_prefix(self, prefix: str) -> None:
        self._filename_prefix = prefix

    @property
    def vae_tiling_enabled(self) -> bool:
        """Accesses whether tiled VAE encoding/decoding will be used."""
        return self._vae_tiling

    @vae_tiling_enabled.setter
    def vae_tiling_enabled(self, use_tiling: bool) -> None:
        self._vae_tiling = use_tiling

    @property
    def vae_tile_size(self) -> int:
        """Accesses the VAE tile resolution used if VAE tiling is enabled."""
        return self._vae_tile_size

    @vae_tile_size.setter
    def vae_tile_size(self, tile_size: int) -> None:
        self._vae_tile_size = tile_size

    def add_extension_model(self, model_name: str, model_strength: float, clip_strength: float,
                            model_type: ExtensionModelType) -> None:
        """Adds a LoRA or Hypernetwork model to the workflow. Models are applied in the order that they're added."""
        if model_type == ExtensionModelType.LORA:
            self._extension_model_nodes.append(LoraLoaderNode(model_name, model_strength, clip_strength))
        else:
            self._extension_model_nodes.append(HypernetLoaderNode(model_name, model_strength))

    @property
    def extension_model_nodes(self) -> list[LoraLoaderNode | HypernetLoaderNode]:
        """Returns the list of extension model nodes, in the order that they should be applied."""
        return [*self._extension_model_nodes]

    @property
    def controlnet_unit_nodes(self) -> list[ControlNetUnitData]:
        """Returns the list of ControlNet unit nodes, with associated data."""
        return [*self._controlnet_units]

    def add_controlnet_unit(self, model_name: str, preprocessor: ControlNetPreprocessor,
                            control_image_ref: ImageFileReference,
                            strength: float, start_step: float, end_step: float) -> None:
        """Adds a new ControlNet unit to the workflow."""
        control_image_str = image_ref_to_str(control_image_ref)

        model_node: Optional[LoadControlNetNode] = None
        preprocessor_node: Optional[DynamicPreprocessorNode] = None

        # Check for and reuse identical preprocessor nodes or control models:
        for control_unit_data in self._controlnet_units:
            if control_unit_data.preprocessor == preprocessor \
                    and control_unit_data.control_image == control_image_str:
                preprocessor_node = control_unit_data.preprocessor_node
            if control_unit_data.model_node is not None and control_unit_data.model_node.model_name == model_name:
                model_node = control_unit_data.model_node
        if model_node is None and model_name != CONTROLNET_MODEL_NONE:
            model_node = LoadControlNetNode(model_name)
        if preprocessor_node is None and preprocessor.name != PREPROCESSOR_NONE:
            control_inputs = {}
            for parameter in preprocessor.parameters:
                control_inputs[parameter.key] = parameter.value
            preprocessor_node = DynamicPreprocessorNode(preprocessor.name, control_inputs, preprocessor.has_image_input,
                                                        preprocessor.has_mask_input)
        control_apply_node = ApplyControlNetNode(strength, start_step, end_step)
        new_control_unit = ControlNetUnitData(model_node, preprocessor_node, control_apply_node, preprocessor,
                                              control_image_str)
        self._controlnet_units.append(new_control_unit)

    def build_workflow(self) -> ComfyNodeGraph:
        """Use the provided parameters to build a complete workflow graph."""
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

        if self.clip_skip > 1:
            clip_skip_node = CLIPSkipNode(self.clip_skip)
            workflow.connect_nodes(clip_skip_node, CLIPSkipNode.CLIP,
                                   clip_model_node, clip_out_index)
            clip_model_node = clip_skip_node
            clip_out_index = CLIPSkipNode.IDX_CLIP

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

        # Load image source:
        mask_load_node: Optional[LoadImageMaskNode] = None
        if self.mask is not None:
            mask_load_node = LoadImageMaskNode(self.mask)

        if self.source_image is None:
            image_loading_node: Optional[LoadImageNode] = None
            latent_source_node: ComfyNode = EmptyLatentNode(self.batch_size, self.image_size)
            latent_out_idx = EmptyLatentNode.IDX_LATENT
        else:
            image_loading_node = LoadImageNode(self.source_image)

            if mask_load_node is not None and self.load_as_inpainting_model:
                inpaint_conditioning_node = InpaintModelConditioningNode()
                workflow.connect_nodes(inpaint_conditioning_node, InpaintModelConditioningNode.POSITIVE,
                                       positive_node, positive_out_idx)
                workflow.connect_nodes(inpaint_conditioning_node, InpaintModelConditioningNode.NEGATIVE,
                                       negative_node, negative_out_idx)
                workflow.connect_nodes(inpaint_conditioning_node, InpaintModelConditioningNode.VAE,
                                       vae_model_node, vae_out_index)
                workflow.connect_nodes(inpaint_conditioning_node, InpaintModelConditioningNode.PIXELS,
                                       image_loading_node, LoadImageNode.IDX_IMAGE)
                workflow.connect_nodes(inpaint_conditioning_node, InpaintModelConditioningNode.MASK,
                                       mask_load_node, LoadImageMaskNode.IDX_MASK)
                positive_node = inpaint_conditioning_node
                positive_out_idx = InpaintModelConditioningNode.IDX_POSITIVE
                negative_node = inpaint_conditioning_node
                negative_out_idx = InpaintModelConditioningNode.IDX_NEGATIVE
                latent_source_node = inpaint_conditioning_node
                latent_out_idx = InpaintModelConditioningNode.IDX_LATENT
            else:
                if self.vae_tiling_enabled:
                    latent_image_node: ComfyNode = VAEEncodeTiledNode(self._vae_tile_size)
                    workflow.connect_nodes(latent_image_node, VAEEncodeTiledNode.PIXELS,
                                           image_loading_node, LoadImageNode.IDX_IMAGE)
                    workflow.connect_nodes(latent_image_node, VAEEncodeTiledNode.VAE,
                                           vae_model_node, vae_out_index)
                    latent_out_idx = VAEEncodeTiledNode.IDX_LATENT
                else:
                    latent_image_node = VAEEncodeNode()
                    workflow.connect_nodes(latent_image_node, VAEEncodeNode.PIXELS,
                                           image_loading_node, LoadImageNode.IDX_IMAGE)
                    workflow.connect_nodes(latent_image_node, VAEEncodeNode.VAE,
                                           vae_model_node, vae_out_index)
                    latent_out_idx = VAEEncodeNode.IDX_LATENT

                latent_source_node = RepeatLatentNode(self.batch_size)
                if mask_load_node is not None:
                    mask_apply_node = LatentMaskNode()
                    workflow.connect_nodes(mask_apply_node, LatentMaskNode.SAMPLES,
                                           latent_image_node, latent_out_idx)
                    workflow.connect_nodes(mask_apply_node, LatentMaskNode.MASK,
                                           mask_load_node, LoadImageMaskNode.IDX_MASK)
                    workflow.connect_nodes(latent_source_node, RepeatLatentNode.SAMPLES,
                                           mask_apply_node, LatentMaskNode.IDX_LATENT)
                else:
                    workflow.connect_nodes(latent_source_node, RepeatLatentNode.SAMPLES,
                                           latent_image_node, latent_out_idx)
                latent_out_idx = RepeatLatentNode.IDX_LATENT

        # Load ControlNet Units:
        loaded_images: dict[str, LoadImageNode] = {}
        if image_loading_node is not None:
            assert self.source_image is not None
            loaded_images[self.source_image] = image_loading_node
        for controlnet_unit in self._controlnet_units:
            control_img_str = controlnet_unit.control_image
            if control_img_str in loaded_images:
                control_image_node = loaded_images[control_img_str]
            else:
                control_image_node = LoadImageNode(control_img_str)
                loaded_images[control_img_str] = control_image_node
            if controlnet_unit.preprocessor_node is not None:
                if controlnet_unit.preprocessor_node.has_image_input:
                    workflow.connect_nodes(controlnet_unit.preprocessor_node, DynamicPreprocessorNode.IMAGE,
                                           control_image_node, LoadImageNode.IDX_IMAGE)
                if controlnet_unit.preprocessor_node.has_mask_input and mask_load_node is not None:
                    workflow.connect_nodes(controlnet_unit.preprocessor_node, DynamicPreprocessorNode.MASK,
                                           mask_load_node, LoadImageMaskNode.IDX_MASK)
            control_apply_node = controlnet_unit.control_apply_node
            workflow.connect_nodes(control_apply_node, ApplyControlNetNode.POSITIVE,
                                   positive_node, positive_out_idx)
            workflow.connect_nodes(control_apply_node, ApplyControlNetNode.NEGATIVE,
                                   negative_node, negative_out_idx)
            if controlnet_unit.model_node is not None:
                workflow.connect_nodes(control_apply_node, ApplyControlNetNode.CONTROLNET,
                                       controlnet_unit.model_node, LoadControlNetNode.IDX_CONTROLNET)
            if controlnet_unit.preprocessor_node is not None:
                workflow.connect_nodes(control_apply_node, ApplyControlNetNode.IMAGE,
                                       controlnet_unit.preprocessor_node, DynamicPreprocessorNode.IDX_IMAGE)
            elif control_image_node is not None:
                workflow.connect_nodes(control_apply_node, ApplyControlNetNode.IMAGE,
                                       control_image_node, LoadImageNode.IDX_IMAGE)
            workflow.connect_nodes(control_apply_node, ApplyControlNetNode.VAE,
                                   vae_model_node, vae_out_index)
            positive_node = control_apply_node
            positive_out_idx = ApplyControlNetNode.IDX_POSITIVE
            negative_node = control_apply_node
            negative_out_idx = ApplyControlNetNode.IDX_NEGATIVE

        # Core diffusion process in KSamplerNode:
        sampling_node = KSamplerNode(self.cfg_scale, self.steps, self.sampler, self.denoising_strength, self.scheduler,
                                     self.seed)
        workflow.connect_nodes(sampling_node, KSamplerNode.MODEL,
                               sd_model_node, model_out_index)
        workflow.connect_nodes(sampling_node, KSamplerNode.POSITIVE,
                               positive_node, positive_out_idx)
        workflow.connect_nodes(sampling_node, KSamplerNode.NEGATIVE,
                               negative_node, negative_out_idx)
        workflow.connect_nodes(sampling_node, KSamplerNode.LATENT_IMAGE,
                               latent_source_node, latent_out_idx)

        # Decode and save images:
        if self.vae_tiling_enabled:
            latent_decode_node: ComfyNode = VAEDecodeTiledNode(self._vae_tile_size)
            workflow.connect_nodes(latent_decode_node, VAEDecodeTiledNode.VAE,
                                   vae_model_node, vae_out_index)
            workflow.connect_nodes(latent_decode_node, VAEDecodeTiledNode.SAMPLES,
                                   sampling_node, KSamplerNode.IDX_LATENT)
        else:
            latent_decode_node = VAEDecodeNode()
            workflow.connect_nodes(latent_decode_node, VAEDecodeNode.VAE,
                                   vae_model_node, vae_out_index)
            workflow.connect_nodes(latent_decode_node, VAEDecodeNode.SAMPLES,
                                   sampling_node, KSamplerNode.IDX_LATENT)

        save_image_node = SaveImageNode(self.filename_prefix)
        workflow.connect_nodes(save_image_node, SaveImageNode.IMAGES,
                               latent_decode_node, VAEDecodeNode.IDX_IMAGE)
        # Changes to the returned graph shouldn't affect the workflow builder, so create a deep copy to return:
        final_workflow = deepcopy(workflow)

        # Before returning the copy, clear all connections in saved nodes to prevent potential issues if the workflow
        # is built more than once:
        for node in self._extension_model_nodes:
            node.clear_connections()
        for controlnet_unit in self._controlnet_units:
            if controlnet_unit.preprocessor_node is not None:
                controlnet_unit.preprocessor_node.clear_connections()
            if controlnet_unit.model_node is not None:
                controlnet_unit.model_node.clear_connections()
            controlnet_unit.control_apply_node.clear_connections()
        return final_workflow

    def load_cached_settings(self) -> None:
        """Loads and applies cached parameters."""
        cache = Cache()
        self.sd_model = cache.get(Cache.SD_MODEL)
        self.batch_size = cache.get(Cache.BATCH_SIZE)
        self.prompt = cache.get(Cache.PROMPT)
        self.negative_prompt = cache.get(Cache.NEGATIVE_PROMPT)
        self.steps = cache.get(Cache.SAMPLING_STEPS)
        self.cfg_scale = cache.get(Cache.GUIDANCE_SCALE)
        self.image_size = cache.get(Cache.GENERATION_SIZE)
        sampler = cache.get(Cache.SAMPLING_METHOD)
        if sampler != '':
            self.sampler = sampler
        scheduler = cache.get(Cache.SCHEDULER)
        if scheduler != '':
            self.scheduler = scheduler
        seed = int(cache.get(Cache.SEED))
        if seed < 0:
            seed = random_seed()
        self.seed = seed

        self.load_as_inpainting_model = cache.get(Cache.COMFYUI_INPAINTING_MODEL)
        self.vae_tiling_enabled = cache.get(Cache.COMFYUI_TILED_VAE)
        self.vae_tile_size = cache.get(Cache.COMFYUI_TILED_VAE_TILE_SIZE)
        self.clip_skip = cache.get(Cache.CLIP_SKIP)

        # Find and add LoRA and Hypernetwork models:
        available_loras = [lora[LORA_KEY_PATH] for lora in cache.get(Cache.LORA_MODELS)]
        available_hypernetworks = cache.get(Cache.HYPERNETWORK_MODELS)
        lora_name_map: dict[str, str] = {}
        hypernet_name_map: dict[str, str] = {}
        for model_list, model_dict in ((available_loras, lora_name_map),
                                       (available_hypernetworks, hypernet_name_map)):
            for model_option in model_list:
                if '.' in model_option:
                    model_dict[model_option[:model_option.rindex('.')]] = model_option
                model_dict[model_option] = model_option

        extension_model_pattern = r'<(lora|lyco|hypernet):([^:><]+):([^:>]+)(?::([^>]+))?>'
        for prompt, strength_multiplier in ((self.prompt, 1.0),
                                            (self.negative_prompt, -1.0)):
            extension_model_matches = list(re.finditer(extension_model_pattern, prompt))

            for match in extension_model_matches:
                model_type_name = match.group(1)
                model_type = ExtensionModelType.HYPERNETWORK if model_type_name == 'hypernet' \
                    else ExtensionModelType.LORA
                model_name = match.group(2)
                model_option_dict = hypernet_name_map if model_type == ExtensionModelType.HYPERNETWORK \
                    else lora_name_map
                if model_name not in model_option_dict:
                    logger.error(f'Extension model {model_name} specified, but not found')
                    continue
                model_name = model_option_dict[model_name]
                model_strength_str = match.group(3)
                clip_strength_str = match.group(4) if match.group(4) is not None else model_strength_str
                try:
                    model_strength = float(model_strength_str) * strength_multiplier
                    clip_strength = float(clip_strength_str) * strength_multiplier
                    self.add_extension_model(model_name, model_strength, clip_strength, model_type)
                except ValueError:
                    logger.error(f'Invalid strength value "{model_strength_str}" for lora "{model_name}"')

            # remove the lora/hypernetwork syntax from the prompt now that the models are selected:
            if strength_multiplier > 0:
                self.prompt = re.sub(extension_model_pattern, '', prompt)
            else:
                self.negative_prompt = re.sub(extension_model_pattern, '', prompt)

            edit_mode = cache.get(Cache.EDIT_MODE)
            if edit_mode != EDIT_MODE_TXT2IMG:
                self.denoising_strength = cache.get(Cache.DENOISING_STRENGTH)

            cached_config = cache.get(Cache.COMFYUI_MODEL_CONFIG)
            if cached_config != '':
                self.model_config_path = cached_config
