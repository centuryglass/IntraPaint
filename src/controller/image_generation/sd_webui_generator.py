"""Generates images through the Stable-Diffusion WebUI (A1111 or Forge)"""
import logging
import os
from argparse import Namespace
from typing import Optional, Any, cast

from PySide6.QtCore import Signal, QSize, QThread
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from requests import ReadTimeout

from src.api.a1111_webservice import A1111Webservice, AuthError
from src.api.controlnet.controlnet_constants import ControlTypeDef
from src.api.controlnet.controlnet_preprocessor import ControlNetPreprocessor
from src.api.webservice import WebService
from src.config.a1111_config import A1111Config
from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_generation.sd_generator import SD_BASE_DESCRIPTION, STABLE_DIFFUSION_CONFIG_CATEGORY, \
    SDGenerator
from src.image.layers.image_stack import ImageStack
from src.ui.modal.modal_utils import show_error_dialog
from src.ui.modal.settings_modal import SettingsModal
from src.ui.panel.generators.generator_panel import GeneratorPanel
from src.ui.panel.generators.stable_diffusion_panel import StableDiffusionPanel
from src.ui.panel.generators.webui_extras_tab import WebUIExtrasTab
from src.ui.window.main_window import MainWindow
from src.ui.window.prompt_style_window import PromptStyleWindow
from src.undo_stack import UndoStack
from src.util.application_state import AppStateTracker, APP_STATE_LOADING, APP_STATE_EDITING, APP_STATE_NO_IMAGE
from src.util.async_task import AsyncTask
from src.util.menu_builder import menu_action
from src.util.shared_constants import EDIT_MODE_TXT2IMG, EDIT_MODE_INPAINT, EDIT_MODE_IMG2IMG, PROJECT_DIR, \
    AUTH_ERROR, AUTH_ERROR_MESSAGE, INTERROGATE_ERROR_TITLE, INTERROGATE_ERROR_MESSAGE_NO_IMAGE, \
    ERROR_MESSAGE_TIMEOUT, \
    GENERATE_ERROR_MESSAGE_EMPTY_MASK, ERROR_MESSAGE_EXISTING_OPERATION

logger = logging.getLogger(__name__)

# The QCoreApplication.translate context for strings in this file
TR_ID = 'controller.image_generation.sd_webui_generator'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


SD_WEBUI_GENERATOR_NAME = _tr('Stable-Diffusion WebUI API')
SD_WEBUI_GENERATOR_DESCRIPTION_HEADER = _tr('<h2>Stable-Diffusion: via WebUI API</h2>')
SD_WEBUI_GENERATOR_DESCRIPTION_WEBUI = _tr("""
<p>
    The Stable-Diffusion WebUI is one of the first interfaces created for using Stable-Diffusion. This IntraPaint
    generator offloads image generation to that system through a network connection.  The WebUI instance can be run on
    the same computer as IntraPaint, or remotely on a separate server.
</p>
""")

SD_WEBUI_GENERATOR_DESCRIPTION = (f'{SD_WEBUI_GENERATOR_DESCRIPTION_HEADER}\n{SD_BASE_DESCRIPTION}'
                                  f'\n{SD_WEBUI_GENERATOR_DESCRIPTION_WEBUI}')

# noinspection SpellCheckingInspection
SD_WEBUI_GENERATOR_SETUP = _tr("""
<h2>Installing Stable-Diffusion</h2>
<p>
    To use this Stable-Diffusion image generator with IntraPaint, you will need to install the Stable-Diffusion WebUI.
    You can choose either the <a href="https://github.com/lllyasviel/stable-diffusion-webui-forge">Forge WebUI</a>
    or the original <a href="https://github.com/AUTOMATIC1111/stable-diffusion-webui"> Stable-Diffusion WebUI</a>, but
    the Forge WebUI is the recommended version. The easiest way to install either of these options is through <a href=
    "https://github.com/LykosAI/StabilityMatrix">Stability Matrix</a>.
</p>
<ol>
    <li>
        Install the appropriate version of Stability Matrix for your system:
        <ul>
            <li>
                <a
                 href="https://github.com/LykosAI/StabilityMatrix/releases/latest/download/StabilityMatrix-win-x64.zip"
                 >Windows 10, 11
                </a>
            </li>
            <li>
                <a
                href="https://github.com/LykosAI/StabilityMatrix/releases/latest/download/StabilityMatrix-linux-x64.zip"
                >Linux AppImage
                </a>
            </li>
            <li><a href="https://aur.archlinux.org/packages/stabilitymatrix"> Arch Linux AUR</a></li>
            <li>
                <a
              href="https://github.com/LykosAI/StabilityMatrix/releases/latest/download/StabilityMatrix-macos-arm64.dmg"
                 >macOS, Apple Silicon
                </a>
            </li>
        </ul>
    </li>
    <li>
        Open Stability Matrix, click "Add Package", select "Stable Diffusion WebUI Forge",and wait for it to install.
    </li>
    <li>
        Once the installation finishes, click the gear icon next to Forge on the package screen to open launch options.
         Scroll to the bottom of the launch options, add "--api" to "Extra Launch Arguments", and click "Save".
    </li>
    <li>Click "Launch", and wait for the WebUI to finish starting up.</li>
    <li>
        Once the WebUI has started completely, you should be able to click "Activate" below, and IntraPaint will
        connect to it automatically.  If you configure the WebUI to use any URL other than the default or to use a
        username and password, IntraPaint will ask for that information before connecting.
    </li>
</ol>
""")
SD_PREVIEW_IMAGE = f'{PROJECT_DIR}/resources/generator_preview/stable-diffusion.png'
ICON_PATH_CONTROLNET_TAB = f'{PROJECT_DIR}/resources/icons/tabs/hex.svg'
DEFAULT_WEBUI_URL = 'http://localhost:7860'
AUTH_ERROR_DETAIL_KEY = 'detail'
STYLE_ERROR_TITLE = _tr('Updating prompt styles failed')

ERROR_TITLE_SETTINGS_LOAD_FAILED = _tr('Failed to load Stable-Diffusion settings')
ERROR_TITLE_SETTINGS_SAVE_FAILED = _tr('Failed to save Stable-Diffusion settings')
ERROR_MESSAGE_SETTINGS_LOAD_FAILED = _tr('The connection to the Stable-Diffusion-WebUI image generator was lost. '
                                         'Connected generator settings will not be available.')
ERROR_MESSAGE_SETTINGS_SAVE_FAILED = _tr('The connection to the Stable-Diffusion-WebUI image generator was lost. '
                                         'Any changes to connected generator settings were not saved.')

MAX_ERROR_COUNT = 10
MIN_RETRY_US = 300000
MAX_RETRY_US = 60000000

MENU_STABLE_DIFFUSION = 'Stable-Diffusion'


def _check_prompt_styles_available(_) -> bool:
    cache = Cache()
    return len(cache.get(Cache.STYLES)) > 0


def _check_lora_available(_) -> bool:
    cache = Cache()
    return len(cache.get(Cache.LORA_MODELS)) > 0


class SDWebUIGenerator(SDGenerator):
    """Interface for providing image generation capabilities."""

    def __init__(self, window: MainWindow, image_stack: ImageStack, args: Namespace) -> None:
        super().__init__(window, image_stack, args, Cache.SD_WEBUI_SERVER_URL, True)
        self._webservice: Optional[A1111Webservice] = A1111Webservice(self.server_url)
        self._gen_extras_tab = WebUIExtrasTab()
        self._active_task_id = 0

    def get_display_name(self) -> str:
        """Returns a display name identifying the generator."""
        return SD_WEBUI_GENERATOR_NAME

    def get_setup_text(self) -> str:
        """Returns a rich text description of how to set up this generator."""
        return SD_WEBUI_GENERATOR_SETUP

    def get_description(self) -> str:
        """Returns an extended description of this generator."""
        return SD_WEBUI_GENERATOR_DESCRIPTION

    def get_webservice(self) -> Optional[WebService]:
        """Return the webservice object this module uses to connect to Stable-Diffusion, if initialized."""
        return self._webservice

    def remove_webservice(self) -> None:
        """Destroy and remove any active webservice object."""
        self._webservice = None

    def create_or_get_webservice(self, url: str) -> WebService:
        """Return the webservice object this module uses to connect to Stable-Diffusion.  If the webservice already
           exists but the url doesn't match, a new webservice should replace the existing one, using the new url."""
        if self._webservice is not None:
            if self._webservice.server_url == url:
                return self._webservice
            self._webservice.disconnect()
            self._webservice = None
        self._webservice = A1111Webservice(url)
        return self._webservice

    def get_controlnet_preprocessors(self) -> list[ControlNetPreprocessor]:
        """Return the list of available Controlnet preprocessors."""
        assert self._webservice is not None
        try:
            return self._webservice.get_controlnet_preprocessors()
        except (RuntimeError, KeyError) as err:
            logger.error(f'Loading ControlNet preprocessors failed: {err}')
            return []

    def get_controlnet_models(self) -> list[str]:
        """Return the list of available ControlNet models."""
        assert self._webservice is not None
        try:
            return self._webservice.get_controlnet_models()['model_list']
        except (RuntimeError, KeyError) as err:
            logger.error(f'Loading ControlNet models failed: {err}')
            return []

    def get_controlnet_types(self) -> dict[str, ControlTypeDef]:
        """Return available ControlNet categories."""
        assert self._webservice is not None
        try:
            return self._webservice.get_controlnet_type_categories()
        except (RuntimeError, KeyError) as err:
            logger.error(f'Loading ControlNet types failed: {err}')
            return {}

    def get_controlnet_unit_cache_keys(self) -> list[str]:
        """Return keys used to cache serialized ControlNet units as strings."""
        return [Cache.CONTROLNET_ARGS_0_WEBUI, Cache.CONTROLNET_ARGS_1_WEBUI, Cache.CONTROLNET_ARGS_2_WEBUI]

    def get_diffusion_model_names(self) -> list[str]:
        """Return the list of available image generation models."""
        assert self._webservice is not None
        try:
            models = self._webservice.get_models()
            return [model['model_name'] for model in models]
        except (RuntimeError, KeyError) as err:
            logger.error(f'Loading stable-diffusion model list failed: {err}')
            return []

    def get_lora_model_info(self) -> list[dict[str, str]]:
        """Return available LoRA model extensions."""
        assert self._webservice is not None
        try:
            return cast(list[dict[str, str]], self._webservice.get_loras())
        except (RuntimeError, KeyError) as err:
            logger.error(f'Loading stable-diffusion LoRA model list failed: {err}')
            return []

    def get_diffusion_sampler_names(self) -> list[str]:
        """Return the list of available samplers."""
        assert self._webservice is not None
        try:
            sampler_info = self._webservice.get_samplers()
            return [sampler['name'] for sampler in sampler_info]
        except (RuntimeError, KeyError) as err:
            logger.error(f'Loading stable-diffusion sampler option list failed: {err}')
            return []

    def get_upscale_method_names(self) -> list[str]:
        """Return the list of available upscale methods."""
        assert self._webservice is not None
        try:
            upscaler_info = self._webservice.get_upscalers()
            return [upscaler['name'] for upscaler in upscaler_info]
        except (RuntimeError, KeyError) as err:
            logger.error(f'Loading stable-diffusion LoRA model list failed: {err}')
            return []

    def cache_generator_specific_data(self) -> None:
        """When activating the generator, after the webservice is connected, this method should be implemented to
           load and cache any generator-specific API data."""
        assert self._webservice is not None
        cache = Cache()
        try:
            # Synchronize local config options with remote WebUI settings:
            for cross_config_key in (Cache.SD_MODEL, Cache.CLIP_SKIP):
                try:
                    cache.disconnect(self, cross_config_key)
                except KeyError:
                    pass  # No previous connection to remove, which isn't a problem here.

            webui_config = A1111Config()
            webui_config.load_all(self._webservice)
            current_model_title = webui_config.get(A1111Config.SD_MODEL_CHECKPOINT)
            model_options = self._webservice.get_models()
            for model in model_options:
                if model['title'] == current_model_title:
                    cache.set(Cache.SD_MODEL, model['model_name'])
                    break

            def _update_remote_model_selection(model_name: str) -> None:
                if not self._connected:
                    return
                for model_option in model_options:
                    if model_option['model_name'] == model_name:
                        if model_option['title'] != webui_config.get(A1111Config.SD_MODEL_CHECKPOINT):
                            remote_setting_change = {A1111Config.SD_MODEL_CHECKPOINT: model_option['title']}
                            self.update_settings(remote_setting_change)
                        return
                raise RuntimeError(f'Selected model "{model_name}" not found in available options.')
            cache.connect(self, Cache.SD_MODEL, _update_remote_model_selection)

            def _update_local_model_selection(selected_model_title: str) -> None:
                if not self._connected:
                    return
                for model_option in model_options:
                    if model_option['title'] == selected_model_title:
                        cache.set(Cache.SD_MODEL, model_option['model_name'])
                        return
                raise RuntimeError(f'Selected model "{selected_model_title}" not found in available options.')
            _update_local_model_selection(current_model_title)
            webui_config.connect(self, A1111Config.SD_MODEL_CHECKPOINT, _update_local_model_selection)

            clip_skip = webui_config.get(A1111Config.CLIP_STOP_AT_LAST_LAYERS)
            cache.set(Cache.CLIP_SKIP, clip_skip)

            def _update_remote_clip_skip(step: int) -> None:
                if not self._connected or step == webui_config.get(A1111Config.CLIP_STOP_AT_LAST_LAYERS):
                    return
                remote_settings_change = {A1111Config.CLIP_STOP_AT_LAST_LAYERS: step}
                self.update_settings(remote_settings_change)
            cache.connect(self, Cache.CLIP_SKIP, _update_remote_clip_skip)

            def _update_local_clip_skip(step: int) -> None:
                if not self._connected:
                    return
                cache.set(Cache.CLIP_SKIP, step)
            webui_config.connect(self, A1111Config.CLIP_STOP_AT_LAST_LAYERS, _update_local_clip_skip)

        except (RuntimeError, KeyError) as err:
            logger.error(f'Loading WebUI model connection failed: {err}')
        try:
            scripts = self._webservice.get_scripts()
            if 'txt2img' in scripts:
                cache.set(Cache.SCRIPTS_TXT2IMG, scripts['txt2img'])
            if 'img2img' in scripts:
                cache.set(Cache.SCRIPTS_IMG2IMG, scripts['img2img'])
        except (KeyError, RuntimeError) as err:
            logger.error(f'error loading scripts from {self._server_url}: {err}')
        try:
            styles = self._webservice.get_styles()
            cache.set(Cache.STYLES, styles)
        except (KeyError, RuntimeError) as err:
            logger.error(f'error loading prompt styles from {self._server_url}: {err}')

    def clear_cached_generator_data(self) -> None:
        """Clear any cached data specific to this image generator."""
        cache = Cache()
        for list_key in (Cache.SCRIPTS_TXT2IMG, Cache.SCRIPTS_IMG2IMG, Cache.STYLES):
            cache.set(list_key, [])

    def load_lora_thumbnail(self, lora_info: Optional[dict[str, str]]) -> Optional[QImage]:
        """Attempt to load a LoRA model thumbnail image from the API."""
        if lora_info is None:
            return None
        try:
            assert self._webservice is not None
            path = lora_info['path']
            path = path[:path.rindex('.')] + '.png'
            return self._webservice.get_thumbnail(path)
        except (KeyError, RuntimeError) as err:
            logger.error(f'error loading LoRA thumbnail from {self._server_url}: {err}')
            return None

    def load_preprocessor_preview(self, preprocessor: ControlNetPreprocessor,
                                  image: QImage, mask: Optional[QImage],
                                  status_signal: Signal,
                                  image_signal: Signal) -> None:
        """Requests a ControlNet preprocessor preview image."""
        assert self._webservice is not None
        preview_image = self._webservice.controlnet_preprocessor_preview(image, mask, preprocessor)
        image_signal.emit(preview_image)

    def is_available(self) -> bool:
        """Returns whether the generator is supported on the current system."""
        if self._webservice is None:
            self._webservice = A1111Webservice(self._server_url)
        try:
            # Login automatically if username/password are defined as env variables.
            if 'SD_UNAME' in os.environ and 'SD_PASS' in os.environ:
                self._webservice.login(os.environ['SD_UNAME'], os.environ['SD_PASS'])
                self._webservice.set_auth((os.environ['SD_UNAME'], os.environ['SD_PASS']))
            health_check_res = self._webservice.login_check()
            if health_check_res.ok or (health_check_res.status_code == 401
                                       and health_check_res.json()[AUTH_ERROR_DETAIL_KEY] == AUTH_ERROR_MESSAGE):
                return True
        except RuntimeError as req_err:
            logger.error(f'Login check connection failed: {req_err}')
        except AuthError:
            self.status_signal.emit(AUTH_ERROR)
        return False

    def init_settings(self, settings_modal: SettingsModal) -> None:
        """Updates a settings modal to add settings relevant to this generator."""
        assert self._webservice is not None
        web_config = A1111Config()
        try:
            web_config.load_all(self._webservice)
            settings_modal.load_from_config(web_config)
        except (KeyError, RuntimeError) as err:
            logger.error(f'Failed to init WebUI API settings: {err}')
            show_error_dialog(None, ERROR_TITLE_SETTINGS_LOAD_FAILED, ERROR_MESSAGE_SETTINGS_LOAD_FAILED)
        app_config = AppConfig()
        settings_modal.load_from_config(app_config, [STABLE_DIFFUSION_CONFIG_CATEGORY])

    def refresh_settings(self, settings_modal: SettingsModal) -> None:
        """Reloads current values for this generator's settings, and updates them in the settings modal."""
        assert self._webservice is not None
        try:
            settings = self._webservice.get_config()
        except (KeyError, RuntimeError) as err:
            logger.error(f'Failed to init WebUI API settings: {err}')
            show_error_dialog(None, ERROR_TITLE_SETTINGS_LOAD_FAILED, ERROR_MESSAGE_SETTINGS_LOAD_FAILED)
            settings = {}
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

            class _SettingsUpdateTask(AsyncTask):
                error_signal = Signal(Exception)

                def signals(self) -> list[Signal]:
                    return [self.error_signal]

            def _update_config(error_signal: Signal) -> None:
                assert self._webservice is not None
                try:
                    self._webservice.set_config(changed_settings)
                except (KeyError, RuntimeError) as err:
                    error_signal.emit(err)

            update_task = _SettingsUpdateTask(_update_config, True)

            def _update_setting() -> None:
                AppStateTracker.set_app_state(APP_STATE_EDITING if self._image_stack.has_image else APP_STATE_NO_IMAGE)
                update_task.finish_signal.disconnect(_update_setting)

            def _handle_error(err: Exception) -> None:
                logger.error(f'Error updating settings: {err}')
                show_error_dialog(None, ERROR_TITLE_SETTINGS_SAVE_FAILED, ERROR_MESSAGE_SETTINGS_SAVE_FAILED)

            update_task.finish_signal.connect(_update_setting)
            update_task.error_signal.connect(_handle_error)
            update_task.start()

    def unload_settings(self, settings_modal: SettingsModal) -> None:
        """Unloads this generator's settings from the settings modal."""
        settings_modal.remove_category(AppConfig(), STABLE_DIFFUSION_CONFIG_CATEGORY)
        a1111_config = A1111Config()
        for category in a1111_config.get_categories():
            settings_modal.remove_category(a1111_config, category)

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

            def signals(self) -> list[Signal]:
                return [self.prompt_ready, self.error_signal]

        def _interrogate(prompt_ready: Signal, error_signal: Signal) -> None:
            try:
                assert self._webservice is not None
                prompt_ready.emit(self._webservice.interrogate(image))
            except ReadTimeout:
                raise RuntimeError(ERROR_MESSAGE_TIMEOUT)
            except (RuntimeError, AssertionError) as err:
                logger.error(f'err:{err}')
                error_signal.emit(err)

        task = _InterrogateTask(_interrogate, True)

        def set_prompt(prompt_text: str) -> None:
            """Update the image prompt in config with the interrogate results."""
            last_prompt = Cache().get(Cache.PROMPT)

            def _update_prompt(text=prompt_text) -> None:
                Cache().set(Cache.PROMPT, text)

            def _restore_prompt(text=last_prompt) -> None:
                Cache().set(Cache.PROMPT, text)

            UndoStack().commit_action(_update_prompt, _restore_prompt, 'SDWebUIGenerator._interrogate')
            AppStateTracker().set_app_state(APP_STATE_EDITING)

        task.prompt_ready.connect(set_prompt)

        def handle_error(err: BaseException) -> None:
            """Show an error popup if interrogate fails."""
            assert self._window is not None
            AppStateTracker().set_app_state(APP_STATE_EDITING)
            show_error_dialog(self._window, INTERROGATE_ERROR_TITLE, err)

        task.error_signal.connect(handle_error)
        task.start()

    def get_control_panel(self) -> Optional[GeneratorPanel]:
        """Returns a widget with inputs for controlling this generator."""
        if self._control_panel is None:
            self._control_panel = StableDiffusionPanel(True, True)
            self._control_panel.hide()
            self._control_panel.generate_signal.connect(self.start_and_manage_image_generation)
            self._control_panel.interrogate_signal.connect(self.interrogate)
            self._control_panel.add_extras_tab(self._gen_extras_tab)
        return self._control_panel

    def _async_progress_check(self, external_status_signal: Optional[Signal] = None):
        webservice = self._webservice
        assert webservice is not None
        self._active_task_id += 1
        generator = self

        class _ProgressTask(AsyncTask):
            status_signal = Signal(dict)

            def __init__(self, task_id: int) -> None:
                super().__init__(self._check_progress)
                self._id = task_id
                self.should_stop = False

            def signals(self) -> list[Signal]:
                return [external_status_signal if external_status_signal is not None else self.status_signal]

            def _check_progress(self, status_signal) -> None:
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
                        progress_percent = int(status['progress'] * 100)
                        if (progress_percent < max_progress or progress_percent >= 100
                                or generator._active_task_id != self._id):
                            break
                        if progress_percent <= 1:
                            continue
                        status_text = f'{progress_percent}%'
                        max_progress = progress_percent
                        if 'eta_relative' in status and status['eta_relative'] != 0 \
                                and 0 < progress_percent < 100:
                            eta_sec = status['eta_relative']
                            minutes = eta_sec // 60
                            seconds = round(eta_sec % 60)
                            if minutes > 0:
                                status_text = f'{status_text} ETA: {minutes}:{seconds}'
                            else:
                                status_text = f'{status_text} ETA: {seconds}s'
                        status_signal.emit({'progress': status_text})
                    except ReadTimeout:
                        error_count += 1
                    except RuntimeError as err:
                        error_count += 1
                        logger.error(f'Error {error_count}: {err}')
                        if error_count > MAX_ERROR_COUNT:
                            logger.error('Inpainting failed, reached max retries.')
                            break
                        continue

        task = _ProgressTask(self._active_task_id)
        assert self._window is not None
        if external_status_signal is None:
            task.status_signal.connect(self._apply_status_update)

            def _finish():
                task.status_signal.disconnect(self._apply_status_update)
                task.finish_signal.disconnect(_finish)

            task.finish_signal.connect(_finish)
        task.start()

    def cancel_generation(self) -> None:
        """Cancels image generation, if in-progress"""
        assert self._webservice is not None
        if AppStateTracker.app_state() == APP_STATE_LOADING:
            self._webservice.interrupt()

    def generate(self,
                 status_signal: Signal,
                 source_image: Optional[QImage] = None,
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
        edit_mode = Cache().get(Cache.EDIT_MODE)
        if edit_mode == EDIT_MODE_INPAINT and self._image_stack.selection_layer.generation_area_fully_selected():
            edit_mode = EDIT_MODE_IMG2IMG
        if edit_mode != EDIT_MODE_INPAINT:
            mask_image = None
        elif self._image_stack.selection_layer.generation_area_is_empty():
            raise RuntimeError(GENERATE_ERROR_MESSAGE_EMPTY_MASK)

            # Check progress before starting:
        assert self._webservice is not None
        try:
            init_data = self._webservice.progress_check()
            if init_data['current_image'] is not None:
                raise RuntimeError(ERROR_MESSAGE_EXISTING_OPERATION)
            self._async_progress_check(status_signal)
            if edit_mode == EDIT_MODE_TXT2IMG:
                image_response = self._webservice.txt2img(control_image=source_image)
            else:
                assert source_image is not None
                image_response = self._webservice.img2img(source_image, mask=mask_image)
            image_data = image_response['images']
            info = image_response['info']
            for i, response_image in enumerate(image_data):
                self._cache_generated_image(response_image, i)
            if info is not None:
                # logger.info(f'Image generation result info: {json.dumps(info, indent=2)}')
                if isinstance(info, dict):
                    status = {}
                    if 'seed' in info:
                        status['seed'] = str(info['seed'])
                    if 'subseed' in info:
                        status['subseed'] = str(info['subseed'])
                    status_signal.emit(status)
        except ReadTimeout:
            raise RuntimeError(ERROR_MESSAGE_TIMEOUT)
        except (RuntimeError, ConnectionError) as image_gen_error:
            logger.error(f'request failed: {image_gen_error}')
            raise RuntimeError(f'request failed: {image_gen_error}') from image_gen_error
        except Exception as unexpected_err:
            logger.error('Unexpected error:', unexpected_err)
            raise RuntimeError(f'unexpected error: {unexpected_err}') from unexpected_err

    def upscale_image(self, image: QImage, new_size: QSize, status_signal: Signal, image_signal: Signal) -> None:
        """Upscales an image using cached upscaling settings."""
        assert self._webservice is not None
        image_response = self._webservice.upscale(self._image_stack.qimage(), new_size.width(),
                                                  new_size.height())
        images = image_response['images']
        info = image_response['info']
        if info is not None:
            logger.debug(f'Upscaling result info: {info}')
        image_signal.emit(images[-1])

    @menu_action(MENU_STABLE_DIFFUSION, 'prompt_style_shortcut', 200, [APP_STATE_EDITING],
                 condition_check=_check_prompt_styles_available)
    def show_style_window(self) -> None:
        """Show the saved prompt style window."""
        style_window = PromptStyleWindow()
        # TODO: update after the prompt style endpoint gets POST support
        # style_window.should_save_changes.connect(self._update_styles)
        style_window.exec()
