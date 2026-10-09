"""Builds `sd_backend_client` request parameters from IntraPaint's cached generation settings.

Each builder reads `Cache` and `AppConfig` when called and returns a new model, so a caller that runs it on the main
thread can hand the result to a worker thread unchanged. Images are passed in, already cropped and scaled to the
generation size.
"""
from typing import Optional

from PySide6.QtGui import QImage
from sd_backend_client import ComfyUIDiffusionParams, ControlNetUnit, DiffusionParams, DiffusionRequestBody, \
    DiffusionUpscalingParams, InpaintFillOption

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_generation.sd_adapters.controlnet_adapter import SavedControlNetUnit, load_request_units
from src.controller.image_generation.sd_adapters.image_adapter import qimage_to_pil
from src.util.shared_constants import EDIT_MODE_INPAINT, EDIT_MODE_TXT2IMG

# `Cache.COMFYUI_MODEL_CONFIG` value that lets the server pick a config file matching the model name.
COMFYUI_MODEL_CONFIG_AUTO = 'auto'

# Seam-fix padding for WebUI "Ultimate SD Upscale" requests. ComfyUI requests use the library default.
WEBUI_SEAM_FIX_PADDING = 32


def _comfyui_control_keys() -> list[str]:
    return [Cache.CONTROLNET_ARGS_0_COMFYUI, Cache.CONTROLNET_ARGS_1_COMFYUI, Cache.CONTROLNET_ARGS_2_COMFYUI]


def _webui_control_keys() -> list[str]:
    return [Cache.CONTROLNET_ARGS_0_WEBUI, Cache.CONTROLNET_ARGS_1_WEBUI, Cache.CONTROLNET_ARGS_2_WEBUI]


def _check_images(edit_mode: str, source_image: Optional[QImage], mask: Optional[QImage]) -> None:
    if edit_mode != EDIT_MODE_TXT2IMG and source_image is None:
        raise ValueError(f'{edit_mode} needs a source image')
    if edit_mode == EDIT_MODE_INPAINT and mask is None:
        raise ValueError(f'{edit_mode} needs a mask')


def _shared_params(params: DiffusionParams, edit_mode: str, source_image: Optional[QImage],
                   mask: Optional[QImage], control_keys: list[str]) -> None:
    """Sets the fields both backends read the same way, including images and ControlNet units."""
    cache = Cache()
    params.batch_size = cache.get(Cache.BATCH_SIZE)
    params.steps = cache.get(Cache.SAMPLING_STEPS)
    params.cfg_scale = cache.get(Cache.GUIDANCE_SCALE)
    generation_size = cache.get(Cache.GENERATION_SIZE)
    params.width = generation_size.width()
    params.height = generation_size.height()
    params.prompt = cache.get(Cache.PROMPT)
    params.negative_prompt = cache.get(Cache.NEGATIVE_PROMPT)
    params.seed = int(cache.get(Cache.SEED))
    sampler = cache.get(Cache.SAMPLING_METHOD)
    if sampler != '':
        params.sampler = sampler

    uses_init_image = edit_mode != EDIT_MODE_TXT2IMG
    if uses_init_image:
        assert source_image is not None
        params.init_images = [qimage_to_pil(source_image)]
        params.denoising_strength = cache.get(Cache.DENOISING_STRENGTH)
    if edit_mode == EDIT_MODE_INPAINT:
        assert mask is not None
        params.mask = qimage_to_pil(mask)
    params.controlnet_units = load_request_units(control_keys, source_image, uses_init_image)


def build_comfy_params(edit_mode: str, source_image: Optional[QImage] = None, mask: Optional[QImage] = None,
                       seed: Optional[int] = None) -> ComfyUIDiffusionParams:
    """Returns ComfyUI parameters for a txt2img, img2img or inpainting request.

    Parameters
    ----------
    edit_mode: str
        `EDIT_MODE_TXT2IMG`, `EDIT_MODE_IMG2IMG` or `EDIT_MODE_INPAINT`. Pass the mode to generate with, which can
        differ from `Cache.EDIT_MODE`.
    source_image: Optional[QImage]
        Generation area content. Required except for txt2img, where it is used only as the control image of units set
        to `CONTROLNET_REUSE_IMAGE_CODE`.
    mask: Optional[QImage]
        Inpainting mask, opaque where content changes. Required for inpainting. ComfyUI doesn't blur masks, so apply
        `AppConfig.MASK_BLUR` before passing it. Don't invert it: the library converts it for ComfyUI.
    seed: Optional[int]
        Seed to use in place of `Cache.SEED`, such as the next seed of a multi-batch request.

    Raises
    ------
    ValueError
        If `source_image` or `mask` is missing for an edit mode that needs it.
    """
    _check_images(edit_mode, source_image, mask)
    cache = Cache()
    params = ComfyUIDiffusionParams()
    _shared_params(params, edit_mode, source_image, mask, _comfyui_control_keys())
    params.sd_model_name = cache.get(Cache.SD_MODEL)
    scheduler = cache.get(Cache.SCHEDULER)
    if scheduler != '':
        params.scheduler = scheduler
    if seed is not None:
        params.seed = seed
    params.load_as_inpainting_model = cache.get(Cache.COMFYUI_INPAINTING_MODEL)
    params.vae_tiling_enabled = cache.get(Cache.COMFYUI_TILED_VAE)
    params.vae_tile_size = cache.get(Cache.COMFYUI_TILED_VAE_TILE_SIZE)
    params.clip_skip = cache.get(Cache.CLIP_SKIP)
    model_config = cache.get(Cache.COMFYUI_MODEL_CONFIG)
    params.sd_model_config = None if model_config in ('', COMFYUI_MODEL_CONFIG_AUTO) else model_config
    return params


def build_webui_body(edit_mode: str, source_image: Optional[QImage] = None,
                     mask: Optional[QImage] = None) -> DiffusionRequestBody:
    """Returns a WebUI request body for a txt2img, img2img or inpainting request.

    The body leaves `sd_model_name` empty: the WebUI generator selects the model through the server's settings.

    Parameters
    ----------
    edit_mode: str
        `EDIT_MODE_TXT2IMG`, `EDIT_MODE_IMG2IMG` or `EDIT_MODE_INPAINT`. Pass the mode to generate with, which can
        differ from `Cache.EDIT_MODE`.
    source_image: Optional[QImage]
        Generation area content. Required except for txt2img, where it is used only as the control image of units set
        to `CONTROLNET_REUSE_IMAGE_CODE`.
    mask: Optional[QImage]
        Inpainting mask, opaque where content changes. Required for inpainting. The server applies
        `AppConfig.MASK_BLUR`, so pass it unblurred.

    Raises
    ------
    ValueError
        If `source_image` or `mask` is missing for an edit mode that needs it.
    """
    _check_images(edit_mode, source_image, mask)
    cache = Cache()
    body = DiffusionRequestBody()
    _shared_params(body, edit_mode, source_image, mask, _webui_control_keys())
    body.n_iter = cache.get(Cache.BATCH_COUNT)
    body.restore_faces = cache.get(Cache.WEBUI_RESTORE_FACES)
    body.tiling = cache.get(Cache.WEBUI_TILING)
    if edit_mode != EDIT_MODE_TXT2IMG:
        body.include_init_images = False
    if edit_mode == EDIT_MODE_INPAINT:
        body.inpainting_mask_invert = 0
        body.inpaint_full_res = cache.get(Cache.INPAINT_FULL_RES)
        body.inpaint_full_res_padding = cache.get(Cache.INPAINT_FULL_RES_PADDING)
        body.mask_blur = AppConfig().get(AppConfig.MASK_BLUR)
        body.inpainting_fill = InpaintFillOption(cache.get_option_index(Cache.MASKED_CONTENT))
    else:
        body.inpainting_fill = None
    subseed = cache.get(Cache.WEBUI_SUBSEED)
    if subseed != -1:
        body.subseed = subseed
        body.subseed_strength = cache.get(Cache.WEBUI_SUBSEED_STRENGTH)
    if cache.get(Cache.WEBUI_SEED_RESIZE_ENABLED):
        seed_resize = cache.get(Cache.WEBUI_SEED_RESIZE)
        body.seed_resize_from_w = seed_resize.width()
        body.seed_resize_from_h = seed_resize.height()
    return body


def build_upscale_params(diffusion_params: DiffusionParams) -> DiffusionUpscalingParams:
    """Returns upscaling parameters from the cached upscale settings.

    Parameters
    ----------
    diffusion_params: DiffusionParams
        Base parameters for the Stable Diffusion pass, from `build_comfy_params` or `build_webui_body` with
        `EDIT_MODE_TXT2IMG`. The upscale request sends a copy without its ControlNet units; the cached tile unit is
        the only ControlNet unit an upscale applies.
    """
    cache = Cache()
    tile_size = cache.get(Cache.GENERATION_SIZE)
    upscale_model = cache.get(Cache.SCALING_MODE)
    if upscale_model not in cache.get(Cache.GENERATOR_SCALING_MODES):
        upscale_model = ''
    pass_params = diffusion_params.model_copy(deep=True)
    pass_params.controlnet_units = []
    params = DiffusionUpscalingParams(
        upscaling_mode=upscale_model,
        use_stable_diffusion_upscaling=(cache.get(Cache.SD_UPSCALING_AVAILABLE)
                                        and cache.get(Cache.USE_STABLE_DIFFUSION_UPSCALING)),
        use_ultimate_upscale_script=(cache.get(Cache.ULTIMATE_UPSCALE_SCRIPT_AVAILABLE)
                                     and cache.get(Cache.USE_ULTIMATE_UPSCALE_SCRIPT)),
        diffusion_params=pass_params,
        denoising_strength=cache.get(Cache.SD_UPSCALING_DENOISING_STRENGTH),
        step_count=cache.get(Cache.SD_UPSCALING_STEP_COUNT),
        tile_width=tile_size.width(),
        tile_height=tile_size.height(),
        tile_controlnet=_tile_controlnet_unit())
    if isinstance(diffusion_params, DiffusionRequestBody):
        params.seam_fix_padding = WEBUI_SEAM_FIX_PADDING
    return params


def _tile_controlnet_unit() -> Optional[ControlNetUnit]:
    """Returns the cached upscale tile unit, or None if it is invalid or has no model or preprocessor.

    The saved unit's `enabled` and `image_string` are ignored: the tile unit has no toggle in the UI, and it always
    reads the image being upscaled.
    """
    try:
        saved = SavedControlNetUnit.from_json(Cache().get(Cache.SD_UPSCALING_CONTROLNET_TILE_SETTINGS))
    except (KeyError, ValueError):
        return None
    if saved.unit.model is None or saved.unit.preprocessor is None:
        return None
    return saved.unit
