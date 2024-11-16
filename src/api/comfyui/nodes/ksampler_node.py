"""A ComfyUI node used to control the diffusion sampling process."""
from typing import TypedDict, NotRequired, cast, Any

from src.api.comfyui.nodes.comfy_node import NodeConnection, ComfyNode

KSAMPLER_NAME = 'KSampler'


class KSamplerInputs(TypedDict):
    """A ComfyUI node used to control the diffusion sampling process."""
    cfg: float  # Cache.GUIDANCE_SCALE
    denoise: float  # Cache.DENOISING_STRENGTH, 1.0 for txt2img
    latent_image: NotRequired[NodeConnection]  # Image source node, e.g. EmptyLatentImage
    model: NotRequired[NodeConnection]  # Usually CheckpointLoaderSimple
    negative: NotRequired[NodeConnection]  # Usually CLIPTextEncode
    positive: NotRequired[NodeConnection]  # Usually CLIPTextEncode
    sampler_name: str
    scheduler: str
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

    def __init__(self, cfg: float, steps: int, sampler: str, denoise: float = 1.0,
                 scheduler: str = 'normal', seed: int = -1) -> None:
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
        super().__init__(KSAMPLER_NAME, cast(dict[str, Any], data), connection_params, 1)
