"""Tests SDWebUIGenerator's paths outside of `generate`: backend option lists, WebUI settings sync, settings updates
and describe, served offline by `FakeSdBackend`."""
import json
from typing import Any
from unittest import mock

from PySide6.QtCore import Qt
from sd_backend_client import A1111Webservice
from sd_backend_client.api.a1111_webservice import ULTIMATE_UPSCALE_SCRIPT

from src.config.a1111_config import A1111Config
from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_generation.sd_webui_generator import SDWebUIGenerator
from src.undo_stack import UndoStack
from src.util.application_state import AppStateTracker, APP_STATE_EDITING, APP_STATE_NO_IMAGE
from src.util.async_task import AsyncTask
from src.util.shared_constants import DESCRIBE_ERROR_TITLE, DESCRIBE_ERROR_MESSAGE_NO_IMAGE
from src.util.singleton import Singleton
from test.controller.image_generation.fake_sd_backend import FakeResponse, image_to_png_bytes
from test.controller.image_generation.sd_generator_test_case import SdGeneratorTestCase, solid_image

Endpoints = A1111Webservice.Endpoints

MODEL_FILES = ['dreamshaper_8.safetensors', 'anything_v5.safetensors']
MODEL_NAMES = ['dreamshaper_8', 'anything_v5']
MODEL_TITLES = ['dreamshaper_8.safetensors [879db523c3]', 'anything_v5.safetensors [7f96a1a9ca]']
SAMPLER_NAMES = ['Euler a', 'DPM++ 2M']
UPSCALER_NAMES = ['None', 'Lanczos', 'R-ESRGAN 4x+']
CONTROLNET_MODELS = ['control_v11p_sd15_canny [d14c016b]', 'control_v11f1e_sd15_tile [a371b31b]']
LORA = {'name': 'detail_lora', 'alias': 'detail', 'path': '/models/Lora/detail_lora.safetensors'}
STYLE = {'name': 'cinematic', 'prompt': 'cinematic {prompt}', 'negative_prompt': 'cartoon'}
CAPTION = 'a lighthouse on a rocky cliff'
INTERROGATE_MODEL = 'deepdanbooru'


def _server_error(_arguments: dict[str, Any]) -> FakeResponse:
    return FakeResponse({'detail': 'Internal Server Error'}, status_code=500)


class SDWebUIGeneratorBackendTest(SdGeneratorTestCase):
    """Covers how the WebUI generator reads backend data, keeps WebUI settings in sync, and describes images."""

    def setUp(self) -> None:
        super().setUp()
        # A1111Config normally exists only once the WebUI generator connects (see reset_singletons):
        if A1111Config not in Singleton._instances:  # pylint: disable=protected-access
            self.addCleanup(Singleton._instances.pop, A1111Config, None)  # pylint: disable=protected-access
        A1111Config()  # Sets the A1111Config key constants.
        self.remote_options: dict[str, Any] = {A1111Config.SD_MODEL_CHECKPOINT: MODEL_TITLES[0],
                                               A1111Config.CLIP_STOP_AT_LAST_LAYERS: 1,
                                               'some_unused_option': True}
        backend = self.backend
        backend.route('GET', Endpoints.OPTIONS, lambda _args: dict(self.remote_options))
        backend.route('POST', Endpoints.OPTIONS, self._set_options)
        backend.route('GET', Endpoints.SD_MODELS, [
            {'title': title, 'model_name': name, 'filename': f'/models/Stable-diffusion/{file}'}
            for title, name, file in zip(MODEL_TITLES, MODEL_NAMES, MODEL_FILES)])
        backend.route('GET', Endpoints.VAE_MODELS, [{'model_name': 'vae-ft-mse', 'filename': '/models/VAE/vae.pt'}])
        backend.route('GET', Endpoints.SAMPLERS, [{'name': name, 'aliases': [], 'options': {}}
                                                  for name in SAMPLER_NAMES])
        backend.route('GET', Endpoints.UPSCALERS, [{'name': name, 'model_name': None, 'model_path': None,
                                                    'model_url': None, 'scale': 4.0} for name in UPSCALER_NAMES])
        backend.route('GET', Endpoints.LORA_MODELS, [LORA])
        backend.route('GET', Endpoints.SCRIPTS, {'txt2img': ['x/y/z plot'],
                                                 'img2img': ['x/y/z plot', ULTIMATE_UPSCALE_SCRIPT]})
        backend.route('GET', Endpoints.STYLES, [STYLE])
        backend.route('GET', Endpoints.CONTROLNET_MODELS, {'model_list': CONTROLNET_MODELS})
        backend.route('GET', Endpoints.CONTROLNET_MODULES, {'module_list': ['none', 'canny', 'tile_resample']})
        backend.route('GET', Endpoints.CONTROLNET_CONTROL_TYPES, _server_error)
        backend.route('GET', Endpoints.SCHEDULERS, [{'name': 'karras', 'label': 'Karras'}])
        backend.route('POST', Endpoints.INTERROGATE, {'caption': CAPTION})
        # The capability check probes the POST-only route with a GET:
        backend.route('GET', Endpoints.INTERROGATE, FakeResponse({'detail': 'Method Not Allowed'}, status_code=405))

        self.generator = SDWebUIGenerator(None, self.image_stack, self.server_args())  # type: ignore
        start_patch = mock.patch.object(AsyncTask, 'start', AsyncTask.run)
        start_patch.start()
        self.addCleanup(start_patch.stop)
        error_dialog_patch = mock.patch('src.controller.image_generation.sd_webui_generator.show_error_dialog')
        self.show_error_dialog = error_dialog_patch.start()
        self.addCleanup(error_dialog_patch.stop)

    def _set_options(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.remote_options.update(arguments['body'])
        return {}

    def _option_posts(self) -> list[dict[str, Any]]:
        return [request.arguments['body'] for request in self.backend.posts() if request.endpoint == Endpoints.OPTIONS]

    def _connect_settings(self) -> None:
        """Caches the WebUI data `configure_or_connect` would, and marks the generator connected."""
        assert isinstance(self.generator, SDWebUIGenerator)
        Cache().update_options(Cache.SD_MODEL, MODEL_NAMES)
        self.generator.cache_generator_specific_data()
        self.generator._connected = True  # pylint: disable=protected-access

    def test_backend_lists(self) -> None:
        """Each option getter returns the names the WebUI lists, in the form the generator caches."""
        generator = self.generator
        assert isinstance(generator, SDWebUIGenerator)
        self.assertEqual(generator.get_diffusion_model_names(), MODEL_NAMES)
        self.assertEqual(generator.get_diffusion_sampler_names(), SAMPLER_NAMES)
        self.assertEqual(generator.get_upscale_method_names(), UPSCALER_NAMES)
        self.assertEqual(generator.get_lora_model_info(), [{**LORA, 'metadata': {}}])
        self.assertEqual(generator.get_controlnet_models(), CONTROLNET_MODELS)
        self.assertEqual([preprocessor.name for preprocessor in generator.get_controlnet_preprocessors()],
                         ['none', 'canny', 'tile_resample'])
        self.assertIn('Canny', generator.get_controlnet_types())
        self.assertTrue(generator.ultimate_upscale_script_available())

    def test_backend_list_failures_return_empty(self) -> None:
        """A failed query leaves its option list empty instead of raising."""
        generator = self.generator
        assert isinstance(generator, SDWebUIGenerator)
        for endpoint in (Endpoints.SD_MODELS, Endpoints.SAMPLERS, Endpoints.UPSCALERS, Endpoints.LORA_MODELS,
                         Endpoints.SCRIPTS, Endpoints.CONTROLNET_MODELS, Endpoints.CONTROLNET_MODULES):
            self.backend.route('GET', endpoint, _server_error)
        self.assert_backend_lists_empty(generator)

    def test_cache_generator_specific_data(self) -> None:
        """Connecting copies the WebUI's model and clip skip into the cache, and caches its scripts and styles."""
        self.remote_options[A1111Config.SD_MODEL_CHECKPOINT] = MODEL_TITLES[1]
        self.remote_options[A1111Config.CLIP_STOP_AT_LAST_LAYERS] = 2
        self._connect_settings()
        cache = Cache()
        self.assertEqual(cache.get(Cache.SD_MODEL), MODEL_NAMES[1])
        self.assertEqual(cache.get(Cache.CLIP_SKIP), 2)
        self.assertEqual(A1111Config().get_options(A1111Config.SD_MODEL_CHECKPOINT), MODEL_TITLES)
        self.assertEqual(cache.get(Cache.SCRIPTS_TXT2IMG), ['x/y/z plot'])
        self.assertEqual(cache.get(Cache.SCRIPTS_IMG2IMG), ['x/y/z plot', ULTIMATE_UPSCALE_SCRIPT])
        self.assertEqual([json.loads(style) for style in cache.get(Cache.STYLES)], [STYLE])
        self.assertTrue(cache.get(Cache.WEBUI_TILING_AVAILABLE))
        self.assertEqual(self._option_posts(), [])

    def test_cache_generator_specific_data_survives_failed_queries(self) -> None:
        """A failed settings query skips the settings sync, and failed script or style queries skip only those."""
        for endpoint in (Endpoints.OPTIONS, Endpoints.SCRIPTS):
            self.backend.route('GET', endpoint, _server_error)
        self._connect_settings()
        cache = Cache()
        self.assertEqual(cache.get(Cache.SCRIPTS_IMG2IMG), [])
        self.assertEqual(len(cache.get(Cache.STYLES)), 1)
        self.assertEqual(self._option_posts(), [])

    def test_local_model_and_clip_skip_changes_reach_the_webui(self) -> None:
        """Choosing a model or clip skip in IntraPaint sends the matching WebUI setting, once each."""
        self._connect_settings()
        cache = Cache()
        cache.set(Cache.SD_MODEL, MODEL_NAMES[1])
        cache.set(Cache.CLIP_SKIP, 3)
        posts = self._option_posts()
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0][A1111Config.SD_MODEL_CHECKPOINT], MODEL_TITLES[1])
        self.assertEqual(posts[1][A1111Config.CLIP_STOP_AT_LAST_LAYERS], 3)
        self.assertEqual(A1111Config().get(A1111Config.SD_MODEL_CHECKPOINT), MODEL_TITLES[1])
        self.assertEqual(A1111Config().get(A1111Config.CLIP_STOP_AT_LAST_LAYERS), 3)

    def test_webui_setting_changes_reach_the_cache_without_echo(self) -> None:
        """A model or clip skip change loaded from the WebUI updates the cached selection and sends nothing back."""
        self._connect_settings()
        self.remote_options[A1111Config.SD_MODEL_CHECKPOINT] = MODEL_TITLES[1]
        self.remote_options[A1111Config.CLIP_STOP_AT_LAST_LAYERS] = 4
        assert isinstance(self.generator, SDWebUIGenerator)
        webservice = self.generator.get_webservice()
        assert webservice is not None
        A1111Config().load_all(webservice)
        self.assertEqual(Cache().get(Cache.SD_MODEL), MODEL_NAMES[1])
        self.assertEqual(Cache().get(Cache.CLIP_SKIP), 4)
        self.assertEqual(self._option_posts(), [])

    def test_disconnected_generator_ignores_setting_changes(self) -> None:
        """Once disconnected, the sync callbacks change nothing in either direction."""
        self._connect_settings()
        assert isinstance(self.generator, SDWebUIGenerator)
        self.generator._connected = False  # pylint: disable=protected-access
        Cache().set(Cache.SD_MODEL, MODEL_NAMES[1])
        Cache().set(Cache.CLIP_SKIP, 5)
        A1111Config().set(A1111Config.CLIP_STOP_AT_LAST_LAYERS, 6)
        self.assertEqual(self._option_posts(), [])
        self.assertEqual(Cache().get(Cache.CLIP_SKIP), 5)

    def test_reconnecting_replaces_sync_connections(self) -> None:
        """Caching the WebUI data again leaves one connection per setting, so each change is sent once."""
        self._connect_settings()
        self._connect_settings()
        Cache().set(Cache.CLIP_SKIP, 3)
        self.assertEqual(len(self._option_posts()), 1)

    def test_update_settings_applies_webui_and_app_changes(self) -> None:
        """Only WebUI settings are sent to the WebUI, and stored once it accepts them. App settings are set locally."""
        self._connect_settings()
        self.image_stack.flush_render()
        assert isinstance(self.generator, SDWebUIGenerator)
        self.generator.update_settings({A1111Config.CLIP_STOP_AT_LAST_LAYERS: 2, AppConfig.MASK_BLUR: 9})
        self.assertEqual(self._option_posts(), [{A1111Config.CLIP_STOP_AT_LAST_LAYERS: 2}])
        self.assertEqual(A1111Config().get(A1111Config.CLIP_STOP_AT_LAST_LAYERS), 2)
        self.assertEqual(Cache().get(Cache.CLIP_SKIP), 2)
        self.assertEqual(AppConfig().get(AppConfig.MASK_BLUR), 9)
        self.assertEqual(AppStateTracker.app_state(), APP_STATE_EDITING)
        self.show_error_dialog.assert_not_called()

    def test_update_settings_without_webui_changes_sends_nothing(self) -> None:
        """App-only changes are set locally without contacting the WebUI."""
        assert isinstance(self.generator, SDWebUIGenerator)
        self.generator.update_settings({AppConfig.MASK_BLUR: 9})
        self.assertEqual(AppConfig().get(AppConfig.MASK_BLUR), 9)
        self.assertEqual(self.backend.requests, [])

    def test_update_settings_failure_keeps_old_values(self) -> None:
        """A rejected update shows an error, leaves the loading state and keeps the local WebUI settings."""
        self._connect_settings()
        self.backend.route('POST', Endpoints.OPTIONS, _server_error)
        assert isinstance(self.generator, SDWebUIGenerator)
        self.image_stack.remove_layer(self.image_stack.active_layer)
        self.generator.update_settings({A1111Config.CLIP_STOP_AT_LAST_LAYERS: 2})
        self.show_error_dialog.assert_called_once()
        self.assertEqual(A1111Config().get(A1111Config.CLIP_STOP_AT_LAST_LAYERS), 1)
        self.assertEqual(AppStateTracker.app_state(), APP_STATE_NO_IMAGE)

    def test_describe_sets_prompt_as_one_undo_step(self) -> None:
        """Describe sends the generation area with the configured model, and the caption replaces the prompt."""
        AppConfig().set(AppConfig.INTERROGATE_MODEL, INTERROGATE_MODEL)
        assert isinstance(self.generator, SDWebUIGenerator)
        old_prompt = Cache().get(Cache.PROMPT)
        UndoStack().clear()
        self.generator.describe()
        body = self.backend.posts()[0].arguments['body']
        self.assertEqual(body['model'], INTERROGATE_MODEL)
        self.assertEqual(Cache().get(Cache.PROMPT), CAPTION)
        self.assertEqual(AppStateTracker.app_state(), APP_STATE_EDITING)
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assertEqual(Cache().get(Cache.PROMPT), old_prompt)

    def test_describe_without_image_shows_error(self) -> None:
        """With no image layers, describe shows an error without contacting the WebUI."""
        self.image_stack.remove_layer(self.image_stack.active_layer)
        assert isinstance(self.generator, SDWebUIGenerator)
        self.generator.describe()
        self.show_error_dialog.assert_called_once_with(None, DESCRIBE_ERROR_TITLE, DESCRIBE_ERROR_MESSAGE_NO_IMAGE)
        self.assertEqual(self.backend.requests, [])

    def test_describe_failure_shows_error_and_keeps_prompt(self) -> None:
        """A failed describe request shows an error, returns to editing and leaves the prompt alone."""
        self.backend.route('POST', Endpoints.INTERROGATE, _server_error)
        assert isinstance(self.generator, SDWebUIGenerator)
        self.generator._window = mock.MagicMock()  # pylint: disable=protected-access
        old_prompt = Cache().get(Cache.PROMPT)
        self.generator.describe()
        self.show_error_dialog.assert_called_once()
        self.assertEqual(self.show_error_dialog.call_args.args[1], DESCRIBE_ERROR_TITLE)
        self.assertEqual(Cache().get(Cache.PROMPT), old_prompt)
        self.assertEqual(AppStateTracker.app_state(), APP_STATE_EDITING)

    def test_lora_thumbnail(self) -> None:
        """A LoRA thumbnail is requested by the model path with a .png extension."""
        assert isinstance(self.generator, SDWebUIGenerator)
        self.backend.route('GET', Endpoints.EXTRA_NW_THUMB,
                           FakeResponse(content=image_to_png_bytes(solid_image(self.image_stack.size,
                                                                               Qt.GlobalColor.red))))
        thumbnail = self.generator.load_lora_thumbnail(LORA)
        assert thumbnail is not None
        self.assertEqual(thumbnail.size(), self.image_stack.size)
        self.assertEqual(self.backend.requests[-1].arguments['url_params'],
                         {'filename': '/models/Lora/detail_lora.png'})
        self.assertIsNone(self.generator.load_lora_thumbnail(None))
        self.assertIsNone(self.generator.load_lora_thumbnail({'name': 'no_path'}))
