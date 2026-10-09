"""Pins the requests SDComfyUIGenerator sends to ComfyUI, including workflow node graphs, using JSON snapshots.

See sd_generator_test_case.py for how the snapshots work.
"""
from typing import Any, Optional
from unittest import mock

from PySide6.QtCore import Qt
from sd_backend_client import ComfyUiWebservice, GenerationError, GenerationHandle, GenerationProgress, \
    GenerationResult, GenerationStatus
from sd_backend_client.api.comfyui_webservice import ComfyEndpoints, ComfyModelType

from src.api.controlnet.controlnet_preprocessor import ControlNetPreprocessor
from src.api.controlnet.controlnet_unit import ControlKeyType
from src.config.cache import Cache
from src.controller.image_generation.sd_comfyui_generator import SDComfyUIGenerator
from src.util.application_state import AppStateTracker, APP_STATE_LOADING, APP_STATE_EDITING
from src.util.shared_constants import EDIT_MODE_TXT2IMG, EDIT_MODE_IMG2IMG, EDIT_MODE_INPAINT
from test.controller.image_generation.fake_sd_backend import FakeResponse, image_to_png_bytes
from test.controller.image_generation.sd_generator_test_case import SdGeneratorTestCase, TEST_SEED, UPSCALE_SIZE, \
    LORA_FILE, solid_image, CONTEXT_PIN

CANNY_PREPROCESSOR = 'CannyEdgePreprocessor'
TILE_PREPROCESSOR = 'TilePreprocessor'
CANNY_MODEL = 'control_v11p_sd15_canny_fp16.safetensors'
TILE_MODEL = 'control_v11f1e_sd15_tile_fp16.safetensors'
UPSCALE_MODEL = '4x-UltraSharp.pth'
MODEL_CONFIG = 'v1-inference.yaml'
SAVE_IMAGE_NODE_ID = '9'
ULTIMATE_UPSCALE_NODE = 'UltimateSDUpscale'


def _int_input(default: int, minimum: int, maximum: int, step: int) -> list[Any]:
    return ['INT', {'default': default, 'min': minimum, 'max': maximum, 'step': step}]


def _preprocessor_node_info(name: str, inputs: dict[str, list[Any]]) -> dict[str, Any]:
    """Returns /object_info data for a ControlNet preprocessor node with an image input."""
    return {
        'input': {'required': {'image': ['IMAGE'], **inputs}},
        'input_order': {'required': ['image', *inputs]},
        'output': ['IMAGE'],
        'output_is_list': [False],
        'output_name': ['IMAGE'],
        'name': name,
        'display_name': name,
        'description': '',
        'python_module': 'custom_nodes.comfyui_controlnet_aux',
        'category': 'ControlNet Preprocessors/Line Extractors',
        'output_node': False
    }


OBJECT_INFO = {
    CANNY_PREPROCESSOR: _preprocessor_node_info(CANNY_PREPROCESSOR, {
        'low_threshold': _int_input(100, 0, 255, 1),
        'high_threshold': _int_input(200, 0, 255, 1),
        'resolution': _int_input(512, 64, 16384, 64)
    }),
    TILE_PREPROCESSOR: _preprocessor_node_info(TILE_PREPROCESSOR, {
        'pyrUp_iters': _int_input(3, 1, 10, 1),
        'resolution': _int_input(512, 64, 16384, 64)
    })
}


class _CancelledWhileWaitingHandle(GenerationHandle):
    """A job that the generator cancels while waiting on it, reporting it as cancelled once it is."""

    def __init__(self, generator: SDComfyUIGenerator) -> None:
        super().__init__('cancelled-job')
        self._generator = generator
        self.cancelled = False

    def poll(self) -> GenerationProgress:
        return GenerationProgress(GenerationStatus.CANCELLED if self.cancelled else GenerationStatus.ACTIVE)

    def _build_result(self) -> GenerationResult:
        raise AssertionError('a cancelled job has no result')

    def cancel(self) -> bool:
        self.cancelled = True
        return True

    def wait(self, timeout: Optional[float] = None, poll_interval: float = 0.5,
             on_progress: Optional[Any] = None) -> GenerationResult:
        self._generator.cancel_generation()
        raise GenerationError(self.poll().status)


class SDComfyUIGeneratorTest(SdGeneratorTestCase):
    """Snapshots ComfyUI uploads and queued workflows for generation, inpainting, ControlNet and upscaling."""

    snapshot_subdir = 'comfyui'

    def setUp(self) -> None:
        super().setUp()
        cache = Cache()
        cache.set(Cache.SAMPLING_METHOD, 'euler_ancestral', add_missing_options=True)
        cache.set(Cache.SCHEDULER, 'karras', add_missing_options=True)
        cache.set(Cache.GENERATOR_SCALING_MODES, [UPSCALE_MODEL])
        cache.set(Cache.SCALING_MODE, UPSCALE_MODEL)
        self._queued_prompts: list[str] = []
        self._image_size = cache.get(Cache.GENERATION_SIZE)

        backend = self.backend
        backend.route('POST', ComfyEndpoints.IMG_UPLOAD, self._upload_response)
        backend.route('POST', ComfyEndpoints.MASK_UPLOAD, self._upload_response)
        backend.route('POST', ComfyEndpoints.PROMPT, self._queue_response)
        backend.route('GET', f'{ComfyEndpoints.HISTORY}/', self._history_response)
        backend.route('GET', ComfyEndpoints.VIEW_IMAGE,
                      lambda _args: FakeResponse(content=image_to_png_bytes(solid_image(self._image_size,
                                                                                        Qt.GlobalColor.blue))))
        backend.route('GET', f'{ComfyEndpoints.MODELS}/{ComfyModelType.CONFIG.value}', [MODEL_CONFIG])
        backend.route('GET', f'{ComfyEndpoints.MODELS}/{ComfyModelType.CONTROLNET.value}', [CANNY_MODEL, TILE_MODEL])
        backend.route('GET', f'{ComfyEndpoints.MODELS}/{ComfyModelType.LORA.value}', [LORA_FILE])
        backend.route('GET', f'{ComfyEndpoints.MODELS}/{ComfyModelType.UPSCALING.value}', [UPSCALE_MODEL])
        backend.route('GET', ComfyEndpoints.OBJECT_INFO, OBJECT_INFO)
        backend.route('GET', f'{ComfyEndpoints.OBJECT_INFO}/{ULTIMATE_UPSCALE_NODE}', {ULTIMATE_UPSCALE_NODE: {}})

        generator = SDComfyUIGenerator(None, self.image_stack, self.server_args())  # type: ignore
        self.capture_generated_images(generator)
        self.generator = generator
        webservice = generator.get_webservice()
        assert isinstance(webservice, ComfyUiWebservice)
        # Live progress reads the websocket on a background thread:
        webservice.progress_listener = None
        self._replacements = {webservice._client_id: '<client id>'}  # pylint: disable=protected-access

    @staticmethod
    def _upload_response(arguments: dict[str, Any]) -> dict[str, Any]:
        file_name = next(iter(arguments['files'].values()))[0]
        return {'name': file_name, 'subfolder': arguments['body']['subfolder'], 'type': 'input'}

    def _queue_response(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        prompt_id = f'prompt-{len(self._queued_prompts)}'
        self._queued_prompts.append(prompt_id)
        return {'prompt_id': prompt_id, 'number': len(self._queued_prompts), 'node_errors': {}}

    def _history_response(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        prompt_id = self._queued_prompts[-1]
        batch_size = Cache().get(Cache.BATCH_SIZE)
        images = [{'filename': f'{prompt_id}_{i}.png', 'subfolder': '', 'type': 'output'} for i in range(batch_size)]
        return {prompt_id: {'prompt': [len(self._queued_prompts), prompt_id, {}, {}, [SAVE_IMAGE_NODE_ID]],
                            'status': {'status_str': 'success', 'completed': True, 'messages': []},
                            'outputs': {SAVE_IMAGE_NODE_ID: {'images': images}}}}

    def _preprocessor(self, name: str) -> ControlNetPreprocessor:
        """Returns a preprocessor as the ControlNet panel receives it."""
        assert isinstance(self.generator, SDComfyUIGenerator)
        return next(preprocessor for preprocessor in self.generator.get_controlnet_preprocessors()
                    if preprocessor.name == name)

    def _set_canny_controlnet_unit(self) -> None:
        Cache().set(Cache.CONTROLNET_ARGS_0_COMFYUI,
                    self.controlnet_unit(ControlKeyType.COMFYUI, CANNY_MODEL, self._preprocessor(CANNY_PREPROCESSOR)))

    def _generate_and_check(self, snapshot_name: str) -> None:
        self.run_generate()
        self.assert_requests_match_snapshot(snapshot_name, replacements=self._replacements)
        self.assertEqual(len(self.generated_images), 4)
        self.assertEqual(self.status.emitted[-1], {'seed': str(TEST_SEED)})

    def _run_upscale(self) -> None:
        assert isinstance(self.generator, SDComfyUIGenerator)
        self._image_size = UPSCALE_SIZE
        Cache().set(Cache.BATCH_SIZE, 1)
        self.generator.upscale_image(self.image_stack.qimage(), UPSCALE_SIZE, self.status, self.status)
        self.assertEqual(self.status.emitted[-1].size(), UPSCALE_SIZE)

    def test_txt2img(self) -> None:
        """Text to image queues one workflow per batch, with consecutive seeds and no uploads."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_TXT2IMG)
        self._generate_and_check('txt2img')

    def test_txt2img_controlnet_reusing_generation_area(self) -> None:
        """A ControlNet unit reusing the generation area uploads it once, and every batch reuses the upload."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_TXT2IMG)
        self._set_canny_controlnet_unit()
        self._generate_and_check('txt2img_controlnet')

    def test_img2img(self) -> None:
        """Image to image uploads the generation area once and loads it in every batch's workflow."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_IMG2IMG)
        self._generate_and_check('img2img')

    def test_inpaint(self) -> None:
        """Inpainting uploads the image and a blurred, inverted mask once, then reuses both."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_INPAINT)
        self._generate_and_check('inpaint')

    def test_inpaint_full_res(self) -> None:
        """Inpainting at full resolution uploads the selection bounds cropped and scaled to the generation size."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_INPAINT)
        Cache().set(Cache.INPAINT_FULL_RES, True)
        self._generate_and_check('inpaint_full_res')

    def test_inpaint_full_res_context_pin(self) -> None:
        """A context pin stretches the uploaded full-res crop past the selection bounds."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_INPAINT)
        Cache().set(Cache.INPAINT_FULL_RES, True)
        self.image_stack.selection_layer.add_context_pin(CONTEXT_PIN)
        self._generate_and_check('inpaint_full_res_context_pin')

    def test_inpaint_controlnet_reusing_generation_area(self) -> None:
        """A ControlNet unit reusing the generation area uses the uploaded inpainting image."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_INPAINT)
        self._set_canny_controlnet_unit()
        self._generate_and_check('inpaint_controlnet')

    def test_upscale_basic(self) -> None:
        """Upscaling without Stable Diffusion queues an upscaling model workflow."""
        self._run_upscale()
        self.assert_requests_match_snapshot('upscale_basic', replacements=self._replacements)

    def test_upscale_stable_diffusion(self) -> None:
        """Stable Diffusion upscaling queues a tiled Ultimate SD Upscale workflow with a tile ControlNet unit."""
        cache = Cache()
        cache.set(Cache.EDIT_MODE, EDIT_MODE_IMG2IMG)
        cache.set(Cache.SD_UPSCALING_AVAILABLE, True)
        cache.set(Cache.USE_STABLE_DIFFUSION_UPSCALING, True)
        cache.set(Cache.ULTIMATE_UPSCALE_SCRIPT_AVAILABLE, True)
        cache.set(Cache.USE_ULTIMATE_UPSCALE_SCRIPT, True)
        cache.set(Cache.SD_UPSCALING_DENOISING_STRENGTH, 0.25)
        cache.set(Cache.SD_UPSCALING_STEP_COUNT, 15)
        cache.set(Cache.SD_UPSCALING_CONTROLNET_TILE_SETTINGS,
                  self.controlnet_unit(ControlKeyType.COMFYUI, TILE_MODEL, self._preprocessor(TILE_PREPROCESSOR)))
        self._run_upscale()
        self.assert_requests_match_snapshot('upscale_stable_diffusion', replacements=self._replacements)

    def test_preprocessor_preview(self) -> None:
        """A preview queues the preprocessor alone, with the panel's parameter values, and returns its one image."""
        assert isinstance(self.generator, SDComfyUIGenerator)
        Cache().set(Cache.BATCH_SIZE, 1)
        preprocessor = self._preprocessor(CANNY_PREPROCESSOR)
        preprocessor.set_value('low_threshold', 80)
        image, mask = self.generator.get_generation_inputs()
        self.generator.load_preprocessor_preview(preprocessor, self.generator.get_gen_area_image(image),
                                                 self.generator.get_gen_area_mask(mask), self.status, self.status)
        self.assert_requests_match_snapshot('preprocessor_preview', replacements=self._replacements)
        self.assertEqual(self.status.emitted[-1].size(), self._image_size)

    def test_cancel_stops_generation(self) -> None:
        """Cancelling while a batch runs cancels its job, and generation ends without images or an error."""
        assert isinstance(self.generator, SDComfyUIGenerator)
        webservice = self.generator.get_webservice()
        assert webservice is not None
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_TXT2IMG)
        handle = _CancelledWhileWaitingHandle(self.generator)
        AppStateTracker.set_app_state(APP_STATE_LOADING)
        self.addCleanup(AppStateTracker.set_app_state, APP_STATE_EDITING)
        with mock.patch.object(webservice, 'submit_txt2img', return_value=handle) as submit:
            self.run_generate()
        submit.assert_called_once()
        self.assertTrue(handle.cancelled)
        self.assertEqual(self.generated_images, {})
        self.assertNotIn({'seed': str(TEST_SEED)}, self.status.emitted)
