"""Defines expected data formats for WebUI API requests.  For the main image generation body format, see
   src/api/webui/diffusion_request_body.py."""
from typing import TypedDict, NotRequired, Any

from src.api.webui.script_info_types import ScriptRequestData


class InterrogateBody(TypedDict):
    """Request format for the /sdapi/v1/interrogate endpoint."""
    image: str  # base64-encoded
    model: str  # usually "clip", there's some alternative options you can set up in the WebUI I think


class UpscalingBody(TypedDict):
    """Request format for upscaling using standalone (non-latent) upscalers through the /sdapi/v1/extra-single-image
       endpoint."""
    image: str  # base64 encoded
    show_extras_results: NotRequired[bool]  # Defaults to true. Needs to be true to get image responses.

    # New size specification:
    resize_mode: int  # 0=scale by multiplier, 1=scale to specific resolution.

    # Required if resize_mode=0, don't use if resize_mode=1:
    upscaling_resize: NotRequired[float]  # Default=2.0

    # Required if resize_mode=1, don't use if resize_mode=0:
    upscaling_resize_w: NotRequired[int]
    upscaling_resize_h: NotRequired[int]
    upscaling_crop: NotRequired[bool]  # Default is True

    # Upscaler selection:
    upscaler_1: NotRequired[str]  # default is "None"

    # If you use a secondary upscaler, it runs the same operation with both options, then merges the results using the
    # extras_upscaler_2_visibility parameter to set which is strongest.  Doesn't seem particularly useful to me,
    # IntraPaint probably isn't going to support this.
    upscaler_2: NotRequired[str]  # default is "None"
    extras_upscaler_2_visibility: NotRequired[float]  # range 0.0-1.0, default=0.0

    # NotRequired face restoration:
    # Face restoration is generally worse than inpainting, so IntraPaint probably won't support these.
    # gfpgan face restorer:
    gfpgan_visibility: NotRequired[float]  # range 0.0-1.0, default=0.0

    # codeformer face restorer:
    codeformer_visibility: NotRequired[float]  # range 0.0-1.0, default=0.0
    codeformer_weight: NotRequired[float]  # range 0.0-1.0, default=0.0.  Higher weight = less effect, for some reason.


class Txt2ImgDiffusionBody(TypedDict):
    """Request format for text-to-image diffusion requests through the /sdapi/v1/txt2img.

    SEE ALSO: src/api/webui/diffusion_request_body.py
    """
    sampler_name: str
    batch_size: int
    n_iter: int  # number of batches
    steps: int
    cfg_scale: float  # guidance scale
    width: int
    height: int
    denoising_strength: NotRequired[float]
    # Prompt:
    prompt: str
    negative_prompt: str
    styles: NotRequired[list[str]]

    # RNG:
    seed: int

    # subseed: also known as "variation seed", sets variance across random generation
    subseed: NotRequired[int]
    subseed_strength: NotRequired[int]

    # Seed resize options: for getting similar results at different resolutions:
    seed_resize_from_h: NotRequired[int]
    seed_resize_from_w: NotRequired[int]

    # minor extra features:
    restore_faces: bool
    tiling: bool
    refiner_checkpoint: NotRequired[str]
    refiner_switch_at: NotRequired[int]  # step count

    # settings and misc. server behavior
    infotext: NotRequired[str]  # metadata string: if provided, it overwrites other parameters
    override_settings: NotRequired[dict[str, Any]]
    override_settings_restore_afterwards: NotRequired[bool]
    do_not_save_samples: NotRequired[bool]
    do_not_save_grid: NotRequired[bool]
    disable_extra_networks: NotRequired[bool]  # Turn off LoRAs, etc.
    send_images: bool
    save_images: bool
    comments: NotRequired[dict[str, Any]]  # Add arbitrary extra info to image metadata.
    force_task_id: NotRequired[str]  # Assign this ID to the job instead of using a random one.

    # High-res fix:
    enable_hr: NotRequired[bool]
    firstphase_width: NotRequired[int]
    firstphase_height: NotRequired[int]
    hr_scale: NotRequired[float]
    hr_upscaler: NotRequired[str]
    hr_second_pass_steps: NotRequired[int]
    hr_resize_x: NotRequired[int]
    hr_resize_y: NotRequired[int]
    hr_sampler_name: NotRequired[str]
    hr_prompt: NotRequired[str]
    hr_negative_prompt: NotRequired[str]

    # custom scripts:
    script_name: NotRequired[str]
    script_args: NotRequired[list[Any]]
    alwayson_scripts: NotRequired[dict[str, ScriptRequestData]]

    # Karras(?) sampler parameters (probably don't need to use these)
    eta: NotRequired[float]
    s_min_uncond: NotRequired[float]
    s_churn: NotRequired[float]
    s_tmax: NotRequired[float]
    s_tmin: NotRequired[float]
    s_noise: NotRequired[float]

    # Probably deprecated, present for compatibility reasons:
    sampler_index: NotRequired[str]
    sampler_index: NotRequired[str]


class Img2ImgDiffusionBody(Txt2ImgDiffusionBody):
    """Request format for image-to-image and inpainting diffusion requests through the /sdapi/v1/img2img.

    SEE ALSO: src/api/webui/diffusion_request_body.py
    """
    init_images: list[str]  # base64 image data

    # Resize mode options (selected by index):
    # 0: Just resize (the default)
    # 1: Crop and resize
    # 2. Resize and fill
    # 3. Just resize (latent upscale)
    resize_mode: NotRequired[int]
    image_cfg_scale: NotRequired[float]
    include_init_images: NotRequired[bool]
    firstpass_image: NotRequired[str]  # alternate initial image for the first part of a highres-fix gen.

    # Inpainting only:
    mask: NotRequired[str]  # base64 image data
    mask_blur_x: NotRequired[int]
    mask_blur_y: NotRequired[int]
    mask_blur: NotRequired[int]

    # Inpaint fill options (selected by index):
    # 0: fill
    # 1: original
    # 2: latent noise
    # 3: latent nothing
    inpainting_fill: NotRequired[int]
    inpaint_full_res: NotRequired[bool]
    inpaint_full_res_padding: NotRequired[int]
    inpainting_mask_invert: NotRequired[int]  # 0=don't invert, 1=invert
    mask_round: NotRequired[bool]
    initial_noise_multiplier: NotRequired[float]  # Adjust extra noise added to masked areas
