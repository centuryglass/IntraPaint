"""Unified class for building text to image, image to image, and inpainting ComfyUI workflows."""
import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional, cast

from PySide6.QtCore import QSize

import src.api.comfyui.comfyui_types as comfy_type
from src.api.comfyui.nodes.comfy_node import ComfyNode
from src.api.comfyui.nodes.comfy_node_graph import ComfyNodeGraph
from src.api.comfyui.nodes.controlnet.apply_controlnet_node import ApplyControlNetNode
from src.api.comfyui.nodes.controlnet.dynamic_preprocessor_node import DynamicPreprocessorNode
from src.api.comfyui.nodes.controlnet.load_controlnet_node import LoadControlNetNode
from src.api.comfyui.nodes.input.checkpoint_loader_node import CheckpointLoaderNode
from src.api.comfyui.nodes.input.clip_text_encode_node import ClipTextEncodeNode
from src.api.comfyui.nodes.input.empty_latent_image_node import EmptyLatentNode
from src.api.comfyui.nodes.input.load_image_mask_node import LoadImageMaskNode
from src.api.comfyui.nodes.input.load_image_node import LoadImageNode
from src.api.comfyui.nodes.input.simple_checkpoint_loader_node import SimpleCheckpointLoaderNode
from src.api.comfyui.nodes.ksampler_node import SAMPLER_OPTIONS, SCHEDULER_OPTIONS, SamplerName, SchedulerName, \
    KSamplerNode
from src.api.comfyui.nodes.latent_mask_node import LatentMaskNode
from src.api.comfyui.nodes.model_extensions.hypernet_loader_node import HypernetLoaderNode
from src.api.comfyui.nodes.model_extensions.lora_loader_node import LoraLoaderNode
from src.api.comfyui.nodes.repeat_latent_node import RepeatLatentNode
from src.api.comfyui.nodes.save_image_node import SaveImageNode
from src.api.comfyui.nodes.vae.vae_decode_node import VAEDecodeNode
from src.api.comfyui.nodes.vae.vae_encode_node import VAEEncodeNode
from src.api.controlnet_constants import CONTROLNET_MODEL_NONE
from src.api.controlnet_preprocessor import ControlNetPreprocessor

random.seed()

DEFAULT_STEP_COUNT = 30
DEFAULT_CFG = 8.0
DEFAULT_SIZE = 512
DEFAULT_SAMPLER = SAMPLER_OPTIONS[0]
DEFAULT_SCHEDULER = SCHEDULER_OPTIONS[0]
MAX_SEED = 0xffffffffffffffff
MAX_BATCH_SIZE = 64


class ExtensionModelType(Enum):
    """Distinguishes between the two types of accepted extension model."""
    LORA = 0
    HYPERNETWORK = 1


@dataclass
class _ControlInfo:
    model_node: Optional[LoadControlNetNode]
    preprocessor_parameters: ControlNetPreprocessor
    preprocessor_node: Optional[DynamicPreprocessorNode]
    control_image: str
    strength: float
    start_step: float
    end_step: float


class DiffusionWorkflowBuilder:
    """Unified class for building text to image, image to image, and inpainting ComfyUI workflows."""

    def __init__(self, sd_model: str) -> None:
        self._batch_size = 1
        self._prompt = ''
        self._negative = ''
        self._steps = DEFAULT_STEP_COUNT
        self._cfg_scale = DEFAULT_CFG
        self._size = QSize(DEFAULT_SIZE, DEFAULT_SIZE)
        self._sd_model = sd_model
        self._denoising = 1.0
        self._sampler: SamplerName = cast(SamplerName, DEFAULT_SAMPLER)
        self._scheduler: SchedulerName = cast(SchedulerName, DEFAULT_SCHEDULER)
        self._seed = random.randrange(0, MAX_SEED)
        self._filename_prefix = ''

        # Optional params that can be set to alter diffusion behavior:
        self._model_config: Optional[str] = None
        self._source_image: Optional[str] = None
        self._mask: Optional[str] = None

        # model_name, model_strength, clip_strength, model_type
        self._extension_models: list[tuple[str, float, float, ExtensionModelType]] = []

        self._controlnet_units: list[_ControlInfo] = []

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
        """Accesses the stable-diffusion model used for image generation."""
        return self._sd_model

    @sd_model.setter
    def sd_model(self, model: str) -> None:
        self._sd_model = model

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
    def sampler(self) -> SamplerName:
        """Accesses the sampling algorithm used for the diffusion process."""
        return self._sampler

    @sampler.setter
    def sampler(self, sampler: SamplerName) -> None:
        self._sampler = sampler

    @property
    def scheduler(self) -> SchedulerName:
        """Accesses the scheduler used to control the magnitude of individual diffusion steps."""
        return self._scheduler

    @scheduler.setter
    def scheduler(self, scheduler: SchedulerName) -> None:
        self._scheduler = scheduler

    @property
    def seed(self) -> int:
        """Accesses the seed used to control diffusion randomization.  Setting any value less than zero selects a new
           random seed."""
        return self._seed

    @seed.setter
    def seed(self, seed: int) -> None:
        if seed < 0:
            seed = random.randrange(0, MAX_SEED)
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

    @staticmethod
    def _image_ref_to_str(source_image: comfy_type.ImageFileReference) -> str:
        if 'subfolder' in source_image and source_image['subfolder'] != '':
            return f'{source_image["subfolder"]}/{source_image["filename"]}'
        return source_image['filename']

    def set_source_image_from_reference(self, source_image: comfy_type.ImageFileReference) -> None:
        """Converts a ComfyUI API image reference to an appropriate string format and assigns it to source_image."""
        self.source_image = self._image_ref_to_str(source_image)

    @property
    def mask(self) -> Optional[str]:
        """Accesses the inpainting mask to apply to the source image.  If None, no mask is used. Otherwise, this needs
           to be a mask that was already uploaded to ComfyUI, and source_image should be set to the matching image
           specified when the mask was uploaded."""
        return self._mask

    @mask.setter
    def mask(self, mask: Optional[str]) -> None:
        self._mask = mask

    def set_mask_from_reference(self, mask_reference: comfy_type.ImageFileReference) -> None:
        """Converts a ComfyUI API image reference to an appropriate string format and assigns it to the mask."""
        self.mask = self._image_ref_to_str(mask_reference)

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

    def add_extension_model(self, model_name: str, model_strength: float, clip_strength: float,
                            model_type: ExtensionModelType) -> None:
        """Adds a LoRA or Hypernetwork model to the workflow. Models are applied in the order that they're added."""
        self._extension_models.append((model_name, model_strength, clip_strength, model_type))

    def add_controlnet_unit(self, model_name: str, preprocessor: ControlNetPreprocessor,
                            control_image_ref: comfy_type.ImageFileReference,
                            strength: float, start_step: float, end_step: float) -> None:
        """Adds a new ControlNet unit to the workflow."""
        control_image_str = self._image_ref_to_str(control_image_ref)

        model_node: Optional[LoadControlNetNode] = None
        preprocessor_node: Optional[DynamicPreprocessorNode] = None

        # Check for and reuse identical preprocessor nodes or control models:
        for control_unit_data in self._controlnet_units:
            if control_unit_data.preprocessor_parameters == preprocessor \
                    and control_unit_data.control_image == control_image_str:
                preprocessor_node = control_unit_data.preprocessor_node
            if control_unit_data.model_node is not None and control_unit_data.model_node.model_name == model_name:
                model_node = control_unit_data.model_node
        if model_node is None and model_name != CONTROLNET_MODEL_NONE:
            model_node = LoadControlNetNode(model_name)
        if preprocessor_node is None:
            preprocessor_node = preprocessor.create_comfyui_node()
        new_control_unit = _ControlInfo(model_node, preprocessor, preprocessor_node, control_image_str, strength,
                                        start_step, end_step)
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

        for model_name, model_strength, clip_strength, extension_model_type in self._extension_models:
            if extension_model_type == ExtensionModelType.LORA:
                lora_node = LoraLoaderNode(model_name, model_strength, clip_strength)
                workflow.connect_nodes(lora_node, LoraLoaderNode.CLIP,
                                       clip_model_node, clip_out_index)
                workflow.connect_nodes(lora_node, LoraLoaderNode.MODEL,
                                       sd_model_node, model_out_index)
                clip_model_node = lora_node
                clip_out_index = LoraLoaderNode.IDX_CLIP
                sd_model_node = lora_node
                model_out_index = LoraLoaderNode.IDX_MODEL
            else:  # hypernetwork
                hypernet_node = HypernetLoaderNode(model_name, model_strength)
                workflow.connect_nodes(hypernet_node, HypernetLoaderNode.MODEL,
                                       sd_model_node, model_out_index)
                sd_model_node = hypernet_node
                model_out_index = HypernetLoaderNode.IDX_MODEL

        # Load image source:
        mask_load_node: Optional[LoadImageMaskNode] = None
        if self.source_image is None:
            image_loading_node: Optional[LoadImageNode] = None
            latent_source_node: ComfyNode = EmptyLatentNode(self.batch_size, self.image_size)
            latent_out_index = EmptyLatentNode.IDX_LATENT
        else:
            image_loading_node = LoadImageNode(self.source_image)
            latent_image_node = VAEEncodeNode()
            workflow.connect_nodes(latent_image_node, VAEEncodeNode.PIXELS,
                                   image_loading_node, LoadImageNode.IDX_IMAGE)
            workflow.connect_nodes(latent_image_node, VAEEncodeNode.VAE,
                                   vae_model_node, vae_out_index)
            latent_out_index = VAEEncodeNode.IDX_LATENT

            latent_source_node = RepeatLatentNode(self.batch_size)
            if self.mask is not None:
                mask_load_node = LoadImageMaskNode(self.mask)
                mask_apply_node = LatentMaskNode()
                workflow.connect_nodes(mask_apply_node, LatentMaskNode.SAMPLES,
                                       latent_image_node, latent_out_index)
                workflow.connect_nodes(mask_apply_node, LatentMaskNode.MASK,
                                       mask_load_node, LoadImageMaskNode.IDX_MASK)
                workflow.connect_nodes(latent_source_node, RepeatLatentNode.SAMPLES,
                                       mask_apply_node, LatentMaskNode.IDX_LATENT)
            else:
                workflow.connect_nodes(latent_source_node, RepeatLatentNode.SAMPLES,
                                       latent_image_node, latent_out_index)
            latent_out_index = RepeatLatentNode.IDX_LATENT

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
            control_apply_node = ApplyControlNetNode(controlnet_unit.strength, controlnet_unit.start_step,
                                                     controlnet_unit.end_step)
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
                               latent_source_node, latent_out_index)

        # Decode and save images:
        latent_decode_node = VAEDecodeNode()
        workflow.connect_nodes(latent_decode_node, VAEDecodeNode.VAE,
                               vae_model_node, vae_out_index)
        workflow.connect_nodes(latent_decode_node, VAEDecodeNode.SAMPLES,
                               sampling_node, KSamplerNode.IDX_LATENT)

        save_image_node = SaveImageNode(self.filename_prefix)
        workflow.connect_nodes(save_image_node, SaveImageNode.IMAGES,
                               latent_decode_node, VAEDecodeNode.IDX_IMAGE)
        return workflow