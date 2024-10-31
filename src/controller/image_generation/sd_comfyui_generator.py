"""Generates images through the Stable-Diffusion ComfyUI"""
import logging
from argparse import Namespace
from typing import Optional, cast, Any

import requests
from PySide6.QtCore import Signal, QSize, QThread, QRect, QPoint
from PySide6.QtGui import QImage, QAction, QIcon, QPainter
from PySide6.QtWidgets import QInputDialog, QApplication
from requests import ReadTimeout

from src.api.a1111_webservice import AuthError
from src.api.comfyui.comfyui_types import ImageFileReference
from src.api.comfyui.nodes.ksampler_node import SAMPLER_OPTIONS, SCHEDULER_OPTIONS
from src.api.comfyui_webservice import ComfyUiWebservice, ComfyModelType, AsyncTaskProgress, AsyncTaskStatus
from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.controller.image_generation.image_generator import ImageGenerator
from src.controller.image_generation.sd_webui_generator import SD_BASE_DESCRIPTION, SD_PREVIEW_IMAGE, \
    STABLE_DIFFUSION_CONFIG_CATEGORY, ICON_PATH_CONTROLNET_TAB
from src.image.filter.blur import BlurFilter, MODE_GAUSSIAN
from src.image.layers.image_stack import ImageStack
from src.ui.layout.draggable_tabs.tab import Tab
from src.ui.modal.settings_modal import SettingsModal
from src.ui.panel.controlnet_panel import TabbedControlNetPanel, CONTROLNET_TITLE
from src.ui.panel.generators.generator_panel import GeneratorPanel
from src.ui.panel.generators.stable_diffusion_panel import StableDiffusionPanel
from src.ui.window.extra_network_window import ExtraNetworkWindow, LORA_KEY_NAME, LORA_KEY_ALIAS, LORA_KEY_PATH
from src.ui.window.main_window import MainWindow
from src.util.application_state import AppStateTracker, APP_STATE_LOADING, APP_STATE_EDITING
from src.util.menu_builder import menu_action
from src.util.parameter import TYPE_LIST, TYPE_STR, TYPE_FLOAT, TYPE_DICT
from src.util.shared_constants import EDIT_MODE_TXT2IMG, EDIT_MODE_INPAINT, EDIT_MODE_IMG2IMG, AUTH_ERROR, \
    URL_REQUEST_MESSAGE, URL_REQUEST_RETRY_MESSAGE, URL_REQUEST_TITLE, \
    GENERATE_ERROR_MESSAGE_EMPTY_MASK, GENERATE_ERROR_TITLE, ERROR_MESSAGE_TIMEOUT
from src.util.visual.pil_image_utils import pil_image_scaling

logger = logging.getLogger(__name__)

# The QCoreApplication.translate context for strings in this file
TR_ID = 'controller.image_generation.sd_comfyui_generator'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


SD_COMFYUI_GENERATOR_NAME = _tr('Stable-Diffusion ComfyUI API')
SD_COMFYUI_GENERATOR_DESCRIPTION_HEADER = _tr("""
<h2>Stable-Diffusion: via ComfyUI API</h2>
<p>
    <b>NOTE:</b> The ComfyUI generator is still in its early implementation stages, the following features are not yet
    supported:
</p>
<ul>
    <li>ControlNet</li>
    <li>CLIP interrogation</li>
    <li>Upscaling</li>
</ul>
""")
SD_COMFYUI_GENERATOR_DESCRIPTION_COMFYUI = _tr("""
<h3>ComfyUI:</h3>
<p>
    ComfyUI is a popular Stable-Diffusion UI with a complex and powerful node-based interface. This IntraPaint
    generator offloads image generation to that system through a network connection.  The ComfyUI instance can be run on
    the same computer as IntraPaint, or remotely on a separate server.
</p>""")
SD_COMFYUI_GENERATOR_DESCRIPTION = (f'{SD_COMFYUI_GENERATOR_DESCRIPTION_HEADER}\n{SD_BASE_DESCRIPTION}'
                                    f'\n{SD_COMFYUI_GENERATOR_DESCRIPTION_COMFYUI}')

# noinspection SpellCheckingInspection
SD_COMFYUI_GENERATOR_SETUP = _tr("""
<h2>Installing Stable-Diffusion</h2>
<p>
    To use this Stable-Diffusion image generator with IntraPaint, you will first to install ComfyUI. TODO: what's the
    most basic ComfyUI install process? Does Stability Matrix support it? Document that here.
</p>
<p>
    Once ComfyUI has started completely, you should be able to click "Activate" below, and IntraPaint will
    connect to it automatically.  If you configure the WebUI to use any URL other than the default, IntraPaint
     will ask for that information before connecting.
</p>
""")

TASK_STATUS_QUEUED = _tr('Waiting, position {queue_number} in queue.')
TASK_STATUS_GENERATING = _tr('Generating...')
TASK_STATUS_BATCH_NUMBER = _tr('Batch {batch_num} of {num_batches}:')

DEFAULT_COMFYUI_URL = 'http://localhost:8188'

MAX_ERROR_COUNT = 10
MIN_RETRY_US = 300000
MAX_RETRY_US = 60000000

LCM_SAMPLER = 'lcm'
LCM_LORA_1_5 = 'lcm-lora-sdv1-5.safetensors'
LCM_LORA_XL = 'lcm-lora-sdxl.safetensors'

MENU_STABLE_DIFFUSION = 'Stable-Diffusion'


def _check_lcm_mode_available(_) -> bool:
    if LCM_SAMPLER not in Cache().get_options(Cache.SAMPLING_METHOD):
        return False
    loras = Cache().get(Cache.LORA_MODELS)
    return LCM_LORA_1_5 in loras or LCM_LORA_XL in loras


def _check_prompt_styles_available(_) -> bool:
    cache = Cache()
    return len(cache.get(Cache.STYLES)) > 0


def _check_lora_available(_) -> bool:
    cache = Cache()
    return len(cache.get(Cache.LORA_MODELS)) > 0


class SDComfyUIGenerator(ImageGenerator):
    """Interface for providing image generation capabilities."""

    def __init__(self, window: MainWindow, image_stack: ImageStack, args: Namespace) -> None:
        super().__init__(window, image_stack)
        self._image_stack = image_stack
        self._server_url = args.server_url if args.server_url != '' else Cache().get(Cache.SD_COMFYUI_SERVER_URL)
        self._webservice: Optional[ComfyUiWebservice] = ComfyUiWebservice(self._server_url)
        self._menu_actions: dict[str, list[QAction]] = {}
        self._connected = False
        self._control_panel: Optional[StableDiffusionPanel] = None
        self._preview = QImage(SD_PREVIEW_IMAGE)
        self._controlnet_tab: Optional[Tab] = None
        self._controlnet_panel: Optional[TabbedControlNetPanel] = None
        self._active_task_id = ''
        self._active_task_number = 0

    def get_display_name(self) -> str:
        """Returns a display name identifying the generator."""
        return SD_COMFYUI_GENERATOR_NAME

    def get_preview_image(self) -> QImage:
        """Returns a preview image for this generator."""
        return self._preview

    def get_setup_text(self) -> str:
        """Returns a rich text description of how to set up this generator."""
        return SD_COMFYUI_GENERATOR_SETUP

    def get_description(self) -> str:
        """Returns an extended description of this generator."""
        return SD_COMFYUI_GENERATOR_DESCRIPTION

    def get_extra_tabs(self) -> list[Tab]:
        """Returns any extra tabs that the generator will add to the main window."""
        if self._controlnet_tab is not None:
            return [self._controlnet_tab]
        return []

    def is_available(self) -> bool:
        """Returns whether the generator is supported on the current system."""
        if self._webservice is None:
            self._webservice = ComfyUiWebservice(self._server_url)
        try:
            # Use the system status endpoint to check for ComfyUI:
            system_status = self._webservice.get_system_stats()
            return 'system' in system_status and 'comfyui_version' in system_status['system']
        except (requests.exceptions.RequestException, requests.exceptions.ConnectionError) as req_err:
            logger.error(f'Login check connection failed: {req_err}')
        except AuthError:
            self.status_signal.emit(AUTH_ERROR)
        return False

    def connect_to_url(self, url: str) -> bool:
        """Attempt to connect to a specific URL, returning whether the connection succeeded."""
        assert self._webservice is not None
        if url == self._server_url:
            if self._connected:
                return True
            return self.configure_or_connect()
        self._server_url = url
        self._webservice.disconnect()
        self._webservice = ComfyUiWebservice(url)
        return self.configure_or_connect()

    def configure_or_connect(self) -> bool:
        """Handles any required steps necessary to configure the generator, install required components, and/or
           connect to required external services, returning whether the process completed correctly."""
        # Check for a valid connection, requesting a URL if needed:
        try:
            if self._webservice is None:
                self._webservice = ComfyUiWebservice(self._server_url)
            while self._server_url == '' or not self.is_available():
                prompt_text = URL_REQUEST_MESSAGE if self._server_url == '' else URL_REQUEST_RETRY_MESSAGE
                new_url, url_entered = QInputDialog.getText(self.menu_window, URL_REQUEST_TITLE, prompt_text,
                                                            text=self._server_url)
                if not url_entered:
                    return False
                if self.connect_to_url(new_url):
                    Cache().set(Cache.SD_COMFYUI_SERVER_URL, new_url)
                    return True
                return False

            cache = Cache()
            for model_type, cache_key in ((ComfyModelType.CHECKPOINT, Cache.SD_MODEL),
                                          (ComfyModelType.CONFIG, Cache.COMFYUI_MODEL_CONFIG),
                                          (ComfyModelType.LORA, Cache.LORA_MODELS),
                                          (ComfyModelType.HYPERNETWORKS, Cache.HYPERNETWORK_MODELS),
                                          (ComfyModelType.UPSCALING, Cache.UPSCALE_METHOD)):
                cache_data_type = cache.get_data_type(cache_key)
                try:
                    model_list = self._webservice.get_models(model_type)
                    model_list.sort()
                    if cache_data_type == TYPE_LIST:
                        cache.set(cache_key, model_list)
                    else:
                        assert cache_data_type == TYPE_STR
                        cache.restore_default_options(cache_key)
                        # Combine default options with dynamic options. This is so we can support having default
                        # options like "any"/"none"/"auto" when appropriate.
                        option_list = cast(list[str], cache.get_options(cache_key))
                        for option in model_list:
                            if option not in option_list:
                                option_list.append(option)
                        cache.update_options(cache_key, option_list)
                except (RuntimeError, KeyError) as err:
                    logger.error(f'Loading {model_type} model options failed: {err}')
                    if cache_data_type == TYPE_LIST:
                        cache.set(cache_key, [])
                    else:
                        assert cache_data_type == TYPE_STR
                        cache.restore_default_options(cache_key)

            cache.update_options(Cache.SAMPLING_METHOD, SAMPLER_OPTIONS)
            cache.update_options(Cache.SCHEDULER, SCHEDULER_OPTIONS)

            # Enable inpainting cropping and padding:
            cache.set(Cache.INPAINT_OPTIONS_AVAILABLE, True)

            # Build ControlNet tab if ControlNet model list is non-empty:
            if self._controlnet_tab is None:
                try:
                    model_list = self._webservice.get_controlnets()
                    preprocessors = self._webservice.get_controlnet_preprocessors()
                    control_types = self._webservice.get_controlnet_type_categories()
                    control_keys = [Cache.CONTROLNET_ARGS_0_COMFYUI, Cache.CONTROLNET_ARGS_1_COMFYUI,
                                    Cache.CONTROLNET_ARGS_2_COMFYUI]
                    if len(preprocessors) > 0 and len(control_types) > 0:
                        controlnet_panel = TabbedControlNetPanel(preprocessors,
                                                                 model_list,
                                                                 control_types,
                                                                 control_keys,
                                                                 True)
                        self._controlnet_tab = Tab(CONTROLNET_TITLE, controlnet_panel, KeyConfig.SELECT_CONTROLNET_TAB,
                                                   parent=self.menu_window)
                        self._controlnet_tab.hide()
                        self._controlnet_tab.setIcon(QIcon(ICON_PATH_CONTROLNET_TAB))
                    else:
                        logger.error(f'Missing data required to initialize ControlNet: found {len(model_list)} models,'
                                     f' {len(preprocessors)} preprocessors, and {len(control_types)} control types.'
                                     f' To use ControlNet, at least one preprocessor and one control type must be'
                                     f' available.')
                except (KeyError, RuntimeError) as err:
                    logger.error(f'Loading ControlNet failed: {err}')

            assert self._window is not None
            self._window.cancel_generation.connect(self.cancel_generation)

            return True
        except AuthError:
            return False

    def disconnect_or_disable(self) -> None:
        """Closes any connections, unloads models, or otherwise turns off this generator."""
        if self._webservice is not None:
            self._webservice.disconnect()
            self._webservice = None
        cache = Cache()
        # Turn off inpainting cropping and padding again:
        cache.set(Cache.INPAINT_OPTIONS_AVAILABLE, False)
        # Clear cached webservice data:
        for cache_key in (Cache.SD_MODEL, Cache.COMFYUI_MODEL_CONFIG, Cache.LORA_MODELS, Cache.HYPERNETWORK_MODELS,
                          Cache.SAMPLING_METHOD, Cache.SCHEDULER, Cache.UPSCALE_METHOD):
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
        if self._controlnet_tab is not None:
            self._controlnet_tab.setParent(None)
            self._controlnet_tab.deleteLater()
            self._controlnet_tab = None
            self._controlnet_panel = None
        assert self._window is not None
        self._window.cancel_generation.disconnect(self.cancel_generation)
        self.clear_menus()

    def init_settings(self, settings_modal: SettingsModal) -> None:
        """Updates a settings modal to add settings relevant to this generator."""
        assert self._webservice is not None
        # TODO: remote config options, similar to A1111Config
        app_config = AppConfig()
        # TODO: sort stable-diffusion config between ComfyUI and WebUI compatible options.
        settings_modal.load_from_config(app_config, [STABLE_DIFFUSION_CONFIG_CATEGORY])

    def refresh_settings(self, settings_modal: SettingsModal) -> None:
        """Reloads current values for this generator's settings, and updates them in the settings modal."""
        # TODO: remote config options, similar to A1111Config
        # assert self._webservice is not None
        settings = {}  # settings = self._webservice.get_config()
        # TODO: sort stable-diffusion config between ComfyUI and WebUI compatible options.
        app_config = AppConfig()
        for key in app_config.get_category_keys(STABLE_DIFFUSION_CONFIG_CATEGORY):
            settings[key] = app_config.get(key)
        settings_modal.update_settings(settings)

    def update_settings(self, changed_settings: dict[str, Any]) -> None:
        """Applies any changed settings from a SettingsModal that are relevant to the image generator and require
           special handling."""
        # TODO: remote config options, similar to A1111Config
        # assert self._webservice is not None
        # web_config = A1111Config()
        # web_categories = web_config.get_categories()
        # web_keys = [key for cat in web_categories for key in web_config.get_category_keys(cat)]
        web_keys: list[str] = []

        # TODO: sort stable-diffusion config between ComfyUI and WebUI compatible options.
        app_keys = AppConfig().get_category_keys(STABLE_DIFFUSION_CONFIG_CATEGORY)
        web_changes = {}
        for key, value in changed_settings.items():
            if key in web_keys:
                web_changes[key] = value
            elif key in app_keys and not isinstance(value, (list, dict)):
                AppConfig().set(key, value)
        # if len(web_changes) > 0:
        #     def _update_config() -> None:
        #         assert self._webservice is not None
        #         try:
        #             self._webservice.set_config(changed_settings)
        #         except ReadTimeout:
        #             logger.error('Settings update timed out')
        #
        #     update_task = AsyncTask(_update_config, True)
        #
        #     def _update_setting():
        #         AppStateTracker.set_app_state(APP_STATE_EDITING if self._image_stack.has_image else APP_STATE_NO_IMAGE)
        #         update_task.finish_signal.disconnect(_update_setting)
        #
        #     update_task.finish_signal.connect(_update_setting)
        #     update_task.start()

    def unload_settings(self, settings_modal: SettingsModal) -> None:
        """Unloads this generator's settings from the settings modal."""
        # TODO: sort stable-diffusion config between ComfyUI and WebUI compatible options.
        settings_modal.remove_category(AppConfig(), STABLE_DIFFUSION_CONFIG_CATEGORY)

        # TODO: remote config options, similar to A1111Config
        # a1111_config = A1111Config()
        # for category in a1111_config.get_categories():
        #     settings_modal.remove_category(a1111_config, category)

    def interrogate(self) -> None:
        """ Use CLIP interrogation to automatically generate image prompts.

        TODO: ComfyUI doesn't support this by default, I'll probably need to track down a custom node that does it.
              Of course, I'll also need to scan installed nodes to make sure that one is actually there, and I'll need
              to add and remove the "Interrogate" button based on that node's availability.
        """
        print('CLIP interrogate not yet available for ComfyUI!')

    def get_control_panel(self) -> Optional[GeneratorPanel]:
        """Returns a widget with inputs for controlling this generator."""
        if self._control_panel is None:
            self._control_panel = StableDiffusionPanel(False, False)
            self._control_panel.hide()
            self._control_panel.generate_signal.connect(self.start_and_manage_image_generation)
            self._control_panel.interrogate_signal.connect(self.interrogate)
        return self._control_panel

    def _repeated_progress_check(self, task_id: str, task_number: int, batch_num: int, num_batches: int,
                                 external_status_signal: Optional[Signal] = None) -> AsyncTaskProgress:
        """Repeatedly checks progress of an ongoing task until an ending condition is reached, returning the final
           status. Call this outside of the UI thread."""
        webservice = self._webservice
        assert webservice is not None
        error_count = 0
        status: Optional[AsyncTaskProgress] = None
        batch_num = batch_num + 1
        last_percentage = 0.0
        with webservice.open_websocket() as websocket:
            while status is None or status['status'] in (AsyncTaskStatus.PENDING, AsyncTaskStatus.ACTIVE):
                ws_message = websocket.recv()
                percentage = ComfyUiWebservice.parse_percentage_from_websocket_message(ws_message)
                if num_batches > 1:
                    if percentage is None:
                        percentage = 0.0
                    single_batch_percentage = round(100 / num_batches, ndigits=4)
                    percentage = round(single_batch_percentage * ((batch_num - 1) + (percentage / 100)), ndigits=4)
                if percentage is not None:
                    last_percentage = max(percentage, last_percentage)

                sleep_time = min(MIN_RETRY_US * pow(2, error_count), MAX_RETRY_US)
                thread = QThread.currentThread()
                assert thread is not None
                thread.usleep(sleep_time)
                try:
                    assert webservice is not None
                    status = webservice.check_queue_entry(task_id, task_number)
                    if status['status'] == AsyncTaskStatus.PENDING and 'index' in status:
                        status_text = TASK_STATUS_QUEUED.format(queue_number=status['index'])
                    else:
                        status_text = TASK_STATUS_GENERATING
                    if num_batches > 1:
                        status_text = (f'{TASK_STATUS_BATCH_NUMBER.format(batch_num=batch_num, num_batches=num_batches)}'
                                       f' {status_text}')
                    status_text = f'{status_text}\n{last_percentage}%'
                    assert external_status_signal is not None
                    external_status_signal.emit({'progress': status_text})
                except ReadTimeout:
                    error_count += 1
                except RuntimeError as err:
                    error_count += 1
                    logger.error(f'Error {error_count}: {err}')
                    if error_count > MAX_ERROR_COUNT:
                        logger.error('Image generation failed, reached max retries.')
                        break
        assert status is not None
        return status

    def upscale(self, new_size: QSize) -> bool:
        """Upscale using AI upscaling modes provided by stable-diffusion-webui, returning whether upscaling
        was attempted."""
        # TODO: Build and apply ComfyUI basic upscaling workflow (with standalone model)
        # TODO: Build and apply ControlNet tiled upscaling workflow, integrating ultimate upscale script
        return False

    def cancel_generation(self) -> None:
        """Cancels image generation, if in-progress"""
        assert self._webservice is not None
        if AppStateTracker.app_state() == APP_STATE_LOADING:
            self._webservice.interrupt(self._active_task_id)

    def generate(self,
                 status_signal: Signal,
                 source_image: QImage,
                 mask_image: Optional[QImage] = None) -> None:
        """Generates new images. Image size, image count, prompts, etc. are loaded from AppConfig as needed.

        Parameters
        ----------
        status_signal : Signal[str]
            Signal to emit when status updates are available.
        source_image : QImage
            Image to potentially use as a basis for the created or edited image.  This will be ignored if the editing
            mode is text-to-image and there are no ControlNet units using the image generation area.
        mask_image : QImage, optional
            Mask marking the edited image region.
        """
        assert self._webservice is not None
        cache = Cache()
        config = AppConfig()
        edit_mode = cache.get(Cache.EDIT_MODE)
        if edit_mode == EDIT_MODE_INPAINT and self._image_stack.selection_layer.generation_area_fully_selected():
            edit_mode = EDIT_MODE_IMG2IMG
        if edit_mode != EDIT_MODE_INPAINT:
            mask_image = None
        elif self._image_stack.selection_layer.generation_area_is_empty():
            raise RuntimeError(GENERATE_ERROR_MESSAGE_EMPTY_MASK)

        original_source_image: Optional[QImage] = None
        gen_area = self._image_stack.generation_area
        inpaint_inner_bounds = QRect(QPoint(), gen_area.size())

        if edit_mode == EDIT_MODE_INPAINT and cache.get(Cache.INPAINT_FULL_RES):
            selection_layer = self._image_stack.selection_layer
            selection_gen_area = selection_layer.get_selection_gen_area()
            assert selection_gen_area is not None
            if inpaint_inner_bounds.size() != selection_gen_area.size():
                inpaint_inner_bounds = selection_gen_area.translated(-selection_layer.position - gen_area.topLeft())
                original_source_image = source_image
                source_image = original_source_image.copy(inpaint_inner_bounds)
                assert mask_image is not None
                mask_image = mask_image.copy(inpaint_inner_bounds)

        # Pre-process image and mask as necessary:
        if source_image is not None:
            expected_size = cast(QSize, cache.get(Cache.GENERATION_SIZE))
            if expected_size != source_image.size():
                source_image = pil_image_scaling(source_image, expected_size)
        if mask_image is not None:
            assert source_image is not None
            if mask_image.size() != source_image.size():
                mask_image = pil_image_scaling(mask_image, source_image.size())
            # ComfyUI doesn't blur masks unless you add another node to do it, so me might as well just do it here:
            blur_radius = config.get(AppConfig.MASK_BLUR)
            if blur_radius > 0:
                mask_image = BlurFilter.blur(mask_image, MODE_GAUSSIAN, blur_radius)
            # ComfyUI expects inverted masks:
            mask_image.invertPixels(QImage.InvertMode.InvertRgba)

        num_batches = Cache().get(Cache.BATCH_COUNT)
        seed: Optional[int] = None
        first_image_idx = 0
        uploaded_image_references: dict[str, ImageFileReference] = {}
        mask_reference: Optional[ImageFileReference] = None
        for batch_num in range(num_batches):
            try:
                sequence_seed = None if seed is None else seed + batch_num
                if edit_mode == EDIT_MODE_INPAINT:
                    assert mask_image is not None
                    queue_info = self._webservice.inpaint(source_image,
                                                          mask_image if mask_reference is None else mask_reference,
                                                          uploaded_image_references, sequence_seed)
                elif edit_mode == EDIT_MODE_IMG2IMG:
                    assert source_image is not None
                    queue_info = self._webservice.img2img(source_image, uploaded_image_references, sequence_seed)
                else:
                    assert edit_mode == EDIT_MODE_TXT2IMG
                    queue_info = self._webservice.txt2img(source_image, uploaded_image_references, sequence_seed)
                if seed is None and 'seed' in queue_info and isinstance(queue_info['seed'], int):
                    seed = queue_info['seed']
                if 'uploaded_mask' in queue_info:
                    mask_reference = queue_info['uploaded_mask']
                if 'error' in queue_info:
                    raise RuntimeError(str(queue_info['error']))
                assert 'number' in queue_info
                assert 'prompt_id' in queue_info
                self._active_task_number = queue_info['number']
                self._active_task_id = queue_info['prompt_id']

                # Check progress in a loop until it finishes or something goes wrong:
                final_status = self._repeated_progress_check(self._active_task_id, self._active_task_number, batch_num,
                                                             num_batches, status_signal)
                if 'outputs' not in final_status:
                    raise RuntimeError(GENERATE_ERROR_TITLE)
                image_data = self._webservice.download_images(final_status['outputs']['images'])
                # TODO: if using "inpaint full res", this would be a good place to pad images to make them match the
                #       gen. area size again.
                for i, response_image in enumerate(image_data):
                    if inpaint_inner_bounds.size() != gen_area.size() and original_source_image is not None:
                        inner_content_image = response_image
                        if inner_content_image.size() != inpaint_inner_bounds.size():
                            inner_content_image = pil_image_scaling(inner_content_image, inpaint_inner_bounds.size())
                        final_image = original_source_image.copy()
                        painter = QPainter(final_image)
                        painter.drawImage(inpaint_inner_bounds, inner_content_image)
                        self._cache_generated_image(final_image, i + first_image_idx)
                    else:
                        self._cache_generated_image(response_image, i + first_image_idx)
                first_image_idx = first_image_idx + len(image_data)
            except ReadTimeout:
                raise RuntimeError(ERROR_MESSAGE_TIMEOUT)
            except (RuntimeError, ConnectionError) as image_gen_error:
                logger.error(f'request failed: {image_gen_error}')
                raise RuntimeError(f'request failed: {image_gen_error}') from image_gen_error
            except Exception as unexpected_err:
                logger.error('Unexpected error:', unexpected_err)
                raise RuntimeError(f'unexpected error: {unexpected_err}') from unexpected_err
        if seed is not None:
            status_signal.emit({'seed': str(seed)})

    @menu_action(MENU_STABLE_DIFFUSION, 'lora_shortcut', 201, [APP_STATE_EDITING],
                 condition_check=_check_lora_available)
    def show_lora_window(self) -> None:
        """Show the Lora model selection window."""
        cache = Cache()
        loras = cache.get(Cache.LORA_MODELS)

        def _structure_lora_data(file) -> dict[str, str]:
            if '.' in file:
                name = file[:file.rindex('.')]
            else:
                name = file
            return {
                LORA_KEY_NAME: name,
                LORA_KEY_ALIAS: name,
                LORA_KEY_PATH: file
            }
        lora_dict = {}
        for lora in loras:
            lora_dict[lora] = _structure_lora_data(lora)
        lora_window = ExtraNetworkWindow(loras, {})
        lora_window.exec()

    @menu_action(MENU_STABLE_DIFFUSION, 'lcm_mode_shortcut', 210,
                 condition_check=_check_lcm_mode_available)
    def set_lcm_mode(self) -> None:
        """Apply all settings required for using an LCM LoRA module."""
        cache = Cache()
        loras = Cache().get(Cache.LORA_MODELS)
        if LCM_LORA_1_5 in loras:
            lora_name = LCM_LORA_1_5
        else:
            assert LCM_LORA_XL in loras
            lora_name = LCM_LORA_XL
        lora_key = f'<lora:{lora_name}:1>'
        prompt = cache.get(Cache.PROMPT)
        if lora_key not in prompt:
            cache.set(Cache.PROMPT, f'{prompt} {lora_key}')
        cache.set(Cache.GUIDANCE_SCALE, 1.5)
        cache.set(Cache.SAMPLING_STEPS, 8)
        cache.set(Cache.SAMPLING_METHOD, LCM_SAMPLER)
