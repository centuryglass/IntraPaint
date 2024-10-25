"""Unified class for building text to image, image to image, and inpainting ComfyUI workflows."""
import random
from typing import Optional, cast

from PySide6.QtCore import QSize

from src.api.comfyui_nodes.comfy_node import ComfyNode
from src.api.comfyui_nodes.comfy_node_graph import ComfyNodeGraph
from src.api.comfyui_nodes.input.checkpoint_loader_node import CheckpointLoaderNode
from src.api.comfyui_nodes.input.clip_text_encode_node import ClipTextEncodeNode
from src.api.comfyui_nodes.input.empty_latent_image_node import EmptyLatentNode
from src.api.comfyui_nodes.input.load_image_mask_node import LoadImageMaskNode
from src.api.comfyui_nodes.input.load_image_node import LoadImageNode
from src.api.comfyui_nodes.input.simple_checkpoint_loader_node import SimpleCheckpointLoaderNode
from src.api.comfyui_nodes.ksampler_node import SAMPLER_OPTIONS, SamplerName, SCHEDULER_OPTIONS, SchedulerName, \
    KSamplerNode
from src.api.comfyui_nodes.latent_mask_node import LatentMaskNode
from src.api.comfyui_nodes.repeat_latent_node import RepeatLatentNode
from src.api.comfyui_nodes.save_image_node import SaveImageNode
from src.api.comfyui_nodes.vae.vae_decode_node import VAEDecodeNode
from src.api.comfyui_nodes.vae.vae_encode_node import VAEEncodeNode

random.seed()

DEFAULT_STEP_COUNT = 30
DEFAULT_CFG = 8.0
DEFAULT_SIZE = 512
DEFAULT_SAMPLER = SAMPLER_OPTIONS[0]
DEFAULT_SCHEDULER = SCHEDULER_OPTIONS[0]
MAX_SEED = 0xffffffffffffffff
MAX_BATCH_SIZE = 64


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
        self._source_mask: Optional[str] = None

        # TODO: not yet supported:
        # self._is_inpainting_model = False
        # self._controlnet_preprocessors: List[ComfyNode] = []
        # self._controlnet_models: List[ComfyNode] = []
        # self._embeddings: List[str] = []
        # self._hypernetworks: List[str] = []

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

    @property
    def source_image(self) -> Optional[str]:
        """Accesses the initial image to use as initial latent data. If None, empty latent data is used.  Otherwise,
           this needs to be an image that was already uploaded to ComfyUI."""
        return self._source_image

    @source_image.setter
    def source_image(self, source_image: Optional[str]) -> None:
        self._source_image = source_image

    @property
    def source_mask(self) -> Optional[str]:
        """Accesses the inpainting mask to apply to the source image.  If None, no mask is used. Otherwise, this needs
           to be a mask that was already uploaded to ComfyUI, and source_image should be set to the matching image
           specified when the mask was uploaded."""
        return self._source_mask

    @source_mask.setter
    def source_mask(self, source_mask: Optional[str]) -> None:
        self._source_mask = source_mask

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

    def build_workflow(self) -> ComfyNodeGraph:
        """Use the provided parameters to build a complete workflow graph."""
        workflow = ComfyNodeGraph()

        # Load model(s):
        if self.model_config_path is None:
            model_loading_node: ComfyNode = SimpleCheckpointLoaderNode(self.sd_model)
            model_source, model_index = model_loading_node, 0
            vae_source, vae_index = model_loading_node, 0
            clip_source: Optional[ComfyNode] = None
            clip_index = 0
        else:
            model_loading_node = CheckpointLoaderNode(self.sd_model, self.model_config_path)
            model_source, model_index = model_loading_node, CheckpointLoaderNode.IDX_MODEL
            vae_source, vae_index = model_loading_node, CheckpointLoaderNode.IDX_VAE
            clip_source, clip_index = model_loading_node, CheckpointLoaderNode.IDX_CLIP

        # Load image source:
        if self.source_image is None:
            image_source_node: ComfyNode = EmptyLatentNode(self.batch_size, self.image_size)
        else:
            image_loading_node = LoadImageNode(self.source_image)
            latent_image_node = VAEEncodeNode()
            workflow.connect_nodes(latent_image_node, VAEEncodeNode.PIXELS, image_loading_node, 0)
            workflow.connect_nodes(latent_image_node, VAEEncodeNode.VAE, vae_source, vae_index)

            image_source_node = RepeatLatentNode(self.batch_size)
            if self.source_mask is not None:
                mask_load_node = LoadImageMaskNode(self.source_mask)
                mask_apply_node = LatentMaskNode()
                workflow.connect_nodes(mask_apply_node, LatentMaskNode.SAMPLES, latent_image_node, 0)
                workflow.connect_nodes(mask_apply_node, LatentMaskNode.MASK, mask_load_node, 0)
                workflow.connect_nodes(image_source_node, RepeatLatentNode.SAMPLES, mask_apply_node, 0)
            else:
                workflow.connect_nodes(image_source_node, RepeatLatentNode.SAMPLES, latent_image_node, 0)

        # Load prompt conditioning:
        prompt_node = ClipTextEncodeNode(self.prompt)
        negative_node = ClipTextEncodeNode(self.negative_prompt)
        if clip_source is not None:
            workflow.connect_nodes(prompt_node, ClipTextEncodeNode.CLIP, clip_source, clip_index)
            workflow.connect_nodes(negative_node, ClipTextEncodeNode.CLIP, clip_source, clip_index)

        # Core diffusion process in KSamplerNode:
        sampling_node = KSamplerNode(self.cfg_scale, self.steps, self.sampler, self.denoising_strength, self.scheduler,
                                     self.seed)
        workflow.connect_nodes(sampling_node, KSamplerNode.MODEL, model_source, model_index)
        workflow.connect_nodes(sampling_node, KSamplerNode.POSITIVE, prompt_node, 0)
        workflow.connect_nodes(sampling_node, KSamplerNode.NEGATIVE, negative_node, 0)
        workflow.connect_nodes(sampling_node, KSamplerNode.LATENT_IMAGE, image_source_node, 0)

        # Decode and save images:
        latent_decode_node = VAEDecodeNode()
        workflow.connect_nodes(latent_decode_node, VAEDecodeNode.VAE, vae_source, vae_index)
        workflow.connect_nodes(latent_decode_node, VAEDecodeNode.SAMPLES, sampling_node, 0)

        save_image_node = SaveImageNode(self.filename_prefix)
        workflow.connect_nodes(save_image_node, SaveImageNode.IMAGES, latent_decode_node, 0)
        return workflow





