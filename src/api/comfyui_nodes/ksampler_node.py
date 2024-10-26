"""A ComfyUI node used to control the diffusion sampling process."""
from typing import TypedDict, NotRequired, TypeAlias, Literal, List, cast, Dict, Any

from src.api.comfyui_nodes.comfy_node import NodeConnection, ComfyNode

KSAMPLER_NAME = 'KSampler'

# Sampler options:  TODO: figure out if these are shared via the API anywhere. The list here is copied from
#                         https://github.com/comfyanonymous/ComfyUI/blob/master/comfy/samplers.py#L575, and line 736,
#                         but it would be better to load it dynamically.
SAMPLER_OPTIONS: List[str] = ['euler', 'euler_cfg_pp', 'euler_ancestral', 'euler_ancestral_cfg_pp', 'heun', 'heunpp2',
                              'dpm_2', 'dpm_2_ancestral', 'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral',
                              'dpmpp_2s_ancestral_cfg_pp', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_cfg_pp',
                              'dpmpp_2m_sde', 'dpmpp_2m_sde_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddpm', 'lcm',
                              'ipndm', 'ipndm_v', 'deis', 'ddim', 'uni_pc', 'uni_pc_bh2']
SamplerName: TypeAlias = Literal[
    'euler', 'euler_cfg_pp', 'euler_ancestral', 'euler_ancestral_cfg_pp', 'heun', 'heunpp2',
    'dpm_2', 'dpm_2_ancestral', 'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral',
    'dpmpp_2s_ancestral_cfg_pp', 'dpmpp_sde', 'dpmpp_sde_gpu', 'dpmpp_2m', 'dpmpp_2m_cfg_pp',
    'dpmpp_2m_sde', 'dpmpp_2m_sde_gpu', 'dpmpp_3m_sde', 'dpmpp_3m_sde_gpu', 'ddpm', 'lcm',
    'ipndm', 'ipndm_v', 'deis', 'ddim', 'uni_pc', 'uni_pc_bh2']

SCHEDULER_OPTIONS: List[str] = ['normal', 'karras', 'exponential', 'sgm_uniform', 'simple', 'ddim_uniform', 'beta']
SchedulerName: TypeAlias = Literal['normal', 'karras', 'exponential', 'sgm_uniform', 'simple', 'ddim_uniform', 'beta']


class KSamplerInputs(TypedDict):
    """A ComfyUI node used to control the diffusion sampling process."""
    cfg: float  # Cache.GUIDANCE_SCALE
    denoise: float  # Cache.DENOISING_STRENGTH, 1.0 for txt2img
    latent_image: NotRequired[NodeConnection]  # Image source node, e.g. EmptyLatentImage
    model: NotRequired[NodeConnection]  # Usually CheckpointLoaderSimple
    negative: NotRequired[NodeConnection]  # Usually CLIPTextEncode
    positive: NotRequired[NodeConnection]  # Usually CLIPTextEncode
    sampler_name: SamplerName
    scheduler: SchedulerName
    seed: int
    steps: int


class KSamplerNode(ComfyNode):
    """Diffusion sampler node."""

    # Connection keys:
    LATENT_IMAGE = 'latent_image'
    MODEL = 'model'
    NEGATIVE = 'negative'
    POSITIVE = 'positive'

    # Output indexes:
    IDX_LATENT = 0

    def __init__(self, cfg: float, steps: int, sampler: SamplerName, denoise: float = 1.0,
                 scheduler: SchedulerName = 'normal', seed: int = -1) -> None:
        data: KSamplerInputs = {
            'cfg': cfg,
            'denoise': denoise,
            'sampler_name': sampler,
            'scheduler': scheduler,
            'seed': seed,
            'steps': steps
        }
        connection_params = {
            KSamplerNode.LATENT_IMAGE,
            KSamplerNode.MODEL,
            KSamplerNode.NEGATIVE,
            KSamplerNode.POSITIVE
        }
        super().__init__(KSAMPLER_NAME, cast(Dict[str, Any], data), connection_params, 1)
