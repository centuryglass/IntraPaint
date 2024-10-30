"""WebUI API response data formats."""
from typing import TypedDict, Any, TypeAlias, Optional

from src.api.webui.request_formats import Txt2ImgRequestBody, Img2ImgRequestBody


class ProgressStateDict(TypedDict):
    """Defines the "state" section within /sdapi/v1/progress responses."""
    skipped: bool
    interrupted: bool
    stopping_generation: bool
    job: str
    job_count: int
    job_timestamp: str
    job_no: int
    sampling_step: int
    sampling_steps: int


class ProgressResponseBody(TypedDict):
    """WebUI API response format for the /sdapi/v1/progress endpoint."""
    progress: float  # Fraction completed
    eta_relative: float  # Expected time remaining in seconds
    state: ProgressStateDict
    current_image: Optional[str]
    textinfo: Optional[str]


# LoRA model data:
class LoraMetadata(TypedDict, total=False):
    """Extra metadata associated with a LoRA model.  I've left out a lot of parameters, this just defines the ones
       that IntraPaint might want to show to users eventually."""
    ss_sd_model_name: str  # Model used for training
    ss_sd_model_hash: str
    ss_resolution: str  # str(tuple(width, height))
    ss_clip_skip: str  # int string, or "None"
    ss_num_train_images: str  # int string
    ss_dataset_dirs: dict[str, dict[str, int]]  # Training data directories
    ss_enable_bucket: str  # bool string
    ss_epoch: str  # int string

    # Bucket data structure: it's potentially useful to see what sizes the LoRA is trained on.
    # bucket_idx: { "resolution": [width, height], "count": num_images }
    ss_bucket_info: dict[str, Any]  # Training image resolution groups

    # Training tags: potentially useful for constructing LoRA prompts.
    ss_tag_frequency: dict[str, dict[str, int]]

    sshs_model_hash: str


class LoraInfo(TypedDict):
    """Data used to define a LoRA model in WebUI API responses from the /sdapi/v1/loras endpoint."""
    name: str
    alias: str
    path: str  # NOTE: this is an absolute path
    metadata: LoraMetadata


class ModelInfo(TypedDict):
    """Data used to define Stable-Diffusion models in WebUI API responses from the /sdapi/v1/sd-models endpoint."""
    title: str
    model_name: str
    hash: str
    sha256: str
    filename: str
    config: Optional[str]


class VaeInfo(TypedDict):
    """Data used to define Stable-Diffusion VAE models in WebUI API responses from the /sdapi/v1/sd-vae endpoint."""
    model_name: str
    filename: str


class SamplerInfo(TypedDict):
    """Data used to define Stable-Diffusion samplers in WebUI API responses from the /sdap1/v1/samplers endpoint."""
    name: str
    aliases: list[str]
    options: dict[str, str]


class UpscalerInfo(TypedDict):
    """Data used to define upscalers in WebUI API responses from the /sdapi/v1/upscalers endpoint."""
    name: str
    model_name: Optional[str]
    model_path: Optional[str]
    model_url: Optional[str]
    scale: float


class HypernetworkInfo(TypedDict):
    """Data used to define hypernetwork models in API responses from the /sdapi/v1/hypernetworks endpoint."""
    name: str
    path: str


class LatentUpscalerInfo(TypedDict):
    """Data used to define latent upscalers in API responses from the /sdapi/v1/latent-upscale-modes endpoint."""
    name: str


# Prompt styles are sent as a list of JSON object strings.
PromptStyleRes: TypeAlias = list[str]


class GenerationInfoData(TypedDict):
    """Extra info data returned in a JSON string in txt2img/img2img responses. Sends back provided parameters, defaults
       used for parameters that weren't specified, additional batch output info, seed values used, and other misc.
       information."""
    prompt: str
    all_prompts: list[str]
    negative_prompt: str
    all_negative_prompts: list[str]
    seed: int
    all_seeds: list[int]
    subseed: int
    all_subseeds: list[int]
    subseed_strength: float
    width: int
    height: int
    sampler_name: str
    cfg_scale: float
    batch_size: int
    restore_faces: bool
    sd_model_name: str
    sd_model_hash: str
    sd_vae_name: Optional[str]
    sd_vae_hash: Optional[str]
    seed_resize_from_w: int
    seed_resize_from_h: int
    denoising_strength: Optional[float]
    extra_generation_params: dict[str, Any]
    index_of_first_image: int
    infotexts: list[str]  # A.K.A. metadata
    styles: list[str]
    job_timestamp: str  # int string
    clip_skip: int
    is_using_inpainting_conditioning: bool
    version: str


class Txt2ImgResponse(TypedDict):
    """WebUI API response for a successful /sdapi/v1/txt2img request."""
    images: list[str]  # base64 image list
    parameters: Txt2ImgRequestBody  # Sends back the unchanged request parameters
    info: str  # Serialized JSON, parses as GenerationInfoData


class Img2ImgResponse(TypedDict):
    """WebUI API response for a successful /sdapi/v1/img2img request."""
    images: list[str]  # base64 image list
    parameters: Img2ImgRequestBody  # Sends back the unchanged request parameters
    info: str  # Serialized JSON, parses as GenerationInfoData


class PromptStyleData(TypedDict):
    """Data used to define prompt styles in API responses from the /sdapi/v1/prompt-style endpoint, after parsing from
       JSON string."""
    name: str
    prompt: str
    negative_prompt: str


class InterrogateResponse(TypedDict):
    """Response format for /sdapi/v1/interrogate API requests. The documentation lists the expected response as a plain
       string, so probably best to make sure responses actually fit this pattern before assuming that they do."""
    caption: str
