"""
Provides image editing functionality through the A1111/stable-diffusion-webui REST API.
"""
import datetime
import json
import logging
import os
import sys
from argparse import Namespace
from typing import Optional, Callable, Any, Dict, List, cast

import requests
from PIL import Image
from PyQt5.QtCore import pyqtSignal, QSize, QThread
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QInputDialog

from src.api.a1111_webservice import A1111Webservice
from src.config.a1111_config import A1111Config
from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.base_controller import BaseInpaintController, MENU_TOOLS
from src.ui.modal.modal_utils import show_error_dialog
from src.ui.modal.settings_modal import SettingsModal
from src.ui.window.extra_network_window import ExtraNetworkWindow
from src.ui.window.prompt_style_window import PromptStyleWindow
from src.ui.window.stable_diffusion_main_window import StableDiffusionMainWindow
from src.util.application_state import APP_STATE_EDITING, AppStateTracker, APP_STATE_LOADING, APP_STATE_NO_IMAGE
from src.util.async_task import AsyncTask
from src.util.display_size import get_screen_size
from src.util.menu_builder import menu_action
from src.util.parameter import ParamType
from src.util.shared_constants import EDIT_MODE_INPAINT, EDIT_MODE_TXT2IMG, EDIT_MODE_IMG2IMG

STABLE_DIFFUSION_CONFIG_CATEGORY = 'Stable-Diffusion'

logger = logging.getLogger(__name__)

AUTH_ERROR_DETAIL_KEY = 'detail'
AUTH_ERROR_MESSAGE = 'Not authenticated'
INTERROGATE_ERROR_MESSAGE_NO_IMAGE = 'Open or create an image first.'
INTERROGATE_ERROR_MESSAGE_EXISTING_OPERATION = 'Existing operation currently in progress'
INTERROGATE_ERROR_TITLE = 'Interrogate failure'
INTERROGATE_LOADING_TEXT = 'Running CLIP interrogate'
URL_REQUEST_TITLE = 'Inpainting UI'
URL_REQUEST_MESSAGE = 'Enter server URL:'
URL_REQUEST_RETRY_MESSAGE = 'Server connection failed, enter a new URL or click "OK" to retry'
CONTROLNET_MODEL_LIST_KEY = 'model_list'
UPSCALE_ERROR_TITLE = 'Upscale failure'
PROGRESS_KEY_CURRENT_IMAGE = 'current_image'
PROGRESS_KEY_FRACTION = "progress"
PROGRESS_KEY_ETA_RELATIVE = 'eta_relative'
STYLE_ERROR_TITLE = 'Updating prompt styles failed'

GENERATE_ERROR_TITLE = "Image generation failed"
GENERATE_ERROR_MESSAGE_EMPTY_MASK = ("Selection mask was empty. Either use the mask tool to mark part of the image"
                                     " generation area for inpainting, or switch to another image generation mode.")

MAX_ERROR_COUNT = 10
MIN_RETRY_US = 300000
MAX_RETRY_US = 60000000

LCM_SAMPLER = 'LCM'
LCM_LORA_1_5 = 'lcm-lora-sdv1-5'
LCM_LORA_XL = 'lcm-lora-sdxl'

MENU_STABLE_DIFFUSION = 'Stable-Diffusion'


def _check_lcm_mode_available(_) -> bool:
    if LCM_SAMPLER not in AppConfig.instance().get_options(AppConfig.SAMPLING_METHOD):
        return False
    loras = [lora['name'] for lora in Cache.instance().get(Cache.LORA_MODELS)]
    return LCM_LORA_1_5 in loras or LCM_LORA_XL in loras


def _check_prompt_styles_available(_) -> bool:
    cache = Cache.instance()
    return len(cache.get_options(Cache.STYLES)) > 0


def _check_lora_available(_) -> bool:
    cache = Cache.instance()
    return len(cache.get(Cache.LORA_MODELS)) > 0


class StableDiffusionController(BaseInpaintController):
    """StableDiffusionController using the A1111/stable-diffusion-webui REST API to handle image operations. """

    def __init__(self, args: Namespace) -> None:
        """Starts the application and creates the main window on init.

        Parameters
        ----------
        args : Namespace
            Command-line arguments, as generated by the argparse module
        """
        self._server_url = args.server_url
        super().__init__(args)
        self._webservice = A1111Webservice(args.server_url)
        self._window: Optional[StableDiffusionMainWindow] = None
        self._lora_images: Optional[Dict[str, Optional[QImage]]] = None

        # Login automatically if username/password are defined as env variables.
        # Obviously this isn't terribly secure, but A1111 auth security is already pretty minimal, and I'm just using
        # this for testing.
        if 'SD_UNAME' in os.environ and 'SD_PASS' in os.environ:
            self._webservice.login(os.environ['SD_UNAME'], os.environ['SD_PASS'])
            self._webservice.set_auth((os.environ['SD_UNAME'], os.environ['SD_PASS']))

    def get_config_categories(self) -> List[str]:
        """Return the list of AppConfig categories this controller supports."""
        categories = super().get_config_categories()
        categories.append(STABLE_DIFFUSION_CONFIG_CATEGORY)
        return categories

    def init_settings(self, settings_modal: SettingsModal) -> None:
        """Adds relevant stable-diffusion-webui settings to a ui.modal SettingsModal.  """
        super().init_settings(settings_modal)
        if not isinstance(self._webservice, A1111Webservice):
            print('Disabling remote settings: only supported with the A1111 API')
            return
        web_config = A1111Config.instance()
        web_config.load_all(self._webservice)
        settings_modal.load_from_config(web_config)

    def refresh_settings(self, settings_modal: SettingsModal) -> None:
        """Loads current settings from the webui and applies them to the SettingsModal."""
        super().refresh_settings(settings_modal)
        settings = self._webservice.get_config()
        settings_modal.update_settings(settings)

    def update_settings(self, changed_settings: dict[str, Any]) -> None:
        """Applies changed settings from a SettingsModal to the stable-diffusion-webui."""
        super().update_settings(changed_settings)
        web_config = A1111Config.instance()
        web_categories = web_config.get_categories()
        web_keys = [key for cat in web_categories for key in web_config.get_category_keys(cat)]
        web_changes = {}
        for key in changed_settings:
            if key in web_keys:
                web_changes[key] = changed_settings[key]
        if len(web_changes) > 0:
            def _update_config() -> None:
                self._webservice.set_config(changed_settings)
            update_task = AsyncTask(_update_config, True)
            update_task.finish_signal.connect(lambda: AppStateTracker.set_app_state(
                APP_STATE_EDITING if self._image_stack.has_image else APP_STATE_NO_IMAGE))
            update_task.start()

    @staticmethod
    def health_check(url: Optional[str] = None, webservice: Optional[A1111Webservice] = None) -> bool:
        """Static method to check if the stable-diffusion-webui API is available.

        Parameters
        ----------
        url : str
            URL to check for the stable-diffusion-webui API.
        webservice : A1111Webservice, optional
            If provided, the url param will be ignored and this object will be used to check the connection.
        Returns
        -------
        bool
            Whether the API is available through the provided URL or webservice object.
        """
        try:
            if webservice is None:
                res = requests.get(url, timeout=20)
            else:
                res = webservice.login_check()
            if res.status_code == 200 or (res.status_code == 401
                                          and res.json()[AUTH_ERROR_DETAIL_KEY] == AUTH_ERROR_MESSAGE):
                return True
            raise RuntimeError(f'{res.status_code} : {res.text}')
        except RuntimeError as status_err:
            logger.error(f'Login check returned failure response: {status_err}')
            return False
        except requests.exceptions.RequestException as req_err:
            logger.error(f'Login check connection failed: {req_err}')
            return False

    def interrogate(self) -> None:
        """ Calls the "interrogate" endpoint to automatically generate image prompts.

        Sends the image generation area content to the stable-diffusion-webui API, where an image captioning model
        automatically generates an appropriate prompt. Once returned, that prompt is copied to the appropriate field
        in the UI. Displays an error dialog instead if no image is loaded or another API operation is in-progress.
        """
        if not self._image_stack.has_image:
            show_error_dialog(self._window, INTERROGATE_ERROR_TITLE, INTERROGATE_ERROR_MESSAGE_NO_IMAGE)
            return

        class _InterrogateTask(AsyncTask):
            prompt_ready = pyqtSignal(str)
            error_signal = pyqtSignal(Exception)

            def signals(self) -> List[pyqtSignal]:
                return [self.prompt_ready, self.error_signal]

        def _interrogate(prompt_ready, error_signal):
            try:
                image = self._image_stack.pil_image_generation_area_content()
                prompt_ready.emit(self._webservice.interrogate(image))
            except RuntimeError as err:
                logger.error(f'err:{err}')
                error_signal.emit(err)

        task = _InterrogateTask(_interrogate)
        AppStateTracker.set_app_state(APP_STATE_LOADING)

        def set_prompt(prompt_text: str) -> None:
            """Update the image prompt in config with the interrogate results."""
            AppConfig.instance().set(AppConfig.PROMPT, prompt_text)
        task.prompt_ready.connect(set_prompt)

        def handle_error(err: BaseException) -> None:
            """Show an error popup if interrogate fails."""
            assert self._window is not None
            self._window.set_is_loading(False)
            show_error_dialog(self._window, INTERROGATE_ERROR_TITLE, err)
        task.error_signal.connect(handle_error)
        task.finish_signal.connect(lambda: AppStateTracker.set_app_state(APP_STATE_EDITING))
        assert self._window is not None
        self._window.set_loading_message(INTERROGATE_LOADING_TEXT)
        task.start()

    def window_init(self) -> None:
        """Creates and shows the main editor window."""

        # Make sure a valid connection exists:
        def prompt_for_url(prompt_text: str) -> None:
            """Open a dialog box to get the server URL from the user."""
            new_url, url_entered = QInputDialog.getText(self._window, URL_REQUEST_TITLE, prompt_text)
            if not url_entered:  # User clicked 'Cancel'
                sys.exit()
            if new_url != '':
                self._server_url = new_url

        # Get URL if one was not provided on the command line:
        while self._server_url == '':
            prompt_for_url(URL_REQUEST_MESSAGE)

        # Check connection:
        while not StableDiffusionController.health_check(webservice=self._webservice):
            prompt_for_url(URL_REQUEST_RETRY_MESSAGE)
        cache = Cache.instance()
        try:
            cache.set(Cache.CONTROLNET_VERSION, float(self._webservice.get_controlnet_version()))
        except RuntimeError:
            # The webui fork at lllyasviel/stable-diffusion-webui-forge is mostly compatible with the A1111 API, but
            # it doesn't have the ControlNet version endpoint. Before assuming ControlNet isn't installed, check if
            # the ControlNet model list endpoint returns anything:
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

        option_loading_params = (
            (Cache.STYLES, self._webservice.get_styles),
            (AppConfig.SAMPLING_METHOD, self._webservice.get_samplers),
            (AppConfig.UPSCALE_METHOD, self._webservice.get_upscalers)
        )

        # load various option lists:
        for config_key, option_loading_fn in option_loading_params:
            try:
                options = option_loading_fn()
                if options is not None and len(options) > 0:
                    if config_key in cache.get_keys():
                        cache.update_options(config_key, options)
                    else:
                        AppConfig.instance().update_options(config_key, options)
            except (KeyError, RuntimeError) as err:
                logger.error(f'error loading {config_key} from {self._server_url}: {err}')

        data_params = (
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

        # initialize remote options modal:
        # Handle final window init now that data is loaded from the API:
        self._window = StableDiffusionMainWindow(self._image_stack, self)
        if self._fixed_window_size is not None:
            size = self._fixed_window_size
            self._window.setGeometry(0, 0, size.width(), size.height())
            self._window.setMaximumSize(self._fixed_window_size)
            self._window.setMinimumSize(self._fixed_window_size)
        else:
            size = get_screen_size(self._window)
            self._window.setGeometry(0, 0, size.width(), size.height())
            self._window.setMaximumSize(size)
        self.fix_styles()
        if self._init_image is not None:
            logger.info('loading init image:')
            self.load_image(file_path=self._init_image)
        self._window.show()

    def _async_progress_check(self, external_status_signal: Optional[pyqtSignal] = None):
        webservice = self._webservice

        class _ProgressTask(AsyncTask):
            status_signal = pyqtSignal(dict)

            def __init__(self) -> None:
                super().__init__(self._check_progress)
                self.should_stop = False

            def signals(self) -> List[pyqtSignal]:
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
        task.start()

    def _scale(self, new_size: QSize) -> None:
        """Provide extra upscaling modes using stable-diffusion-webui."""
        assert self._window is not None
        width = self._image_stack.width
        height = self._image_stack.height
        # If downscaling, use base implementation:
        if new_size.width() <= width and new_size.height() <= height:
            super()._scale(new_size)
            return

        # If upscaling, use stable-diffusion-webui upscale api:

        class _UpscaleTask(AsyncTask):
            image_ready = pyqtSignal(Image.Image)
            error_signal = pyqtSignal(Exception)

            def signals(self) -> List[pyqtSignal]:
                return [self.image_ready, self.error_signal]

        def _upscale(image_ready: pyqtSignal, error_signal: pyqtSignal) -> None:
            try:
                images, info = self._webservice.upscale(self._image_stack.pil_image(), new_size.width(),
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

        def apply_upscaled(img: Image.Image) -> None:
            """Copy the upscaled image into the image stack."""
            self._image_stack.set_image(img)

        task.image_ready.connect(apply_upscaled)
        def _on_finish() -> None:
            assert self._window is not None
            self._window.set_is_loading(False)
        task.finish_signal.connect(_on_finish)
        self._async_progress_check()
        task.start()

    def _inpaint(self,
                 source_image_section: Image.Image,
                 mask: Image.Image,
                 save_image: Callable[[Image.Image, int], None],
                 status_signal: pyqtSignal) -> None:
        """Handle image editing operations using stable-diffusion-webui.

        Parameters
        ----------
        source_image_section : PIL Image, optional
            Image selection to edit
        mask : PIL Image, optional
            Mask marking edited image region.
        save_image : function (PIL Image, int)
            Function used to return each image response and its index.
        status_signal : pyqtSignal
            Signal to emit when status updates are available.
        """
        edit_mode = AppConfig.instance().get(AppConfig.EDIT_MODE)
        if edit_mode == EDIT_MODE_INPAINT and self._image_stack.selection_layer.generation_area_fully_selected():
            edit_mode = EDIT_MODE_IMG2IMG
        if edit_mode != EDIT_MODE_INPAINT:
            mask = None
        elif self._image_stack.selection_layer.generation_area_is_empty():
            raise RuntimeError(GENERATE_ERROR_MESSAGE_EMPTY_MASK)

        # Check progress before starting:
        init_data = self._webservice.progress_check()
        if init_data[PROGRESS_KEY_CURRENT_IMAGE] is not None:
            raise RuntimeError('Image generation in progress, try again later.')
        self._async_progress_check(status_signal)

        try:
            if edit_mode == EDIT_MODE_TXT2IMG:
                image_data, info = self._webservice.txt2img(source_image_section.width, source_image_section.height,
                                                            image=source_image_section)
            else:
                image_data, info = self._webservice.img2img(source_image_section, mask=mask)
            if info is not None:
                logger.debug(f'Image generation result info: {info}')
            for i, response_image in enumerate(image_data):
                save_image(response_image, i)

        except RuntimeError as image_gen_error:
            logger.error(f'request failed: {image_gen_error}')

    def _apply_status_update(self, status_dict: Dict[str, str]) -> None:
        """Show status updates in the UI."""
        assert self._window is not None
        if 'seed' in status_dict:
            Cache.instance().set(Cache.LAST_SEED, str(status_dict['seed']))
        if 'progress' in status_dict:
            self._window.set_loading_message(status_dict['progress'])

    @menu_action(MENU_TOOLS, 'lcm_mode_shortcut', 99, condition_check=_check_lcm_mode_available)
    def set_lcm_mode(self) -> None:
        """Apply all settings required for using an LCM LoRA module."""
        config = AppConfig.instance()
        loras = [lora['name'] for lora in Cache.instance().get(Cache.LORA_MODELS)]
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
            self._webservice.set_styles(style_list)
        except RuntimeError as err:
            show_error_dialog(None, STYLE_ERROR_TITLE, err)
            return
        style_strings = [json.dumps(style) for style in style_list]
        Cache.instance().update_options(Cache.STYLES, cast(List[ParamType], style_strings))

    @menu_action(MENU_STABLE_DIFFUSION, 'prompt_style_shortcut', 200, [APP_STATE_EDITING],
                 condition_check=_check_prompt_styles_available)
    def show_style_window(self) -> None:
        """Show the saved prompt style window."""
        style_window = PromptStyleWindow()
        # TODO: update after the prompt style endpoint gets POST support
        # style_window.should_save_changes.connect(self._update_styles)
        style_window.exec_()

    @menu_action(MENU_STABLE_DIFFUSION, 'lora_shortcut', 201, [APP_STATE_EDITING],
                 condition_check=_check_lora_available)
    def show_lora_window(self) -> None:
        """Show the Lora model selection window."""
        cache = Cache.instance()
        loras = cache.get(Cache.LORA_MODELS).copy()
        if self._lora_images is None:
            self._lora_images = {}
            AppStateTracker.set_app_state(APP_STATE_LOADING)

            class _LoadingTask(AsyncTask):
                status = pyqtSignal(str)

                def signals(self) -> List[pyqtSignal]:
                    return [self.status]

            def _load_and_open(status_signal: pyqtSignal) -> None:
                for i, lora in enumerate(loras):
                    status_signal.emit(f'Loading thumbnail {i+1}/{len(loras)}')
                    path = lora['path']
                    path = path[:path.rindex('.')] + '.png'
                    assert self._lora_images is not None
                    self._lora_images[lora['name']] = self._webservice.get_thumbnail(path)

            task = _LoadingTask(_load_and_open)

            def _resume_and_show() -> None:
                AppStateTracker.set_app_state(APP_STATE_EDITING)
                assert self._lora_images is not None
                delayed_lora_window = ExtraNetworkWindow(loras, self._lora_images)
                delayed_lora_window.exec_()

            assert self._window is not None
            task.status.connect(self._window.set_loading_message)
            task.finish_signal.connect(_resume_and_show)
            task.start()
        else:
            lora_window = ExtraNetworkWindow(loras, self._lora_images)
            lora_window.exec_()
