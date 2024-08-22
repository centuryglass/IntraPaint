"""Generates images through the Stable-Diffusion WebUI (A1111 or Forge)"""
import datetime
import json
import logging
import os
from argparse import Namespace
from typing import Optional, Dict, List, cast, Any, Callable, Tuple

import requests
from PySide6.QtCore import Signal, QSize, QThread
from PySide6.QtGui import QImage, QAction, QIcon
from PySide6.QtWidgets import QInputDialog, QWidget, QApplication

from src.api.a1111_webservice import A1111Webservice, AuthError
from src.config.a1111_config import A1111Config
from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_generation.image_generator import ImageGenerator
from src.image.layers.image_stack import ImageStack
from src.ui.modal.modal_utils import show_error_dialog
from src.ui.modal.settings_modal import SettingsModal
from src.ui.panel.controlnet_panel import TabbedControlnetPanel, CONTROLNET_TITLE
from src.ui.panel.generators.sd_webui_panel import SDWebUIPanel
from src.ui.layout.draggable_tabs.tab import Tab
from src.ui.window.extra_network_window import ExtraNetworkWindow
from src.ui.window.main_window import MainWindow
from src.ui.window.prompt_style_window import PromptStyleWindow
from src.util.application_state import AppStateTracker, APP_STATE_LOADING, APP_STATE_EDITING, APP_STATE_NO_IMAGE
from src.util.async_task import AsyncTask
from src.util.menu_builder import menu_action
from src.util.parameter import ParamType
from src.util.shared_constants import EDIT_MODE_TXT2IMG, EDIT_MODE_INPAINT, EDIT_MODE_IMG2IMG, PROJECT_DIR

logger = logging.getLogger(__name__)

# The QCoreApplication.translate context for strings in this file
TR_ID = 'controller.image_generation.sd_webui_generator'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


MENU_TOOLS = _tr('Tools')

SD_WEBUI_GENERATOR_NAME = _tr('Stable-Diffusion WebUI API')
SD_WEBUI_GENERATOR_DESCRIPTION = _tr('<h2>Stable-Diffusion: via WebUI API</h2>'
                                     '<p>Released in August 2022, Stable-Diffusion remains the most versatile and '
                                     'useful free image generation model.</p>'
                                     '<h2>Generator capabilities and limits:</h2>'
                                     '<ul>'
                                     '<li>Requires only 4GB of VRAM, or 8GB if using an SDXL model.</li>'
                                     '<li>Tuned for an ideal resolution of 512x512 (1024x1024 for SDXL).</li>'
                                     '<li>A huge variety of fine-tuned variant models are available.</li>'
                                     '<li>The magnitude of changes made to existing images can be precisely controlled'
                                     ' by varying denoising strength.</li>'
                                     '<li>Supports LORAs, miniature extension models adding support for new styles and'
                                     ' subjects.</li>'
                                     '<li>Supports positive and negative prompting, where (parentheses) draw additional'
                                     ' attention to prompt sections, and [square brackets] reduce attention.</li>'
                                     '<li>Supports ControlNet modules, allowing image generation to be guided by '
                                     'arbitrary constraints like depth maps, existing image lines, and more.</li>'
                                     '</ul><h3>Stable-Diffusion WebUI:</h3><p>The Stable-Diffusion WebUI is one of the '
                                     'first interfaces created for using Stable-Diffusion. This IntraPaint generator '
                                     'offloads image generation to that system through a network connection.  The '
                                     'WebUI instance can be run on the same computer as IntraPaint, or remotely on a '
                                     'separate server.</p>')

# noinspection SpellCheckingInspection
SD_WEBUI_GENERATOR_SETUP = _tr('<h2>Installing the WebUI</h2><p>The <a href="https://github.com/lllyasviel/'
                               'stable-diffusion-webui-forge">Forge WebUI</a> is the recommended version, but the'
                               ' original <a href="https://github.com/AUTOMATIC1111/stable-diffusion-webui">'
                               'Stable-Diffusion WebUI</a> also works. Pick one of those, and follow instructions at'
                               ' the link to install it.</p><p>Once the WebUI is installed, open the "webui-user.bat" '
                               'file in its main folder (or "webui-user.sh" on Linux and MacOS). Where it says "set '
                               'COMMANDLINE_ARGS", add <nobr>--api</nobr>, save changes, and run the webui-user script.'
                               ' Once the WebUI starts successfully, you should be able to activate this IntraPaint'
                               ' generator.</p>')
SD_PREVIEW_IMAGE = f'{PROJECT_DIR}/resources/generator_preview/stable-diffusion.png'
CONTROLNET_TAB_ICON = f'{PROJECT_DIR}/resources/icons/tabs/hex.svg'
DEFAULT_SD_URL = 'http://localhost:7860'
STABLE_DIFFUSION_CONFIG_CATEGORY = 'Stable-Diffusion'
AUTH_ERROR_DETAIL_KEY = 'detail'
AUTH_ERROR_MESSAGE = _tr('Not authenticated')
INTERROGATE_ERROR_MESSAGE_NO_IMAGE = _tr('Open or create an image first.')
ERROR_MESSAGE_EXISTING_OPERATION = _tr('Existing operation still in progress')
INTERROGATE_ERROR_TITLE = _tr('Interrogate failure')
INTERROGATE_LOADING_TEXT = _tr('Running CLIP interrogate')
URL_REQUEST_TITLE = _tr('Inpainting UI')
URL_REQUEST_MESSAGE = _tr('Enter server URL:')
URL_REQUEST_RETRY_MESSAGE = _tr('Server connection failed, enter a new URL or click "OK" to retry')
CONTROLNET_MODEL_LIST_KEY = 'model_list'
UPSCALE_ERROR_TITLE = _tr('Upscale failure')
PROGRESS_KEY_CURRENT_IMAGE = 'current_image'
PROGRESS_KEY_FRACTION = 'progress'
PROGRESS_KEY_ETA_RELATIVE = 'eta_relative'
STYLE_ERROR_TITLE = _tr('Updating prompt styles failed')

GENERATE_ERROR_TITLE = _tr('Image generation failed')
GENERATE_ERROR_MESSAGE_EMPTY_MASK = _tr('Nothing was selected in the image generation area. Either use the selection'
                                        ' tool to mark part of the image generation area for inpainting, move the image'
                                        ' generation area to cover selected content, or switch to another image'
                                        ' generation mode.')
CONTROLNET_TAB = _tr('ControlNet')
CONTROLNET_UNIT_TAB = _tr('ControlNet Unit {unit_number}')
AUTH_ERROR = _tr('Login cancelled.')

MAX_ERROR_COUNT = 10
MIN_RETRY_US = 300000
MAX_RETRY_US = 60000000

LCM_SAMPLER = 'LCM'
LCM_LORA_1_5 = 'lcm-lora-sdv1-5'
LCM_LORA_XL = 'lcm-lora-sdxl'

MENU_STABLE_DIFFUSION = 'Stable-Diffusion'

GEN_TAB_ICON = f'{PROJECT_DIR}/resources/icons/tabs/sparkle.svg'


def _check_lcm_mode_available(_) -> bool:
    if LCM_SAMPLER not in AppConfig().get_options(AppConfig.SAMPLING_METHOD):
        return False
    loras = [lora['name'] for lora in Cache().get(Cache.LORA_MODELS)]
    return LCM_LORA_1_5 in loras or LCM_LORA_XL in loras


def _check_prompt_styles_available(_) -> bool:
    cache = Cache()
    return len(cache.get(Cache.STYLES)) > 0


def _check_lora_available(_) -> bool:
    cache = Cache()
    return len(cache.get(Cache.LORA_MODELS)) > 0


class SDWebUIGenerator(ImageGenerator):
    """Interface for providing image generation capabilities."""

    def __init__(self, window: MainWindow, image_stack: ImageStack, args: Namespace) -> None:
        super().__init__(window, image_stack)
        self._server_url = args.server_url if args.server_url != '' else DEFAULT_SD_URL
        self._webservice: Optional[A1111Webservice] = A1111Webservice(self._server_url)
        self._lora_images: Optional[Dict[str, Optional[QImage]]] = None
        self._menu_actions: Dict[str, List[QAction]] = {}
        self._connected = False
        self._control_panel: Optional[SDWebUIPanel] = None
        self._preview = QImage(SD_PREVIEW_IMAGE)
        self._controlnet_tab: Optional[Tab] = None
        self._controlnet_panel: Optional[TabbedControlnetPanel] = None

    def get_display_name(self) -> str:
        """Returns a display name identifying the generator."""
        return SD_WEBUI_GENERATOR_NAME

    def get_preview_image(self) -> QImage:
        """Returns a preview image for this generator."""
        return self._preview

    def get_setup_text(self) -> str:
        """Returns a rich text description of how to set up this generator."""
        return SD_WEBUI_GENERATOR_SETUP

    def get_description(self) -> str:
        """Returns an extended description of this generator."""
        return SD_WEBUI_GENERATOR_DESCRIPTION

    def get_extra_tabs(self) -> List[Tab]:
        """Returns any extra tabs that the generator will add to the main window."""
        if self._controlnet_tab is not None:
            return [self._controlnet_tab]
        return []

    def is_available(self) -> bool:
        """Returns whether the generator is supported on the current system."""
        if self._webservice is None:
            self._webservice = A1111Webservice(self._server_url)
        try:
            # Login automatically if username/password are defined as env variables.
            # Obviously this isn't terribly secure, but A1111 auth security is already pretty minimal, and I'm just using
            # this for testing.
            if 'SD_UNAME' in os.environ and 'SD_PASS' in os.environ:
                self._webservice.login(os.environ['SD_UNAME'], os.environ['SD_PASS'])
                self._webservice.set_auth((os.environ['SD_UNAME'], os.environ['SD_PASS']))
            health_check_res = self._webservice.login_check()
            if health_check_res.ok or (health_check_res.status_code == 401
                                       and health_check_res.json()[AUTH_ERROR_DETAIL_KEY] == AUTH_ERROR_MESSAGE):
                return True
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
        self._webservice = A1111Webservice(url)
        return self.configure_or_connect()

    def configure_or_connect(self) -> bool:
        """Handles any required steps necessary to configure the generator, install required components, and/or
           connect to required external services, returning whether the process completed correctly."""
        # Check for a valid connection, requesting a URL if needed:
        try:
            if self._webservice is None:
                self._webservice = A1111Webservice(self._server_url)
            while self._server_url == '' or not self.is_available():
                prompt_text = URL_REQUEST_MESSAGE if self._server_url == '' else URL_REQUEST_RETRY_MESSAGE
                new_url, url_entered = QInputDialog.getText(self.menu_window, URL_REQUEST_TITLE, prompt_text)
                if not url_entered:
                    return False
                return self.connect_to_url(new_url)

            # If a login is required and none is defined in the environment, the webservice will automatically request
            # one during the following setup process:
            cache = Cache()
            try:
                model_list = self._webservice.get_controlnet_models()
                if model_list is not None and CONTROLNET_MODEL_LIST_KEY in model_list and len(
                        model_list[CONTROLNET_MODEL_LIST_KEY]) > 0:
                    cache.set(Cache.CONTROLNET_VERSION, 1.0)
                else:
                    cache.set(Cache.CONTROLNET_VERSION, -1.0)
            except RuntimeError as err:
                logger.error(f'Loading controlnet config failed: {err}')
                cache.set(Cache.CONTROLNET_VERSION, -1.0)

            option_loading_params: Tuple[Tuple[str, Callable[[], List[str]]], ...] = (
                (AppConfig.SAMPLING_METHOD, self._webservice.get_samplers),
                (AppConfig.UPSCALE_METHOD, self._webservice.get_upscalers)
            )

            # load various option lists:
            for config_key, option_loading_fn in option_loading_params:
                try:
                    options = cast(List[ParamType], option_loading_fn())
                    if options is not None and len(options) > 0:
                        if config_key in cache.get_keys():
                            cache.update_options(config_key, options)
                        else:
                            AppConfig().update_options(config_key, options)
                except (KeyError, RuntimeError) as err:
                    logger.error(f'error loading {config_key} from {self._server_url}: {err}')

            data_params = (
                (Cache.STYLES, self._webservice.get_styles),
                (Cache.CONTROLNET_CONTROL_TYPES, self._webservice.get_controlnet_control_types),
                (Cache.CONTROLNET_MODULES, self._webservice.get_controlnet_modules),
                (Cache.CONTROLNET_MODELS, self._webservice.get_controlnet_models),
                (Cache.LORA_MODELS, self._webservice.get_loras)
            )

            for config_key, data_loading_fn in data_params:
                try:
                    value = data_loading_fn()
                    if value is not None and len(value) > 0:
                        cache.set(config_key, value)
                except (KeyError, RuntimeError) as err:
                    logger.error(f'error loading {config_key} from {self._server_url}: {err}')
            # Build ControlNet tab:
            if cache.get(cache.CONTROLNET_VERSION) > 0 and self._controlnet_tab is None:
                controlnet_panel = TabbedControlnetPanel(Cache().get(Cache.CONTROLNET_CONTROL_TYPES),
                                                         Cache().get(Cache.CONTROLNET_MODULES),
                                                         Cache().get(Cache.CONTROLNET_MODELS))
                self._controlnet_tab = Tab(CONTROLNET_TITLE, controlnet_panel)
                self._controlnet_tab.setIcon(QIcon(CONTROLNET_TAB_ICON))

            return True
        except AuthError:
            return False

    def disconnect_or_disable(self) -> None:
        """Closes any connections, unloads models, or otherwise turns off this generator."""
        if self._webservice is not None:
            self._webservice.disconnect()
            self._webservice = None
        # Clear cached webservice data:
        if self._lora_images is not None:
            self._lora_images.clear()
            self._lora_images = None
        cache = Cache()
        cache.set(Cache.CONTROLNET_VERSION, -1.0)
        cache.set(Cache.CONTROLNET_CONTROL_TYPES, {})
        cache.set(Cache.CONTROLNET_MODULES, {})
        cache.set(Cache.CONTROLNET_MODELS, {})
        cache.set(Cache.LORA_MODELS, [])
        if self._controlnet_tab is not None:
            self._controlnet_tab.setParent(None)
            self._controlnet_tab.deleteLater()
            self._controlnet_tab = None
            self._controlnet_panel = None
        self.clear_menus()

    def init_settings(self, settings_modal: SettingsModal) -> None:
        """Updates a settings modal to add settings relevant to this generator."""
        assert self._webservice is not None
        web_config = A1111Config()
        web_config.load_all(self._webservice)
        settings_modal.load_from_config(web_config)
        app_config = AppConfig()
        settings_modal.load_from_config(app_config, [STABLE_DIFFUSION_CONFIG_CATEGORY])

    def refresh_settings(self, settings_modal: SettingsModal) -> None:
        """Reloads current values for this generator's settings, and updates them in the settings modal."""
        assert self._webservice is not None
        settings = self._webservice.get_config()
        app_config = AppConfig()
        for key in app_config.get_category_keys(STABLE_DIFFUSION_CONFIG_CATEGORY):
            settings[key] = app_config.get(key)
        settings_modal.update_settings(settings)

    def update_settings(self, changed_settings: dict[str, Any]) -> None:
        """Applies any changed settings from a SettingsModal that are relevant to the image generator and require
           special handling."""
        assert self._webservice is not None
        web_config = A1111Config()
        web_categories = web_config.get_categories()
        web_keys = [key for cat in web_categories for key in web_config.get_category_keys(cat)]
        app_keys = AppConfig().get_category_keys(STABLE_DIFFUSION_CONFIG_CATEGORY)
        web_changes = {}
        for key, value in changed_settings.items():
            if key in web_keys:
                web_changes[key] = value
            elif key in app_keys and not isinstance(value, (list, dict)):
                AppConfig().set(key, value)
        if len(web_changes) > 0:
            def _update_config() -> None:
                assert self._webservice is not None
                self._webservice.set_config(changed_settings)
            update_task = AsyncTask(_update_config, True)

            def _update_setting():
                AppStateTracker.set_app_state(APP_STATE_EDITING if self._image_stack.has_image else APP_STATE_NO_IMAGE)
                update_task.finish_signal.disconnect(_update_setting)
            update_task.finish_signal.connect(_update_setting)
            update_task.start()

    def unload_settings(self, settings_modal: SettingsModal) -> None:
        """Unloads this generator's settings from the settings modal."""
        settings_modal.remove_category(A1111Config(), STABLE_DIFFUSION_CONFIG_CATEGORY)

    def interrogate(self) -> None:
        """ Calls the "interrogate" endpoint to automatically generate image prompts.

        Sends the image generation area content to the stable-diffusion-webui API, where an image captioning model
        automatically generates an appropriate prompt. Once returned, that prompt is copied to the appropriate field
        in the UI. Displays an error dialog instead if no image is loaded or another API operation is in-progress.
        """
        assert self._webservice is not None
        if not self._image_stack.has_image:
            show_error_dialog(None, INTERROGATE_ERROR_TITLE, INTERROGATE_ERROR_MESSAGE_NO_IMAGE)
            return
        image = self._image_stack.qimage_generation_area_content()

        class _InterrogateTask(AsyncTask):
            prompt_ready = Signal(str)
            error_signal = Signal(Exception)

            def signals(self) -> List[Signal]:
                return [self.prompt_ready, self.error_signal]

        def _interrogate(prompt_ready: Signal, error_signal: Signal) -> None:
            try:
                assert self._webservice is not None
                prompt_ready.emit(self._webservice.interrogate(image))
            except (RuntimeError, AssertionError) as err:
                logger.error(f'err:{err}')
                error_signal.emit(err)

        task = _InterrogateTask(_interrogate)
        AppStateTracker.set_app_state(APP_STATE_LOADING)

        def set_prompt(prompt_text: str) -> None:
            """Update the image prompt in config with the interrogate results."""
            AppConfig().set(AppConfig.PROMPT, prompt_text)

        task.prompt_ready.connect(set_prompt)

        def handle_error(err: BaseException) -> None:
            """Show an error popup if interrogate fails."""
            assert self._window is not None
            self._window.set_is_loading(False)
            show_error_dialog(self._window, INTERROGATE_ERROR_TITLE, err)

        task.error_signal.connect(handle_error)

    def get_control_panel(self) -> QWidget:
        """Returns a widget with inputs for controlling this generator."""
        if self._control_panel is None:
            self._control_panel = SDWebUIPanel()
            self._control_panel.generate_signal.connect(self.start_and_manage_image_generation)
            self._control_panel.interrogate_signal.connect(self.interrogate)
        return self._control_panel

    def _async_progress_check(self, external_status_signal: Optional[Signal] = None):
        webservice = self._webservice
        assert webservice is not None

        class _ProgressTask(AsyncTask):
            status_signal = Signal(dict)

            def __init__(self) -> None:
                super().__init__(self._check_progress)
                self.should_stop = False

            def signals(self) -> List[Signal]:
                return [external_status_signal if external_status_signal is not None else self.status_signal]

            def _check_progress(self, status_signal) -> None:
                init_timestamp: Optional[float] = None
                error_count = 0
                max_progress = 0
                while not self.should_stop:
                    sleep_time = min(MIN_RETRY_US * pow(2, error_count), MAX_RETRY_US)
                    thread = QThread.currentThread()
                    assert thread is not None
                    thread.usleep(sleep_time)
                    try:
                        assert webservice is not None
                        status = webservice.progress_check()
                        progress_percent = int(status[PROGRESS_KEY_FRACTION] * 100)
                        if progress_percent < max_progress or progress_percent >= 100:
                            break
                        if progress_percent <= 1:
                            continue
                        status_text = f'{progress_percent}%'
                        max_progress = progress_percent
                        if PROGRESS_KEY_ETA_RELATIVE in status and status[PROGRESS_KEY_ETA_RELATIVE] != 0:
                            timestamp = datetime.datetime.now().timestamp()
                            if init_timestamp is None:
                                init_timestamp = timestamp
                            else:
                                seconds_passed = timestamp - init_timestamp
                                fraction_complete = status[PROGRESS_KEY_FRACTION]
                                eta_sec = int(seconds_passed / fraction_complete)
                                minutes = eta_sec // 60
                                seconds = eta_sec % 60
                                if minutes > 0:
                                    status_text = f'{status_text} ETA: {minutes}:{seconds}'
                                else:
                                    status_text = f'{status_text} ETA: {seconds}s'
                        status_signal.emit({'progress': status_text})
                    except RuntimeError as err:
                        error_count += 1
                        print(f'Error {error_count}: {err}')
                        if error_count > MAX_ERROR_COUNT:
                            logger.error('Inpainting failed, reached max retries.')
                            break
                        continue

        task = _ProgressTask()
        assert self._window is not None
        if external_status_signal is None:
            task.status_signal.connect(self._apply_status_update)

            def _finish():
                task.status_signal.disconnect(self._apply_status_update)
                task.finish_signal.disconnect(_finish)

            task.finish_signal.connect(_finish)
        task.start()

    def upscale(self, new_size: QSize) -> bool:
        """Upscale using AI upscaling modes provided by stable-diffusion-webui, returning whether upscaling
        was attempted."""
        assert self._window is not None
        width = self._image_stack.width
        height = self._image_stack.height
        if new_size.width() <= width and new_size.height() <= height:
            return False

        class _UpscaleTask(AsyncTask):
            image_ready = Signal(QImage)
            error_signal = Signal(Exception)

            def signals(self) -> List[Signal]:
                return [self.image_ready, self.error_signal]

        def _upscale(image_ready: Signal, error_signal: Signal) -> None:
            try:
                assert self._webservice is not None
                images, info = self._webservice.upscale(self._image_stack.qimage(), new_size.width(),
                                                        new_size.height())
                if info is not None:
                    logger.debug(f'Upscaling result info: {info}')
                image_ready.emit(images[-1])
            except IOError as err:
                error_signal.emit(err)

        task = _UpscaleTask(_upscale, True)

        def handle_error(err: IOError) -> None:
            """Show an error dialog if upscaling fails."""
            show_error_dialog(self._window, UPSCALE_ERROR_TITLE, err)

        task.error_signal.connect(handle_error)

        def apply_upscaled(img: QImage) -> None:
            """Copy the upscaled image into the image stack."""
            self._image_stack.load_image(img)

        task.image_ready.connect(apply_upscaled)

        def _on_finish() -> None:
            assert self._window is not None
            self._window.set_is_loading(False)
            task.error_signal.disconnect(handle_error)
            task.image_ready.disconnect(apply_upscaled)
            task.finish_signal.disconnect(_on_finish)

        task.finish_signal.connect(_on_finish)
        self._async_progress_check()
        task.start()
        return True

    def generate(self,
                 status_signal: Signal,
                 source_image: Optional[QImage] = None,
                 mask_image: Optional[QImage] = None) -> None:
        """Generates new images. Image size, image count, prompts, etc. are loaded from AppConfig as needed.

        Parameters
        ----------
        status_signal : Signal[str]
            Signal to emit when status updates are available.
        source_image : QImage, optional
            Image used as a basis for the edited image.
        mask_image : QImage, optional
            Mask marking edited image region.
        """
        assert self._webservice is not None
        edit_mode = AppConfig().get(AppConfig.EDIT_MODE)
        if edit_mode == EDIT_MODE_INPAINT and self._image_stack.selection_layer.generation_area_fully_selected():
            edit_mode = EDIT_MODE_IMG2IMG
        if edit_mode != EDIT_MODE_INPAINT:
            mask_image = None
        elif self._image_stack.selection_layer.generation_area_is_empty():
            raise RuntimeError(GENERATE_ERROR_MESSAGE_EMPTY_MASK)

            # Check progress before starting:
        assert self._webservice is not None
        init_data = self._webservice.progress_check()
        if init_data[PROGRESS_KEY_CURRENT_IMAGE] is not None:
            raise RuntimeError(ERROR_MESSAGE_EXISTING_OPERATION)
        self._async_progress_check(status_signal)
        try:
            if edit_mode == EDIT_MODE_TXT2IMG:
                gen_size = AppConfig().get(AppConfig.GENERATION_SIZE)
                width = gen_size.width()
                height = gen_size.height()
                image_data, info = self._webservice.txt2img(width, height, image=source_image)
            else:
                assert source_image is not None
                image_data, info = self._webservice.img2img(source_image, mask=mask_image)
            if info is not None:
                logger.debug(f'Image generation result info: {info}')
            for i, response_image in enumerate(image_data):
                self._cache_generated_image(response_image, i)

        except RuntimeError as image_gen_error:
            logger.error(f'request failed: {image_gen_error}')

    @menu_action(MENU_TOOLS, 'lcm_mode_shortcut', 99, condition_check=_check_lcm_mode_available)
    def set_lcm_mode(self) -> None:
        """Apply all settings required for using an LCM LoRA module."""
        config = AppConfig()
        loras = [lora['name'] for lora in Cache().get(Cache.LORA_MODELS)]
        if LCM_LORA_1_5 in loras:
            lora_name = LCM_LORA_1_5
        else:
            lora_name = LCM_LORA_XL
        lora_key = f'<lora:{lora_name}:1>'
        prompt = config.get(AppConfig.PROMPT)
        if lora_key not in prompt:
            config.set(AppConfig.PROMPT, f'{prompt} {lora_key}')
        config.set(AppConfig.GUIDANCE_SCALE, 1.5)
        config.set(AppConfig.SAMPLING_STEPS, 8)
        config.set(AppConfig.SAMPLING_METHOD, 'LCM')
        config.set(AppConfig.SEED, -1)
        if config.get(AppConfig.BATCH_SIZE) < 5:
            config.set(AppConfig.BATCH_SIZE, 5)

    def _update_styles(self, style_list: List[Dict[str, str]]) -> None:
        try:
            assert self._webservice is not None
            self._webservice.set_styles(style_list)
        except RuntimeError as err:
            show_error_dialog(None, STYLE_ERROR_TITLE, err)
            return
        style_strings = [json.dumps(style) for style in style_list]
        Cache().update_options(Cache.STYLES, cast(List[ParamType], style_strings))

    @menu_action(MENU_STABLE_DIFFUSION, 'prompt_style_shortcut', 200, [APP_STATE_EDITING],
                 condition_check=_check_prompt_styles_available)
    def show_style_window(self) -> None:
        """Show the saved prompt style window."""
        style_window = PromptStyleWindow()
        # TODO: update after the prompt style endpoint gets POST support
        # style_window.should_save_changes.connect(self._update_styles)
        style_window.exec()

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

                def signals(self) -> List[Signal]:
                    return [self.status]

            def _load_and_open(status_signal: Signal) -> None:
                for i, lora in enumerate(loras):
                    status_signal.emit(f'Loading thumbnail {i + 1}/{len(loras)}')
                    path = lora['path']
                    path = path[:path.rindex('.')] + '.png'
                    assert self._lora_images is not None
                    assert self._webservice is not None
                    self._lora_images[lora['name']] = self._webservice.get_thumbnail(path)

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
