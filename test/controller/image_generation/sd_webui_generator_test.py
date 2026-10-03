"""Pins the request payloads SDWebUIGenerator sends to the Stable Diffusion WebUI, using JSON snapshots.

See sd_generator_test_case.py for how the snapshots work.
"""
import json
from typing import Any

from PySide6.QtCore import QSize, Qt

from src.api.a1111_webservice import A1111Webservice, ULTIMATE_UPSCALE_SCRIPT
from src.api.controlnet.controlnet_unit import ControlKeyType
from src.api.webui.controlnet_webui_utils import get_all_preprocessors
from src.config.cache import Cache
from src.controller.image_generation.sd_webui_generator import SDWebUIGenerator
from src.util.shared_constants import EDIT_MODE_TXT2IMG, EDIT_MODE_IMG2IMG, EDIT_MODE_INPAINT
from test.controller.image_generation.fake_sd_backend import image_to_base64_png
from test.controller.image_generation.sd_generator_test_case import SdGeneratorTestCase, TEST_SEED, \
    UPSCALE_SIZE, solid_image

Endpoints = A1111Webservice.Endpoints

CANNY_MODEL = 'control_v11p_sd15_canny [d14c016b]'
TILE_MODEL = 'control_v11f1e_sd15_tile [a371b31b]'
UPSCALER_NAMES = ['None', 'Lanczos', 'R-ESRGAN 4x+']


class SDWebUIGeneratorTest(SdGeneratorTestCase):
    """Snapshots WebUI txt2img, img2img, inpainting, ControlNet and upscaling requests."""

    snapshot_subdir = 'webui'

    def setUp(self) -> None:
        super().setUp()
        cache = Cache()
        cache.set(Cache.SAMPLING_METHOD, 'Euler a', add_missing_options=True)
        cache.set(Cache.MASKED_CONTENT, 'original')

        backend = self.backend
        backend.route('GET', Endpoints.PROGRESS, {'progress': 0.0, 'eta_relative': 0.0, 'current_image': None})
        backend.route('POST', Endpoints.TXT2IMG, self._image_response)
        backend.route('POST', Endpoints.IMG2IMG, self._image_response)
        backend.route('POST', Endpoints.UPSCALE,
                      lambda _args: {'image': image_to_base64_png(solid_image(UPSCALE_SIZE, Qt.GlobalColor.green))})
        backend.route('GET', Endpoints.CONTROLNET_MODELS, {'model_list': [CANNY_MODEL, TILE_MODEL]})
        backend.route('GET', Endpoints.CONTROLNET_MODULES, {'module_list': ['none', 'canny', 'tile_resample']})
        backend.route('GET', Endpoints.UPSCALERS, [{'name': name} for name in UPSCALER_NAMES])

        self.generator = SDWebUIGenerator(None, self.image_stack, self.server_args())  # type: ignore
        self.capture_generated_images(self.generator)
        # Progress polling runs in its own thread and sends nothing but GET requests:
        self.generator._async_progress_check = lambda *_args: None  # type: ignore # pylint: disable=protected-access

    @staticmethod
    def _image_response(arguments: dict[str, Any]) -> dict[str, Any]:
        body = arguments['body']
        image_count = body['batch_size'] * body['n_iter']
        size = QSize(body['width'], body['height'])
        return {
            'images': [image_to_base64_png(solid_image(size, Qt.GlobalColor.blue)) for _ in range(image_count)],
            'info': json.dumps({'seed': body['seed'], 'subseed': 5678})
        }

    @staticmethod
    def _set_canny_controlnet_unit() -> None:
        canny = get_all_preprocessors(['canny'])[0]
        Cache().set(Cache.CONTROLNET_ARGS_0_WEBUI,
                    SdGeneratorTestCase.controlnet_unit(ControlKeyType.WEBUI, CANNY_MODEL, canny))

    def _generate_and_check(self, snapshot_name: str) -> None:
        self.run_generate()
        self.assert_requests_match_snapshot(snapshot_name)
        self.assertEqual(len(self.generated_images), 4)
        self.assertIn({'seed': str(TEST_SEED), 'subseed': '5678'}, self.status.emitted)

    def test_txt2img(self) -> None:
        """Text to image sends one txt2img request with the cached settings and no image data."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_TXT2IMG)
        self._generate_and_check('txt2img')

    def test_txt2img_controlnet_reusing_generation_area(self) -> None:
        """A ControlNet unit reusing the generation area gets its own copy of the image in text to image mode."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_TXT2IMG)
        self._set_canny_controlnet_unit()
        self._generate_and_check('txt2img_controlnet')

    def test_img2img(self) -> None:
        """Image to image sends the generation area content as the init image."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_IMG2IMG)
        self._generate_and_check('img2img')

    def test_inpaint(self) -> None:
        """Inpainting sends the init image and a grayscale mask, with the inpainting options."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_INPAINT)
        self._generate_and_check('inpaint')

    def test_inpaint_full_res(self) -> None:
        """Inpainting at full resolution leaves cropping to the WebUI, so only the flag and padding change."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_INPAINT)
        Cache().set(Cache.INPAINT_FULL_RES, True)
        self._generate_and_check('inpaint_full_res')

    def test_inpaint_controlnet_reusing_generation_area(self) -> None:
        """A ControlNet unit reusing the generation area sends no image of its own when inpainting."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_INPAINT)
        self._set_canny_controlnet_unit()
        self._generate_and_check('inpaint_controlnet')

    def test_upscale_basic(self) -> None:
        """Upscaling without Stable Diffusion sends the whole image to the extras endpoint."""
        Cache().set(Cache.SCALING_MODE, 'R-ESRGAN 4x+')
        self.generator.upscale_image(self.image_stack.qimage(), UPSCALE_SIZE, self.status, self.status)
        self.assert_requests_match_snapshot('upscale_basic')
        self.assertEqual(self.status.emitted[-1].size(), UPSCALE_SIZE)

    def test_upscale_stable_diffusion(self) -> None:
        """Stable Diffusion upscaling sends img2img with a tile ControlNet unit and the Ultimate SD Upscale script."""
        cache = Cache()
        cache.set(Cache.EDIT_MODE, EDIT_MODE_IMG2IMG)
        cache.set(Cache.SCALING_MODE, 'R-ESRGAN 4x+')
        cache.set(Cache.SD_UPSCALING_AVAILABLE, True)
        cache.set(Cache.USE_STABLE_DIFFUSION_UPSCALING, True)
        cache.set(Cache.ULTIMATE_UPSCALE_SCRIPT_AVAILABLE, True)
        cache.set(Cache.USE_ULTIMATE_UPSCALE_SCRIPT, True)
        cache.set(Cache.SCRIPTS_IMG2IMG, [ULTIMATE_UPSCALE_SCRIPT])
        cache.set(Cache.SD_UPSCALING_DENOISING_STRENGTH, 0.25)
        cache.set(Cache.SD_UPSCALING_STEP_COUNT, 15)
        tile = get_all_preprocessors(['tile_resample'])[0]
        cache.set(Cache.SD_UPSCALING_CONTROLNET_TILE_SETTINGS,
                  self.controlnet_unit(ControlKeyType.WEBUI, TILE_MODEL, tile))
        self.generator.upscale_image(self.image_stack.qimage(), UPSCALE_SIZE, self.status, self.status)
        self.assert_requests_match_snapshot('upscale_stable_diffusion')
        self.assertEqual(self.status.emitted[-1].size(), UPSCALE_SIZE)
