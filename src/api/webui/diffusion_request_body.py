"""Typedefs for WebUI API data."""
import logging
import os.path
from copy import deepcopy
from dataclasses import dataclass, asdict
from typing import Any, Optional, cast

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from src.api.webui.controlnet_constants import ControlNetUnitDict, CONTROLNET_SCRIPT_KEY
from src.api.webui.script_info_types import ScriptRequestData
from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.util.shared_constants import EDIT_MODE_INPAINT, EDIT_MODE_IMG2IMG, \
    CONTROLNET_REUSE_IMAGE_CODE
from src.util.visual.image_utils import image_to_base64

logger = logging.getLogger(__name__)


@dataclass
class DiffusionRequestBody:
    """Request body format for image generation (all types)"""
    # Basic image generation:
    sampler_name: str = ''
    batch_size: int = 1
    n_iter: int = 1  # number of batches
    steps: int = 30
    cfg_scale: float = 7.0  # guidance scale
    width: int = 512
    height: int = 512
    denoising_strength: Optional[float] = None

    # Img2img and inpainting only:
    init_images: Optional[list[str]] = None  # base64 image data

    # Resize mode options (selected by index):
    # 0: Just resize (the default)
    # 1: Crop and resize
    # 2. Resize and fill
    # 3. Just resize (latent upscale)
    resize_mode: Optional[int] = None
    image_cfg_scale: Optional[float] = None  # TODO: how does this differ from regular cfg_scale?
    include_init_images: Optional[bool] = None
    firstpass_image: Optional[str] = None  # alternate initial image for the first part of a highres-fix gen.

    # Inpainting only:
    mask: Optional[str] = None  # base64 image data
    mask_blur_x: Optional[int] = None
    mask_blur_y: Optional[int] = None
    mask_blur: Optional[int] = None

    # Inpaint fill options (selected by index):
    # 0: fill
    # 1: original
    # 2: latent noise
    # 3: latent nothing
    inpainting_fill: Optional[int] = None
    inpaint_full_res: Optional[bool] = None
    inpaint_full_res_padding: Optional[int] = None
    inpainting_mask_invert: Optional[int] = None  # 0=don't invert, 1=invert
    mask_round: Optional[bool] = None
    initial_noise_multiplier: Optional[float] = None  # Adjust extra noise added to masked areas

    # Img2img/inpaint exlcusive options end here.

    # Prompt:
    prompt: str = ''
    negative_prompt: str = ''
    styles: Optional[list[str]] = None

    # RNG:
    seed: int = -1

    # subseed: also known as "variation seed", sets variance across random generation
    subseed: Optional[int] = None
    subseed_strength: Optional[int] = None

    # Seed resize options: for getting similar results at different resolutions:
    seed_resize_from_h: Optional[int] = None
    seed_resize_from_w: Optional[int] = None

    # minor extra features:
    restore_faces: bool = False
    tiling: bool = False
    refiner_checkpoint: Optional[str] = None
    refiner_switch_at: Optional[int] = None  # step count

    # settings and misc. server behavior
    infotext: Optional[str] = None  # metadata string: if provided, it overwrites other parameters
    override_settings: Optional[dict[str, Any]] = None
    override_settings_restore_afterwards: Optional[bool] = None
    do_not_save_samples: Optional[bool] = None
    do_not_save_grid: Optional[bool] = None
    disable_extra_networks: Optional[bool] = None  # Turn off LoRAs, etc.
    send_images: bool = True
    save_images: bool = False
    comments: Optional[dict[str, Any]] = None  # Add arbitrary extra info to image metadata.
    force_task_id: Optional[str] = None  # Assign this ID to the job instead of using a random one.

    # High-res fix:
    enable_hr: Optional[bool] = None
    firstphase_width: Optional[int] = None
    firstphase_height: Optional[int] = None
    hr_scale: Optional[float] = None
    hr_upscaler: Optional[str] = None
    hr_second_pass_steps: Optional[int] = None
    hr_resize_x: Optional[int] = None
    hr_resize_y: Optional[int] = None
    hr_sampler_name: Optional[str] = None
    hr_prompt: Optional[str] = None
    hr_negative_prompt: Optional[str] = None

    # custom scripts:
    script_name: Optional[str] = None
    script_args: Optional[list[Any]] = None
    alwayson_scripts: Optional[dict[str, ScriptRequestData]] = None

    # Karras(?) sampler parameters (probably don't need to use these)
    eta: Optional[float] = None
    s_min_uncond: Optional[float] = None
    s_churn: Optional[float] = None
    s_tmax: Optional[float] = None
    s_tmin: Optional[float] = None
    s_noise: Optional[float] = None

    # Probably deprecated, present for compatibility reasons:
    sampler_index: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the request body to a dict, removing unused optional parameters."""
        data = asdict(self)
        empty_keys = [key for key in data if data[key] is None]
        for key in empty_keys:
            del data[key]
        return data

    def load_data(self, image: Optional[QImage] = None, mask: Optional[QImage] = None) -> None:
        """Load as many parameters as possible from config, cache, and optional image parameters."""
        config = AppConfig()
        cache = Cache()

        self.sampler_name = cache.get(Cache.SAMPLING_METHOD)
        self.batch_size = cache.get(Cache.BATCH_SIZE)
        self.n_iter = cache.get(Cache.BATCH_COUNT)
        self.steps = cache.get(Cache.SAMPLING_STEPS)
        self.cfg_scale = cache.get(Cache.GUIDANCE_SCALE)

        size = cast(QSize, cache.get(Cache.GENERATION_SIZE))
        self.width = size.width()
        self.height = size.height()

        self.prompt = cache.get(Cache.PROMPT)
        self.negative_prompt = cache.get(Cache.NEGATIVE_PROMPT)
        self.seed = int(cache.get(Cache.SEED))

        self.restore_faces = config.get(AppConfig.RESTORE_FACES)
        self.tiling = config.get(AppConfig.TILING)
        if self.alwayson_scripts is None:
            self.alwayson_scripts = {}

        edit_mode = cache.get(Cache.EDIT_MODE)
        if edit_mode in (EDIT_MODE_IMG2IMG, EDIT_MODE_INPAINT):
            if image is not None:
                self.add_init_image(image)
            self.include_init_images = False
            self.denoising_strength = cache.get(Cache.DENOISING_STRENGTH)

            if edit_mode == EDIT_MODE_INPAINT:
                if mask is not None:
                    self.mask = image_to_base64(mask, include_prefix=True)
                self.inpainting_mask_invert = 0
                self.inpaint_full_res = cache.get(Cache.INPAINT_FULL_RES)
                self.inpaint_full_res_padding = cache.get(Cache.INPAINT_FULL_RES_PADDING)
                self.mask_blur = config.get(AppConfig.MASK_BLUR)

        # Add ControlNet parameters:
        if CONTROLNET_SCRIPT_KEY in self.alwayson_scripts:
            self.alwayson_scripts[CONTROLNET_SCRIPT_KEY] = {'args': []}  # Make sure to clear any old ControlNet defs
        for controlnet_key in (Cache.CONTROLNET_ARGS_0, Cache.CONTROLNET_ARGS_1, Cache.CONTROLNET_ARGS_2):
            control_unit = cast(ControlNetUnitDict, deepcopy(cache.get(controlnet_key)))
            if 'enabled' not in control_unit or not control_unit['enabled']:
                continue
            if 'image' in control_unit:
                control_image = control_unit['image']
                if control_image == CONTROLNET_REUSE_IMAGE_CODE and image is not None:
                    if edit_mode in (EDIT_MODE_IMG2IMG, EDIT_MODE_INPAINT) and self.init_images is not None \
                            and len(self.init_images) > 0:
                        control_unit['image'] = self.init_images[-1]
                    else:
                        control_unit['image'] = image_to_base64(image, include_prefix=True)
                elif isinstance(control_image, str) and os.path.exists(control_image):
                    try:
                        control_unit['image'] = image_to_base64(control_unit['image'], include_prefix=True)
                    except (IOError, KeyError) as err:
                        logger.error(f"Error loading controlnet image {control_image}: {err}")
                        control_unit['image'] = None
            if CONTROLNET_SCRIPT_KEY not in self.alwayson_scripts:
                self.alwayson_scripts[CONTROLNET_SCRIPT_KEY] = {'args': []}
            self.alwayson_scripts[CONTROLNET_SCRIPT_KEY]['args'].append(control_unit)

    def add_init_image(self, image: QImage) -> None:
        """Adds a base64 init image."""
        if self.init_images is None:
            self.init_images = []
        image_str = image_to_base64(image, include_prefix=True)
        self.init_images.append(image_str)
