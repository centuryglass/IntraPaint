"""Tests SDComfyUIGenerator's paths outside of a successful `generate`: backend option lists, cached option data,
settings, cancelling and failed requests, served offline by `FakeSdBackend`."""
from typing import Any
from unittest import mock

from sd_backend_client import BackendTimeoutError, ComfyUiWebservice, GenerationHandle, PREPROCESSOR_NONE, ServerError
from sd_backend_client.api.comfyui_webservice import ComfyEndpoints, ComfyModelType

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_generation.sd_comfyui_generator import SDComfyUIGenerator
from src.util.application_state import AppStateTracker, APP_STATE_EDITING, APP_STATE_LOADING
from src.util.shared_constants import EDIT_MODE_TXT2IMG, ERROR_MESSAGE_TIMEOUT
from test.controller.image_generation.fake_sd_backend import FakeResponse
from test.controller.image_generation.sd_comfyui_generator_test import OBJECT_INFO, CANNY_PREPROCESSOR, \
    CANNY_MODEL, TILE_MODEL, UPSCALE_MODEL, ULTIMATE_UPSCALE_NODE
from test.controller.image_generation.sd_generator_test_case import SdGeneratorTestCase

CHECKPOINTS = ['dreamshaper_8.safetensors', 'anything_v5.safetensors']
LORA_FILES = ['detail_lora.safetensors', 'no_extension']
MODEL_CONFIGS = ['v2-inference.yaml', 'v1-inference.yaml']
HYPERNETWORKS = ['zeta.pt', 'alpha.pt']
SAMPLERS = ['euler', 'dpmpp_2m']
SCHEDULERS = ['normal', 'karras']

KSAMPLER_INFO = {'KSampler': {
    'input': {'required': {'sampler_name': [SAMPLERS], 'scheduler': [SCHEDULERS]}},
    'input_order': {'required': ['sampler_name', 'scheduler']},
    'output': ['LATENT'],
    'output_is_list': [False],
    'output_name': ['LATENT'],
    'name': 'KSampler',
    'display_name': 'KSampler',
    'description': '',
    'python_module': 'nodes',
    'category': 'sampling',
    'output_node': False
}}


def _server_error(_arguments: dict[str, Any]) -> FakeResponse:
    return FakeResponse({'error': 'Internal Server Error'}, status_code=500)


def _models_endpoint(model_type: ComfyModelType) -> str:
    return f'{ComfyEndpoints.MODELS}/{model_type.value}'


class SDComfyUIGeneratorBackendTest(SdGeneratorTestCase):
    """Covers how the ComfyUI generator reads backend data and handles failed or cancelled jobs."""

    def setUp(self) -> None:
        super().setUp()
        backend = self.backend
        backend.route('GET', _models_endpoint(ComfyModelType.CHECKPOINT), CHECKPOINTS)
        backend.route('GET', _models_endpoint(ComfyModelType.LORA), LORA_FILES)
        backend.route('GET', _models_endpoint(ComfyModelType.CONFIG), MODEL_CONFIGS)
        backend.route('GET', _models_endpoint(ComfyModelType.HYPERNETWORKS), HYPERNETWORKS)
        backend.route('GET', _models_endpoint(ComfyModelType.UPSCALING), [UPSCALE_MODEL])
        backend.route('GET', _models_endpoint(ComfyModelType.CONTROLNET), [CANNY_MODEL, TILE_MODEL])
        backend.route('GET', ComfyEndpoints.OBJECT_INFO, OBJECT_INFO)
        # Nodes without their own route are missing:
        backend.route('GET', f'{ComfyEndpoints.OBJECT_INFO}/', {})
        backend.route('GET', f'{ComfyEndpoints.OBJECT_INFO}/KSampler', KSAMPLER_INFO)
        backend.route('GET', f'{ComfyEndpoints.OBJECT_INFO}/{ULTIMATE_UPSCALE_NODE}', {ULTIMATE_UPSCALE_NODE: {}})
        backend.route('POST', ComfyEndpoints.PROMPT, {'prompt_id': 'prompt-0', 'number': 1, 'node_errors': {}})
        backend.route('POST', ComfyEndpoints.FREE, {})

        generator = SDComfyUIGenerator(None, self.image_stack, self.server_args())  # type: ignore
        self.capture_generated_images(generator)
        self.generator = generator
        webservice = generator.get_webservice()
        assert isinstance(webservice, ComfyUiWebservice)
        self.webservice = webservice
        # Live progress reads the websocket on a background thread:
        webservice.progress_listener = None

    def _comfyui_generator(self) -> SDComfyUIGenerator:
        assert isinstance(self.generator, SDComfyUIGenerator)
        return self.generator

    def test_backend_lists(self) -> None:
        """Each option getter returns the names ComfyUI lists, with LoRA names taken from their file names."""
        generator = self._comfyui_generator()
        self.assertEqual(generator.get_diffusion_model_names(), CHECKPOINTS)
        self.assertEqual(generator.get_diffusion_sampler_names(), SAMPLERS)
        self.assertEqual(generator.get_upscale_method_names(), [UPSCALE_MODEL])
        self.assertEqual(generator.get_lora_model_info(), [
            {'name': 'detail_lora', 'alias': 'detail_lora', 'path': 'detail_lora.safetensors'},
            {'name': 'no_extension', 'alias': 'no_extension', 'path': 'no_extension'}])
        self.assertEqual(generator.get_controlnet_models(), [CANNY_MODEL, TILE_MODEL])
        self.assertTrue(generator.ultimate_upscale_script_available())
        self.assertIsNone(generator.load_lora_thumbnail(generator.get_lora_model_info()[0]))

    def test_controlnet_preprocessors_include_none(self) -> None:
        """The preprocessor list always offers the no-op preprocessor, after the preprocessors ComfyUI has."""
        names = [preprocessor.name for preprocessor in self._comfyui_generator().get_controlnet_preprocessors()]
        self.assertIn(CANNY_PREPROCESSOR, names)
        self.assertEqual(names[-1], PREPROCESSOR_NONE)
        self.assertEqual(names.count(PREPROCESSOR_NONE), 1)
        self.assertGreater(len(self._comfyui_generator().get_controlnet_types()), 0)

    def test_backend_list_failures_return_empty(self) -> None:
        """A failed query leaves its option list empty instead of raising."""
        generator = self._comfyui_generator()
        for endpoint in (_models_endpoint(ComfyModelType.CHECKPOINT), _models_endpoint(ComfyModelType.LORA),
                         _models_endpoint(ComfyModelType.UPSCALING), _models_endpoint(ComfyModelType.CONTROLNET),
                         ComfyEndpoints.OBJECT_INFO, f'{ComfyEndpoints.OBJECT_INFO}/KSampler',
                         f'{ComfyEndpoints.OBJECT_INFO}/{ULTIMATE_UPSCALE_NODE}', f'{ComfyEndpoints.OBJECT_INFO}/'):
            self.backend.route('GET', endpoint, _server_error)
        self.assert_backend_lists_empty(generator)

    def test_cache_generator_specific_data(self) -> None:
        """Model configs join the default options, hypernetworks are cached sorted, and schedulers replace the
        defaults."""
        self._comfyui_generator().cache_generator_specific_data()
        cache = Cache()
        self.assertEqual(cache.get_options(Cache.COMFYUI_MODEL_CONFIG), ['auto', *sorted(MODEL_CONFIGS)])
        self.assertEqual(cache.get(Cache.HYPERNETWORK_MODELS), sorted(HYPERNETWORKS))
        self.assertEqual(cache.get_options(Cache.SCHEDULER), SCHEDULERS)

    def test_cache_generator_specific_data_failures_restore_defaults(self) -> None:
        """Failed queries leave each option list at its defaults, and clearing restores the config options."""
        generator = self._comfyui_generator()
        generator.cache_generator_specific_data()
        for endpoint in (_models_endpoint(ComfyModelType.CONFIG), _models_endpoint(ComfyModelType.HYPERNETWORKS),
                         f'{ComfyEndpoints.OBJECT_INFO}/KSampler'):
            self.backend.route('GET', endpoint, _server_error)
        # The webservice caches KSampler data after the first read:
        self.webservice._ksampler_info = None  # pylint: disable=protected-access
        generator.cache_generator_specific_data()
        cache = Cache()
        self.assertEqual(cache.get_options(Cache.COMFYUI_MODEL_CONFIG), ['auto'])
        self.assertEqual(cache.get(Cache.HYPERNETWORK_MODELS), [])
        self.assertEqual(cache.get_options(Cache.SCHEDULER), ['default'])

        self.backend.route('GET', _models_endpoint(ComfyModelType.CONFIG), MODEL_CONFIGS)
        generator.cache_generator_specific_data()
        generator.clear_cached_generator_data()
        self.assertEqual(cache.get_options(Cache.COMFYUI_MODEL_CONFIG), ['auto'])

    def test_update_settings_applies_stable_diffusion_app_settings(self) -> None:
        """Stable Diffusion app settings are set, and other changes are left to the caller."""
        self._comfyui_generator().update_settings({AppConfig.MASK_BLUR: 9, AppConfig.MAX_UNDO: 3})
        self.assertEqual(AppConfig().get(AppConfig.MASK_BLUR), 9)
        self.assertNotEqual(AppConfig().get(AppConfig.MAX_UNDO), 3)
        self.assertEqual(self.backend.requests, [])

    def test_describe_is_unsupported(self) -> None:
        """ComfyUI has no image description, so describe raises."""
        with self.assertRaises(RuntimeError):
            self._comfyui_generator().describe()

    def test_clear_memory(self) -> None:
        """Clearing memory asks ComfyUI to unload models and free memory."""
        self._comfyui_generator().clear_comfyui_memory()
        self.assertEqual(self.backend.posts()[-1].arguments['body'], {'unload_models': True, 'free_memory': True})

    def test_generate_server_error_raises(self) -> None:
        """A rejected job raises a RuntimeError naming the failed request, and no image is cached."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_TXT2IMG)
        self.backend.route('POST', ComfyEndpoints.PROMPT, _server_error)
        with self.assertRaisesRegex(RuntimeError, 'request failed') as context:
            self.run_generate()
        self.assertIsInstance(context.exception.__cause__, ServerError)
        self.assertEqual(self.generated_images, {})

    def test_generate_failed_job_raises(self) -> None:
        """A job ComfyUI reports as failed raises a RuntimeError, and no seed is reported."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_TXT2IMG)
        self.backend.route('GET', f'{ComfyEndpoints.HISTORY}/', {'prompt-0': {
            'prompt': [1, 'prompt-0', {}, {}, []],
            'status': {'status_str': 'error', 'completed': False, 'messages': []},
            'outputs': {}}})
        with self.assertRaisesRegex(RuntimeError, 'request failed'):
            self.run_generate()
        self.assertEqual(self.generated_images, {})
        self.assertFalse(any('seed' in update for update in self.status.emitted))

    def test_generate_timeout_raises_timeout_message(self) -> None:
        """A request that times out raises a RuntimeError with the timeout message."""
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_TXT2IMG)

        def _timeout(_arguments: dict[str, Any]) -> None:
            raise BackendTimeoutError('POST /prompt timed out')
        self.backend.route('POST', ComfyEndpoints.PROMPT, _timeout)
        with self.assertRaisesRegex(RuntimeError, ERROR_MESSAGE_TIMEOUT):
            self.run_generate()

    def test_cancel_outside_generation_does_nothing(self) -> None:
        """Cancelling cancels only a job being waited on while the app is loading."""
        generator = self._comfyui_generator()
        handle = mock.MagicMock(spec=GenerationHandle)
        generator.cancel_generation()
        generator._active_handle = handle  # pylint: disable=protected-access
        AppStateTracker.set_app_state(APP_STATE_EDITING)
        generator.cancel_generation()
        handle.cancel.assert_not_called()

    def test_failed_cancel_is_logged(self) -> None:
        """A cancel request the backend rejects is logged instead of raised."""
        generator = self._comfyui_generator()
        handle = mock.MagicMock(spec=GenerationHandle)
        handle.task_id = 'job'
        handle.cancel.side_effect = ServerError(500, 'no', ComfyEndpoints.INTERRUPT, 'POST')
        generator._active_handle = handle  # pylint: disable=protected-access
        AppStateTracker.set_app_state(APP_STATE_LOADING)
        self.addCleanup(AppStateTracker.set_app_state, APP_STATE_EDITING)
        with self.assertLogs('src.controller.image_generation.sd_generator', 'ERROR'):
            generator.cancel_generation()
        handle.cancel.assert_called_once()
