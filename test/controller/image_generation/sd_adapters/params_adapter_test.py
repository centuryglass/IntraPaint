"""Tests building sd_backend_client request parameters from cached generation settings."""
import os

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QColor
from sd_backend_client import ComfyUIDiffusionParams, DiffusionRequestBody, InpaintFillOption

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_generation.sd_adapters.params_adapter import build_comfy_params, build_webui_body, \
    build_upscale_params, WEBUI_SEAM_FIX_PADDING
from src.util.shared_constants import EDIT_MODE_TXT2IMG, EDIT_MODE_IMG2IMG, EDIT_MODE_INPAINT
from test.base_test_case import IntraPaintTestCase, TEST_RESOURCE_DIR

UNIT_DIR = os.path.join(TEST_RESOURCE_DIR, 'controlnet_units')
GENERATION_SIZE = QSize(512, 384)
TILE_MODEL = 'control_v11f1e_sd15_tile [a371b31b]'


def _fixture(name: str) -> str:
    with open(os.path.join(UNIT_DIR, f'{name}.json'), encoding='utf-8') as file:
        return file.read()


def _image(color: QColor) -> QImage:
    image = QImage(GENERATION_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    return image


class ParamsAdapterTest(IntraPaintTestCase):
    """Tests building sd_backend_client request parameters from cached generation settings."""

    def setUp(self) -> None:
        super().setUp()
        cache = Cache()
        cache.set(Cache.GENERATION_SIZE, GENERATION_SIZE)
        cache.set(Cache.PROMPT, 'a lighthouse')
        cache.set(Cache.NEGATIVE_PROMPT, 'blurry')
        cache.set(Cache.SEED, '1234')
        cache.set(Cache.BATCH_SIZE, 2)
        cache.set(Cache.BATCH_COUNT, 3)
        cache.set(Cache.SAMPLING_STEPS, 20)
        cache.set(Cache.GUIDANCE_SCALE, 6.5)
        cache.set(Cache.DENOISING_STRENGTH, 0.6)
        cache.set(Cache.SD_MODEL, 'dreamshaper_8.safetensors', add_missing_options=True)
        AppConfig().set(AppConfig.MASK_BLUR, 4)
        self.source = _image(QColor(10, 20, 30))
        self.mask = _image(QColor(255, 255, 255))

    def test_comfy_txt2img(self) -> None:
        """Txt2img parameters carry the cached settings and no init image or mask."""
        cache = Cache()
        cache.set(Cache.SAMPLING_METHOD, 'dpmpp_2m', add_missing_options=True)
        cache.set(Cache.SCHEDULER, 'karras', add_missing_options=True)
        cache.set(Cache.CLIP_SKIP, 2)
        params = build_comfy_params(EDIT_MODE_TXT2IMG)
        self.assertIsInstance(params, ComfyUIDiffusionParams)
        self.assertEqual((params.sd_model_name, params.prompt, params.negative_prompt, params.seed),
                         ('dreamshaper_8.safetensors', 'a lighthouse', 'blurry', 1234))
        self.assertEqual((params.batch_size, params.steps, params.cfg_scale, params.width, params.height),
                         (2, 20, 6.5, 512, 384))
        self.assertEqual((params.sampler, params.scheduler, params.clip_skip), ('dpmpp_2m', 'karras', 2))
        self.assertIsNone(params.init_images)
        self.assertIsNone(params.mask)
        self.assertIsNone(params.denoising_strength)
        self.assertIsNone(params.sd_model_config, 'the default "auto" config lets the server choose')

    def test_comfy_seed_and_model_config(self) -> None:
        """An explicit seed replaces the cached one, and a named model config is passed through."""
        Cache().set(Cache.COMFYUI_MODEL_CONFIG, 'v1-inference.yaml', add_missing_options=True)
        params = build_comfy_params(EDIT_MODE_TXT2IMG, seed=99)
        self.assertEqual(params.seed, 99)
        self.assertEqual(params.sd_model_config, 'v1-inference.yaml')

    def test_comfy_inpaint(self) -> None:
        """Inpainting sends the source image, the mask unchanged and the cached denoising strength."""
        params = build_comfy_params(EDIT_MODE_INPAINT, self.source, self.mask)
        assert params.init_images is not None and params.mask is not None
        self.assertEqual(params.init_images[0].getpixel((0, 0)), (10, 20, 30, 255))
        self.assertEqual(params.mask.getpixel((0, 0)), (255, 255, 255, 255))
        self.assertEqual(params.denoising_strength, 0.6)

    def test_missing_images_raise(self) -> None:
        """Img2img needs a source image, and inpainting also needs a mask."""
        with self.assertRaises(ValueError):
            build_comfy_params(EDIT_MODE_IMG2IMG)
        with self.assertRaises(ValueError):
            build_webui_body(EDIT_MODE_INPAINT, self.source)

    def test_controlnet_units_use_backend_cache_keys(self) -> None:
        """Each backend reads its own cached units, and the generation area is the control image only for txt2img."""
        cache = Cache()
        cache.set(Cache.CONTROLNET_ARGS_0_COMFYUI, _fixture('legacy_comfyui_unit'))
        cache.set(Cache.CONTROLNET_ARGS_1_WEBUI, _fixture('legacy_webui_unit'))
        comfy_units = build_comfy_params(EDIT_MODE_TXT2IMG, self.source).controlnet_units
        self.assertEqual(len(comfy_units), 1)
        assert comfy_units[0].preprocessor is not None and comfy_units[0].image is not None
        self.assertEqual(comfy_units[0].preprocessor.typedef.name, 'CannyEdgePreprocessor')
        webui_units = build_webui_body(EDIT_MODE_IMG2IMG, self.source).controlnet_units
        self.assertEqual(len(webui_units), 1)
        assert webui_units[0].preprocessor is not None
        self.assertEqual(webui_units[0].preprocessor.typedef.name, 'canny')
        self.assertIsNone(webui_units[0].image, 'img2img units reuse the init image')

    def test_webui_txt2img(self) -> None:
        """WebUI txt2img sends batch count and extras, no model name and no inpainting fields."""
        cache = Cache()
        cache.set(Cache.SAMPLING_METHOD, 'Euler a', add_missing_options=True)
        cache.set(Cache.WEBUI_SUBSEED, 55)
        cache.set(Cache.WEBUI_SUBSEED_STRENGTH, 0.3)
        cache.set(Cache.WEBUI_SEED_RESIZE_ENABLED, True)
        cache.set(Cache.WEBUI_SEED_RESIZE, QSize(256, 128))
        body = build_webui_body(EDIT_MODE_TXT2IMG)
        self.assertIsInstance(body, DiffusionRequestBody)
        self.assertEqual((body.sampler, body.n_iter, body.seed, body.sd_model_name), ('Euler a', 3, 1234, ''))
        self.assertEqual((body.subseed, body.subseed_strength), (55, 0.3))
        self.assertEqual((body.seed_resize_from_w, body.seed_resize_from_h), (256, 128))
        self.assertIsNone(body.inpainting_fill)
        self.assertIsNone(body.mask_blur)
        self.assertIsNone(body.include_init_images)
        self.assertNotIn('denoising_strength', body.to_dict())

    def test_webui_inpaint(self) -> None:
        """WebUI inpainting sends the mask settings, with the server applying the configured mask blur."""
        cache = Cache()
        cache.set(Cache.INPAINT_FULL_RES, True)
        cache.set(Cache.INPAINT_FULL_RES_PADDING, 48)
        cache.update_options(Cache.MASKED_CONTENT, ['fill', 'original', 'latent noise', 'latent nothing'])
        cache.set(Cache.MASKED_CONTENT, 'latent noise')
        body = build_webui_body(EDIT_MODE_INPAINT, self.source, self.mask)
        self.assertEqual((body.mask_blur, body.inpainting_mask_invert, body.include_init_images), (4, 0, False))
        self.assertEqual((body.inpaint_full_res, body.inpaint_full_res_padding), (True, 48))
        self.assertEqual(body.inpainting_fill, InpaintFillOption.LATENT_NOISE.value)
        self.assertEqual(body.denoising_strength, 0.6)

    def test_upscale_params(self) -> None:
        """Upscaling reads the cached upscale settings, drops regular ControlNet units and loads the tile unit."""
        cache = Cache()
        cache.set(Cache.GENERATOR_SCALING_MODES, ['Lanczos', 'ESRGAN_4x'])
        cache.set(Cache.SCALING_MODE, 'ESRGAN_4x', add_missing_options=True)
        cache.set(Cache.SD_UPSCALING_AVAILABLE, True)
        cache.set(Cache.USE_STABLE_DIFFUSION_UPSCALING, True)
        cache.set(Cache.ULTIMATE_UPSCALE_SCRIPT_AVAILABLE, False)
        cache.set(Cache.SD_UPSCALING_DENOISING_STRENGTH, 0.25)
        cache.set(Cache.SD_UPSCALING_STEP_COUNT, 12)
        cache.set(Cache.CONTROLNET_ARGS_0_WEBUI, _fixture('legacy_webui_unit'))
        cache.set(Cache.SD_UPSCALING_CONTROLNET_TILE_SETTINGS,
                  _fixture('legacy_webui_unit').replace('control_v11p_sd15_canny [d14c016b]', TILE_MODEL))
        base = build_webui_body(EDIT_MODE_TXT2IMG, self.source)
        self.assertEqual(len(base.controlnet_units), 1)
        params = build_upscale_params(base)
        self.assertEqual(params.upscaling_mode, 'ESRGAN_4x')
        self.assertTrue(params.use_stable_diffusion_upscaling)
        self.assertFalse(params.use_ultimate_upscale_script)
        self.assertEqual((params.denoising_strength, params.step_count), (0.25, 12))
        self.assertEqual((params.tile_width, params.tile_height), (512, 384))
        self.assertEqual(params.seam_fix_padding, WEBUI_SEAM_FIX_PADDING)
        self.assertEqual(params.diffusion_params.controlnet_units, [])
        self.assertEqual(len(base.controlnet_units), 1, 'the base parameters must not change')
        assert params.tile_controlnet is not None and params.tile_controlnet.model is not None
        self.assertEqual(params.tile_controlnet.model.full_model_name, TILE_MODEL)

    def test_upscale_params_without_valid_options(self) -> None:
        """An unknown upscaler and an unset tile unit are left out, and ComfyUI keeps the default seam-fix padding."""
        cache = Cache()
        cache.set(Cache.GENERATOR_SCALING_MODES, ['Lanczos'])
        cache.set(Cache.SCALING_MODE, 'missing_model', add_missing_options=True)
        cache.set(Cache.SD_UPSCALING_CONTROLNET_TILE_SETTINGS, _fixture('legacy_default_unit'))
        params = build_upscale_params(build_comfy_params(EDIT_MODE_TXT2IMG))
        self.assertEqual(params.upscaling_mode, '')
        self.assertIsNone(params.tile_controlnet)
        self.assertNotEqual(params.seam_fix_padding, WEBUI_SEAM_FIX_PADDING)
