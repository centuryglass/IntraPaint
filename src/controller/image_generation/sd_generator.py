"""Shared base for generators that provide Stable-Diffusion image generation with possible ControlNet and upscaling
   support."""
import logging
from argparse import Namespace
from typing import Optional, cast, Any

from PySide6.QtCore import Signal
from PySide6.QtGui import QImage, QIcon
from PySide6.QtWidgets import QInputDialog, QApplication

from src.api.a1111_webservice import AuthError
from src.api.controlnet.controlnet_constants import ControlTypeDef, CONTROLNET_REUSE_IMAGE_CODE
from src.api.controlnet.controlnet_preprocessor import ControlNetPreprocessor
from src.api.webservice import WebService
from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.controller.image_generation.image_generator import ImageGenerator
from src.image.layers.image_stack import ImageStack
from src.ui.layout.draggable_tabs.tab import Tab
from src.ui.modal.modal_utils import show_error_dialog
from src.ui.panel.controlnet_panel import TabbedControlNetPanel, CONTROLNET_TITLE
from src.ui.panel.generators.stable_diffusion_panel import StableDiffusionPanel
from src.ui.window.extra_network_window import ExtraNetworkWindow
from src.ui.window.main_window import MainWindow
from src.util.application_state import AppStateTracker, APP_STATE_LOADING, APP_STATE_EDITING
from src.util.async_task import AsyncTask
from src.util.menu_builder import menu_action
from src.util.parameter import TYPE_LIST, TYPE_STR, TYPE_FLOAT, TYPE_DICT
from src.util.shared_constants import PROJECT_DIR, \
    URL_REQUEST_MESSAGE, URL_REQUEST_RETRY_MESSAGE, \
    URL_REQUEST_TITLE

logger = logging.getLogger(__name__)

# The QCoreApplication.translate context for strings in this file
TR_ID = 'controller.image_generation.sd_generator'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


SD_BASE_DESCRIPTION = _tr("""
<p>
    Released in August 2022, Stable-Diffusion remains the most versatile and useful free image generation model.
</p>
<h2>Generator capabilities and limits:</h2>
<ul>
    <li>Requires only 4GB of VRAM, or 8GB if using an SDXL model.</li>
    <li>Tuned for an ideal resolution of 512x512 (1024x1024 for SDXL).</li>
    <li>A huge variety of fine-tuned variant models are available.</li>
    <li>
        The magnitude of changes made to existing images can be precisely controlled by varying denoising strength.
    </li>
    <li>
        Supports LoRAs, miniature extension models adding support for new styles and subjects.
    </li>
    <li>
        Supports positive and negative prompting, where (parentheses) draw additional attention to prompt sections,
        and [square brackets] reduce attention.
    </li>
    <li>
        Supports ControlNet modules, allowing image generation to be guided by arbitrary constraints like depth maps,
        existing image lines, and pose analysis.
    </li>
</ul>
""")


ERROR_TITLE_PREPROCESSOR_PREVIEW_FAILED = _tr('ControlNet preview failed')
ERROR_MESSAGE_PREPROCESSOR_PREVIEW_FAILED = _tr('Loading ControlNet preprocessor preview failed: {err}')

SD_PREVIEW_IMAGE = f'{PROJECT_DIR}/resources/generator_preview/stable-diffusion.png'
STABLE_DIFFUSION_CONFIG_CATEGORY = QApplication.translate('config.application_config', 'Stable-Diffusion')
ICON_PATH_CONTROLNET_TAB = f'{PROJECT_DIR}/resources/icons/tabs/hex.svg'
MENU_STABLE_DIFFUSION = 'Stable-Diffusion'


def _check_prompt_styles_available(_) -> bool:
    cache = Cache()
    return len(cache.get(Cache.STYLES)) > 0


def _check_lora_available(_) -> bool:
    cache = Cache()
    return len(cache.get(Cache.LORA_MODELS)) > 0


class SDGenerator(ImageGenerator):
    """Shared base for generators that provide Stable-Diffusion image generation with possible ControlNet and upscaling
       support."""

    def __init__(self, window: MainWindow, image_stack: ImageStack, args: Namespace, url_cache_key: str,
                 show_extended_controlnet_options=False) -> None:
        super().__init__(window, image_stack)
        self._image_stack = image_stack
        self._server_url = args.server_url if args.server_url != '' else Cache().get(url_cache_key)
        self._url_cache_key = url_cache_key
        self._lora_images: Optional[dict[str, Optional[QImage]]] = None
        self._connected = False
        self._control_panel: Optional[StableDiffusionPanel] = None
        self._preview = QImage(SD_PREVIEW_IMAGE)
        self._controlnet_tab: Optional[Tab] = None
        self._controlnet_panel: Optional[TabbedControlNetPanel] = None
        self._show_extended_controlnet_options = show_extended_controlnet_options

    @property
    def server_url(self) -> str:
        """Return the Stable-Diffusion server URL."""
        return self._server_url

    def get_preview_image(self) -> QImage:
        """Returns a preview image for this generator."""
        return self._preview

    def get_extra_tabs(self) -> list[Tab]:
        """Returns any extra tabs that the generator will add to the main window."""
        if self._controlnet_tab is not None:
            return [self._controlnet_tab]
        return []

    def get_webservice(self) -> Optional[WebService]:
        """Return the webservice object this module uses to connect to Stable-Diffusion, if initialized."""
        raise NotImplementedError()

    def remove_webservice(self) -> None:
        """Destroy and remove any active webservice object."""
        raise NotImplementedError()

    def create_or_get_webservice(self, url: str) -> WebService:
        """Return the webservice object this module uses to connect to Stable-Diffusion.  If the webservice already
           exists but the url doesn't match, a new webservice should replace the existing one, using the new url."""
        raise NotImplementedError()

    def interrogate(self) -> None:
        """Update the prompt to match image content using an AI image description model."""
        raise NotImplementedError()

    def get_controlnet_preprocessors(self) -> list[ControlNetPreprocessor]:
        """Return the list of available Controlnet preprocessors."""
        raise NotImplementedError()

    def get_controlnet_models(self) -> list[str]:
        """Return the list of available ControlNet models."""
        raise NotImplementedError()

    def get_controlnet_types(self) -> dict[str, ControlTypeDef]:
        """Return available ControlNet categories."""
        raise NotImplementedError()

    def get_controlnet_unit_cache_keys(self) -> list[str]:
        """Return keys used to cache serialized ControlNet units as strings."""
        raise NotImplementedError()

    def get_diffusion_model_names(self) -> list[str]:
        """Return the list of available image generation models."""
        raise NotImplementedError()

    def get_lora_model_info(self) -> list[dict[str, Any]]:
        """Return available LoRA model extensions."""
        raise NotImplementedError()

    def get_diffusion_sampler_names(self) -> list[str]:
        """Return the list of available samplers."""
        raise NotImplementedError()

    def get_upscale_method_names(self) -> list[str]:
        """Return the list of available upscale methods."""
        raise NotImplementedError()

    def cache_generator_specific_data(self) -> None:
        """When activating the generator, after the webservice is connected, this method should be implemented to
           load and cache any generator-specific API data."""
        raise NotImplementedError()

    def clear_cached_generator_data(self) -> None:
        """Clear any cached data specific to this image generator."""
        raise NotImplementedError()

    def cancel_generation(self) -> None:
        """Cancels image generation, if in-progress"""
        raise NotImplementedError()

    def load_lora_thumbnail(self, lora_info: Optional[dict[str, str]]) -> Optional[QImage]:
        """Attempt to load a LoRA model thumbnail image from the API."""
        raise NotImplementedError()

    def load_preprocessor_preview(self, preprocessor: ControlNetPreprocessor,
                                     image: QImage, mask: Optional[QImage],
                                     status_signal: Signal,
                                     image_signal: Signal) -> None:
        """Requests a ControlNet preprocessor preview image."""
        raise NotImplementedError()

    def get_gen_area_image(self, init_image: Optional[QImage] = None) -> QImage:
        """Gets the contents of the image generation area, handling any necessary preprocessing."""
        if init_image is not None:
            return init_image
        return self._image_stack.qimage_generation_area_content()

    def get_gen_area_mask(self, init_mask: Optional[QImage] = None) -> QImage:
        """Gets the inpainting mask for the image generation area, handling any necessary preprocessing."""
        if init_mask is not None:
            return init_mask
        return self._image_stack.selection_layer.mask_image

    def connect_to_url(self, url: str) -> bool:
        """Attempt to connect to a specific URL, returning whether the connection succeeded."""
        webservice = self.get_webservice()
        if webservice is not None and webservice.server_url == url and self._connected:
            return True
        self._connected = False
        if webservice is None or webservice.server_url != url:
            self.create_or_get_webservice(url)
        return self.configure_or_connect()

    def configure_or_connect(self) -> bool:
        """Handles any required steps necessary to configure the generator, install required components, and/or
           connect to required external services, returning whether the process completed correctly."""
        # Check for a valid connection, requesting a URL if needed:
        try:
            while self._server_url == '' or not self.is_available():
                prompt_text = URL_REQUEST_MESSAGE if self._server_url == '' else URL_REQUEST_RETRY_MESSAGE
                new_url, url_entered = QInputDialog.getText(self.menu_window, URL_REQUEST_TITLE, prompt_text,
                                                            text=self._server_url)
                if not url_entered:
                    return False
                if self.connect_to_url(new_url):
                    Cache().set(self._url_cache_key, new_url)
                    return True
                return False

            # If a login is required and none is defined in the environment, the webservice will automatically request
            # one during the following setup process:
            cache = Cache()

            sampler_names = self.get_diffusion_sampler_names()
            upscale_methods = self.get_upscale_method_names()
            sd_models = self.get_diffusion_model_names()
            lora_models = self.get_lora_model_info()
            for api_data, cache_key in ((sampler_names, Cache.SAMPLING_METHOD),
                                        (upscale_methods, Cache.UPSCALE_METHOD),
                                        (sd_models, Cache.SD_MODEL),
                                        (lora_models, Cache.LORA_MODELS)):
                cache_data_type = cache.get_data_type(cache_key)
                try:
                    if isinstance(api_data, dict):
                        cache.set(cache_key, api_data)
                        continue
                    assert isinstance(api_data, list)
                    if cache_data_type == TYPE_LIST:
                        cache.set(cache_key, api_data)
                    else:
                        assert cache_data_type == TYPE_STR
                        # Combine default options with dynamic options. This is so we can support having default
                        # options like "any"/"none"/"auto" when appropriate.
                        option_list = cast(list, cache.get_options(cache_key))
                        for option in api_data:
                            if option not in option_list:
                                option_list.append(option)
                        cache.update_options(cache_key, option_list)

                except (RuntimeError, KeyError) as err:
                    logger.error(f'Caching "{cache_key}" {cache_data_type} data failed: {err}')
                    if cache_data_type == TYPE_LIST:
                        cache.set(cache_key, [])
                    else:
                        assert cache_data_type == TYPE_STR
                        cache.restore_default_options(cache_key)
            self.cache_generator_specific_data()

            # Build ControlNet tab, if available through the API:
            if self._controlnet_tab is None:
                try:
                    model_list = self.get_controlnet_models()
                    preprocessors = self.get_controlnet_preprocessors()
                    control_types = self.get_controlnet_types()
                    control_keys = self.get_controlnet_unit_cache_keys()
                    if AppConfig().get(AppConfig.CONTROLNET_TILE_MODEL) in model_list:
                        cache.set(Cache.CONTROLNET_UPSCALING_AVAILABLE, True)
                    if len(preprocessors) > 0 and len(control_types) > 0:
                        controlnet_panel = TabbedControlNetPanel(preprocessors,
                                                                 model_list,
                                                                 control_types,
                                                                 control_keys,
                                                                 self._show_extended_controlnet_options)
                        self._controlnet_tab = Tab(CONTROLNET_TITLE, controlnet_panel, KeyConfig.SELECT_CONTROLNET_TAB,
                                                   parent=self.menu_window)
                        self._controlnet_tab.hide()
                        self._controlnet_tab.setIcon(QIcon(ICON_PATH_CONTROLNET_TAB))
                        controlnet_panel.request_preview.connect(self.controlnet_preprocessor_preview)
                        self._controlnet_panel = controlnet_panel
                except (KeyError, RuntimeError) as err:
                    logger.error(f'Loading ControlNet failed. {err.__class__}: {err}')

            assert self._window is not None
            self._window.cancel_generation.connect(self.cancel_generation)
            self._connected = True
            return True
        except AuthError:
            return False

    def disconnect_or_disable(self) -> None:
        """Closes any connections, unloads models, or otherwise turns off this generator."""
        cache = Cache()
        self._connected = False
        webservice = self.get_webservice()
        if webservice is not None:
            webservice.disconnect()
            self.remove_webservice()
        # Turn off inpainting cropping and padding again:
        cache.set(Cache.INPAINT_OPTIONS_AVAILABLE, False)

        # Clear cached webservice data:
        if self._lora_images is not None:
            self._lora_images.clear()
            self._lora_images = None
        cache = Cache()
        for cache_key in (Cache.SD_MODEL, Cache.LORA_MODELS, Cache.HYPERNETWORK_MODELS, Cache.SAMPLING_METHOD,
                          Cache.SCHEDULER, Cache.UPSCALE_METHOD):
            cache_data_type = cache.get_data_type(cache_key)
            if cache_data_type == TYPE_FLOAT:
                cache.set(cache_key, -1.0)
            elif cache_data_type == TYPE_STR:
                cache.restore_default_options(cache_key)
            elif cache_data_type == TYPE_LIST:
                cache.set(cache_key, [])
            else:
                assert cache_data_type == TYPE_DICT
                cache.set(cache_key, {})
        self.clear_cached_generator_data()

        if self._controlnet_tab is not None:
            self._controlnet_tab.setParent(None)
            self._controlnet_tab.deleteLater()
            self._controlnet_tab = None
            self._controlnet_panel = None
        assert self._window is not None
        self._window.cancel_generation.disconnect(self.cancel_generation)
        self.clear_menus()

    def controlnet_preprocessor_preview(self, preprocessor: ControlNetPreprocessor, image_str: str) -> None:
        """Generates a ControlNet preprocessor preview, displaying it in a new window."""
        if image_str == CONTROLNET_REUSE_IMAGE_CODE:
            image = self.get_gen_area_image()
        else:
            image = QImage(image_str)
        mask = self.get_gen_area_mask()

        class _AsyncPreviewTask(AsyncTask):
            status_signal = Signal(dict)
            error_signal = Signal(Exception)
            preview_ready = Signal(QImage)

            def signals(self) -> list[Signal]:
                return [self.status_signal, self.error_signal, self.preview_ready]

        def _get_preview(status_signal: Signal, error_signal: Signal, preview_signal: Signal) -> None:
            try:
                self.load_preprocessor_preview(preprocessor, image, mask, status_signal, preview_signal)
            except Exception as err:
                error_signal.emit(err)

        def _apply_status_update(status_dict: dict) -> None:
            if 'progress' in status_dict:
                self._window.set_loading_message(status_dict['progress'])

        def _handle_error(error: Exception) -> None:
            AppStateTracker.set_app_state(APP_STATE_EDITING)
            show_error_dialog(self._window, ERROR_TITLE_PREPROCESSOR_PREVIEW_FAILED,
                              ERROR_MESSAGE_PREPROCESSOR_PREVIEW_FAILED.format(err=error))

        def _load_preview(preview_image: QImage) -> None:
            AppStateTracker.set_app_state(APP_STATE_EDITING)
            print(f'LOADED PREVIEW: {preview_image}')
            assert self._controlnet_panel is not None
            self._controlnet_panel.set_preview(preview_image)

        AppStateTracker.set_app_state(APP_STATE_LOADING)
        preview_task = _AsyncPreviewTask(_get_preview)
        preview_task.status_signal.connect(_apply_status_update)
        preview_task.error_signal.connect(_handle_error)
        preview_task.preview_ready.connect(_load_preview)
        preview_task.start()

    @menu_action(MENU_STABLE_DIFFUSION, 'lora_shortcut', 201, [APP_STATE_EDITING],
                 condition_check=_check_lora_available)
    def show_lora_window(self) -> None:
        """Show the Lora model selection window."""
        cache = Cache()
        loras = cache.get(Cache.LORA_MODELS).copy()
        if self._lora_images is None:
            self._lora_images = {}
            AppStateTracker.set_app_state(APP_STATE_LOADING)

            class _LoadingTask(AsyncTask):
                status = Signal(str)

                def signals(self) -> list[Signal]:
                    return [self.status]

            def _load_and_open(status_signal: Signal) -> None:
                if self._lora_images is None:
                    self._lora_images = {}
                for i, lora in enumerate(loras):
                    assert isinstance(lora, dict)
                    status_signal.emit(f'Loading thumbnail {i + 1}/{len(loras)}')
                    thumbnail = self.load_lora_thumbnail(lora)
                    if thumbnail is not None and not thumbnail.isNull():
                        self._lora_images[lora['name']] = thumbnail

            task = _LoadingTask(_load_and_open)

            def _resume_and_show() -> None:
                AppStateTracker.set_app_state(APP_STATE_EDITING)
                assert self._lora_images is not None
                assert self._window is not None
                task.status.disconnect(self._window.set_loading_message)
                task.finish_signal.disconnect(_resume_and_show)
                delayed_lora_window = ExtraNetworkWindow(loras, self._lora_images)
                delayed_lora_window.exec()

            assert self._window is not None
            task.status.connect(self._window.set_loading_message)
            task.finish_signal.connect(_resume_and_show)
            task.start()
        else:
            lora_window = ExtraNetworkWindow(loras, self._lora_images)
            lora_window.exec()
