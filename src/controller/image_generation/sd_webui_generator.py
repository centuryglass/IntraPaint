"""Generates images through the Stable Diffusion WebUI (A1111 or Forge), using the `sd_backend_client` library's WebUI
client."""
import logging
import os
from argparse import Namespace
from typing import Optional, Any, cast

from PySide6.QtCore import Signal, QSize, SignalInstance, QRect
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from sd_backend_client import A1111Webservice, AuthError, BackendTimeoutError, ControlNetPreprocessor, ControlTypeDef, \
    SDBackendError
from sd_backend_client.api.webui.response_formats import GenerationInfoData

from src.api.controlnet.controlnet_unit import ControlKeyType
from src.config.a1111_config import A1111Config
from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_generation.sd_adapters.credentials_adapter import create_webservice, login_without_prompt
from src.controller.image_generation.sd_adapters.image_adapter import pil_to_qimage, qimage_to_pil
from src.controller.image_generation.sd_adapters.params_adapter import build_webui_body, build_upscale_params
from src.controller.image_generation.sd_generator import SD_BASE_DESCRIPTION, STABLE_DIFFUSION_CONFIG_CATEGORY, \
    SDGenerator, INSTALLATION_STABILITY_MATRIX, GETTING_SD_MODELS, IMAGE_PREVIEW_STABILITY_MATRIX_PACKAGES, \
    MENU_STABLE_DIFFUSION
from src.image.layers.image_stack import ImageStack
from src.ui.modal.modal_utils import show_error_dialog
from src.ui.modal.settings_modal import SettingsModal
from src.ui.panel.generators.generator_panel import GeneratorPanel
from src.ui.panel.generators.stable_diffusion_panel import StableDiffusionPanel
from src.ui.panel.generators.webui_extras_tab import WebUIExtrasTab
from src.ui.window.main_window import MainWindow
from src.ui.window.prompt_style_window import PromptStyleWindow
from src.undo_stack import UndoStack
from src.util.application_state import AppStateTracker, APP_STATE_EDITING, APP_STATE_NO_IMAGE
from src.util.async_task import AsyncTask
from src.util.menu_builder import menu_action
from src.util.shared_constants import EDIT_MODE_TXT2IMG, EDIT_MODE_INPAINT, EDIT_MODE_IMG2IMG, PROJECT_DIR, \
    AUTH_ERROR, AUTH_ERROR_MESSAGE, INTERROGATE_ERROR_TITLE, INTERROGATE_ERROR_MESSAGE_NO_IMAGE, \
    ERROR_MESSAGE_TIMEOUT, GENERATE_ERROR_MESSAGE_EMPTY_MASK, GENERATE_ERROR_TITLE, MISC_CONNECTION_ERROR

logger = logging.getLogger(__name__)

# The QCoreApplication.translate context for strings in this file
TR_ID = 'controller.image_generation.sd_webui_generator'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


SD_WEBUI_GENERATOR_NAME = _tr('Stable Diffusion WebUI API')
SD_WEBUI_GENERATOR_DESCRIPTION_HEADER = _tr('<h2>Stable Diffusion: via WebUI API</h2>')
SD_WEBUI_GENERATOR_DESCRIPTION_WEBUI = _tr("""
<h3>About the Stable Diffusion WebUI</h3>
<p>
    The <a href="https://github.com/AUTOMATIC1111/stable-diffusion-webui?tab=readme-ov-file#stable-diffusion-web-ui">
    Stable Diffusion WebUI</a> is one of the first interfaces created for using Stable Diffusion. When the WebUI is
    running and configured correctly, IntraPaint can access Stable Diffusion image generation by sending requests to
    the WebUI. You can run the WebUI on the same computer as IntraPaint, or remotely on a separate server.
</p>
<p>
    When connected, IntraPaint provides controls for the WebUI in the <b>Image Generation</b> tab and in the <b>settings
    window</b> under the Stable Diffusion category. When running, you can also access the WebUI's own interface
    directly through your web browser at <a href="http://localhost:7860/">localhost:7860</a>.
</p>
<h3>About Stable Diffusion WebUI Forge</h3>
<p>
    <a href="https://github.com/lllyasviel/stable-diffusion-webui-forge?tab=readme-ov-file#stable-diffusion-webui-forge">
    Stable Diffusion WebUI Forge</a> is a popular variant of the original Stable Diffusion WebUI, that adds significant
    improvements to image generation speed and efficiency. It also adds a large number of experimental features that 
    cause compatibility issues. IntraPaint provides some support for WebUI Forge, but ControlNet will not work with
    recent versions.
</p>
<h3>About Stable Diffusion WebUI reForge</h3>
<p>
    <a href="https://github.com/Panchovix/stable-diffusion-webui-reForge?tab=readme-ov-file#stable-diffusion-webui-forgereforge">
    Stable Diffusion WebUI re Forge</a> is a third version of the WebUI that includes the improved performance of
    WebUI Forge without any of the compatibility issues. <b>This is the recommended version to use with IntraPaint</b>.
</p>
""")

SD_WEBUI_GENERATOR_DESCRIPTION = (f'{SD_WEBUI_GENERATOR_DESCRIPTION_HEADER}\n{SD_BASE_DESCRIPTION}'
                                  f'\n{SD_WEBUI_GENERATOR_DESCRIPTION_WEBUI}')

# noinspection SpellCheckingInspection
SD_WEBUI_GENERATOR_SETUP_OPTIONS = _tr("""
<h1>Stable Diffusion WebUI Generator Setup</h1>
<p>
    To use the Stable Diffusion WebUI generator, you will to download at least one Stable Diffusion model file, 
    install the WebUI, enable API access, and start the WebUI.  This guide will explain each of those steps.
</p>""" + GETTING_SD_MODELS + """
<hr/>
<h2>Installing Stable Diffusion WebUI: Available options</h2>
<p>
    There are a few different ways you can install the WebUI. The recommended method is to use
    <a href="https://github.com/LykosAI/StabilityMatrix?tab=readme-ov-file#stability-matrix">Stability Matrix</a>,
    but other methods are covered here for the sake of completeness.
</p>
<hr/>
<h2>Option 1: Stability Matrix</h2>
<p>
    Installation through Stability Matrix is the recommended method. This method is the simplest option, provides a lot
    of helpful extra resources, and supports Windows, macOS and Linux.  This method also lets you switch between the
    original WebUI and the Forge version easily, or even install ComfyUI if you want to try IntraPaint's
    Stable Diffusion ComfyUI image generator.
</p>""")

IMAGE_PREVIEW_STABILITY_MATRIX_SETTINGS = f'{PROJECT_DIR}/resources/help_docs/stability_matrix_settings_button.png'
SD_WEBUI_GENERATOR_STABILITY_MATRIX_CONFIG = _tr("""
    <li>
        On the <img src='""" + IMAGE_PREVIEW_STABILITY_MATRIX_PACKAGES + """'/><b>Packages</b> tab, click the
        <img src='""" + IMAGE_PREVIEW_STABILITY_MATRIX_SETTINGS + """'/><b>Settings</b> button next to the WebUI
        package to open the launch options.  Scroll to the bottom of the list, and find the <b>"Extra Launch Arguments"
        </b> text field. Enter <b>--api</b> into that text field, and click the <b>"Save"</b> button.  This step is
         needed to make the WebUI accept image generation requests from IntraPaint.
        <br/>
    </li>
""")

SD_WEBUI_GENERATOR_STABILITY_MATRIX_PACKAGE = 'Stable Diffusion WebUI reForge'

SD_WEBUI_GENERATOR_SETUP_STABILITY_MATRIX = INSTALLATION_STABILITY_MATRIX.format(
    generator_package=SD_WEBUI_GENERATOR_STABILITY_MATRIX_PACKAGE,
    post_install_generator_setup=SD_WEBUI_GENERATOR_STABILITY_MATRIX_CONFIG
)

SD_WEBUI_GENERATOR_SETUP_ALTERNATIVES = _tr("""
<hr/>
<h2>Option 2: WebUI Forge one-click installer</h2>
<p>
    Stable Diffusion WebUI Forge provides a <a href="https://github.com/lllyasviel/stable-diffusion-webui-forge/releases/download/previous/webui_forge_cu121_torch21_f0017.7z">
    one-click Windows installation package</a> you can use to easily install the WebUI. This won't work outside of
    Windows and requires a bit more file management, but it's still a good option if you don't need the extra features
    in Stability Matrix.
</p>
<ol>
    <li>
        Download the last stable package version <a href="https://github.com/lllyasviel/stable-diffusion-webui-forge/releases/download/previous/webui_forge_cu121_torch21_f0017.7z">
        here</a>. There are several other options linked on the
        <a href="https://github.com/lllyasviel/stable-diffusion-webui-forge?tab=readme-ov-file#installing-forge">
        WebUI Forge README</a> you can try, but newer versions may cause compatibility issues.<br/>
    </li>
    <li>
        Extract the downloaded package into a new folder. If you're not using Windows 11, you may need to install
        <a href="https://www.7-zip.org">7-Zip</a> to extract the compressed files.<br/>
    </li>
    <li>
        Within the new WebUI-Forge folder, open the <b>webui\\webui-user.bat</b> file in a text editor. Find the 
        "<b>set COMMANDLINE_ARGS=</b>" line near the top of the file, and change it to 
        "<b>set COMMANDLINE_ARGS=--api</b>".  Save and close the file. This step is needed to make the WebUI accept
        image generation requests from IntraPaint.<br/>
    </li>
    <li>
        If you haven't already found at least one Stable Diffusion model file, do that now. Copy it into the 
        WebUI-Forge folder under <b>webui\\models\\Stable-diffusion</b>.<br/>
    </li>
    <li>
        Launch the <b>run.bat</b> file in the WebUI-Forge folder to start Stable Diffusion.  A terminal window will
        open and print startup information as the WebUI initializes.<br/>
    </li>
    <li>
        Once you see <b>"Running on local URL:  http://0.0.0.0:7860"</b> in the terminal window, Stable Diffusion is
        ready to use.  Back in IntraPaint, click the "Activate" button below to connect to Stable Diffusion. <br/>
    </li>
    <li>
        In the future, the only step you'll need to repeat from this list is launching <b>run.bat</b> and waiting
        for it to finish starting up. If you do this before launching IntraPaint, it will automatically connect to
        the WebUI-Forge image generator on startup.
    </li>
</ol>
<hr/>
<h3>Option 3: Running directly in Python</h3>
<p>
    This method requires a lot more technical knowledge than the previous ones, but it also provides the most
    flexibility and requires the least amount of storage space.  This is only recommended if you've set up a Python
    virtual environment and debugged Python dependency issues before, or if you're interested in teaching yourself to
    do so.
</p>
<p>
    Because this option isn't recommended, IntraPaint won't provide a full guide. The
    <a href="https://github.com/AUTOMATIC1111/stable-diffusion-webui?tab=readme-ov-file#automatic-installation-on-windows">
    Stable Diffusion WebUI installation instructions</a> should help you get started. If you run into any problems,
    searching the <a href="https://github.com/AUTOMATIC1111/stable-diffusion-webui/issues">WebUI issues page</a> will 
    probably help you find a solution.
</p>
""")

SD_WEBUI_GENERATOR_SETUP = SD_WEBUI_GENERATOR_SETUP_OPTIONS + SD_WEBUI_GENERATOR_SETUP_STABILITY_MATRIX \
                           + SD_WEBUI_GENERATOR_SETUP_ALTERNATIVES

SD_PREVIEW_IMAGE = f'{PROJECT_DIR}/resources/generator_preview/stable-diffusion.png'
ICON_PATH_CONTROLNET_TAB = f'{PROJECT_DIR}/resources/icons/tabs/hex.svg'
DEFAULT_WEBUI_URL = 'http://localhost:7860'
AUTH_ERROR_DETAIL_KEY = 'detail'
STYLE_ERROR_TITLE = _tr('Updating prompt styles failed')

ERROR_TITLE_SETTINGS_LOAD_FAILED = _tr('Failed to load Stable Diffusion settings')
ERROR_TITLE_SETTINGS_SAVE_FAILED = _tr('Failed to save Stable Diffusion settings')
ERROR_MESSAGE_SETTINGS_LOAD_FAILED = _tr('The connection to the Stable Diffusion WebUI image generator was lost. '
                                         'Connected generator settings will not be available.')
ERROR_MESSAGE_SETTINGS_SAVE_FAILED = _tr('The connection to the Stable Diffusion WebUI image generator was lost. '
                                         'Any changes to connected generator settings were not saved.')


def _check_prompt_styles_available(_) -> bool:
    cache = Cache()
    return len(cache.get(Cache.STYLES)) > 0


def _check_lora_available(_) -> bool:
    cache = Cache()
    return len(cache.get(Cache.LORA_MODELS)) > 0


class SDWebUIGenerator(SDGenerator):
    """Interface for providing image generation capabilities."""

    def __init__(self, window: MainWindow, image_stack: ImageStack, args: Namespace) -> None:
        super().__init__(window, image_stack, args, Cache.SD_WEBUI_SERVER_URL, ControlKeyType.WEBUI, True)
        self._webservice: Optional[A1111Webservice] = create_webservice(self.server_url)
        self._gen_extras_tab = WebUIExtrasTab()

    def get_display_name(self) -> str:
        """Returns a display name identifying the generator."""
        return SD_WEBUI_GENERATOR_NAME

    def get_setup_text(self) -> str:
        """Returns a rich text description of how to set up this generator."""
        return SD_WEBUI_GENERATOR_SETUP

    def get_description(self) -> str:
        """Returns an extended description of this generator."""
        return SD_WEBUI_GENERATOR_DESCRIPTION

    def get_webservice(self) -> Optional[A1111Webservice]:
        """Return the webservice object this module uses to connect to Stable Diffusion, if initialized."""
        return self._webservice

    def remove_webservice(self) -> None:
        """Destroy and remove any active webservice object."""
        self._webservice = None

    def create_or_get_webservice(self, url: str) -> A1111Webservice:
        """Return the webservice object this module uses to connect to Stable Diffusion.  If the webservice already
           exists but the url doesn't match, a new webservice should replace the existing one, using the new url."""
        if self._webservice is not None:
            if self._webservice.server_url == url.rstrip('/'):
                return self._webservice
            self._webservice.disconnect()
            self._webservice = None
        self._webservice = create_webservice(url)
        return self._webservice

    def get_controlnet_preprocessors(self) -> list[ControlNetPreprocessor]:
        """Return the list of available Controlnet preprocessors."""
        assert self._webservice is not None
        try:
            return list(self._webservice.get_controlnet_preprocessors())
        except SDBackendError as err:
            logger.error(f'Loading ControlNet preprocessors failed: {err}')
            return []

    def get_controlnet_models(self) -> list[str]:
        """Return the list of available ControlNet models."""
        assert self._webservice is not None
        try:
            return self._webservice.get_controlnet_models().model_list
        except SDBackendError as err:
            logger.error(f'Loading ControlNet models failed: {err}')
            return []

    def get_controlnet_types(self) -> dict[str, ControlTypeDef]:
        """Return available ControlNet categories."""
        assert self._webservice is not None
        try:
            return cast(dict[str, ControlTypeDef], self._webservice.get_controlnet_type_categories())
        except SDBackendError as err:
            logger.error(f'Loading ControlNet types failed: {err}')
            return {}

    def get_controlnet_unit_cache_keys(self) -> list[str]:
        """Return keys used to cache serialized ControlNet units as strings."""
        return [Cache.CONTROLNET_ARGS_0_WEBUI, Cache.CONTROLNET_ARGS_1_WEBUI, Cache.CONTROLNET_ARGS_2_WEBUI]

    def get_diffusion_model_names(self) -> list[str]:
        """Return the list of available image generation models."""
        assert self._webservice is not None
        try:
            return [model.model_name for model in self._webservice.get_models()]
        except SDBackendError as err:
            logger.error(f'Loading Stable Diffusion model list failed: {err}')
            return []

    def get_lora_model_info(self) -> list[dict[str, str]]:
        """Return available LoRA model extensions."""
        assert self._webservice is not None
        try:
            return [cast(dict[str, str], lora.model_dump()) for lora in self._webservice.get_loras()]
        except SDBackendError as err:
            logger.error(f'Loading Stable Diffusion LoRA model list failed: {err}')
            return []

    def get_diffusion_sampler_names(self) -> list[str]:
        """Return the list of available samplers."""
        assert self._webservice is not None
        try:
            return [sampler.name for sampler in self._webservice.get_samplers()]
        except SDBackendError as err:
            logger.error(f'Loading Stable Diffusion sampler option list failed: {err}')
            return []

    def get_upscale_method_names(self) -> list[str]:
        """Return the list of available upscale methods."""
        assert self._webservice is not None
        try:
            return [upscaler.name for upscaler in self._webservice.get_upscalers()]
        except SDBackendError as err:
            logger.error(f'Loading Stable Diffusion upscaler list failed: {err}')
            return []

    def ultimate_upscale_script_available(self) -> bool:
        """Return whether the Stable Diffusion API will support the 'Ultimate SD Upscale' script."""
        assert self._webservice is not None
        try:
            return self._webservice.get_capabilities().ultimate_upscale
        except SDBackendError as err:
            logger.error(f'Checking for Ultimate SD Upscale support failed: {err}')
            return False

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
                if model.title == current_model_title:
                    cache.set(Cache.SD_MODEL, model.model_name)
                    break

            def _update_remote_model_selection(model_name: str) -> None:
                if not self._connected:
                    return
                assert self._webservice is not None
                webui_config.load_all(self._webservice)
                for model_option in model_options:
                    if model_option.model_name == model_name:
                        if model_option.title != webui_config.get(A1111Config.SD_MODEL_CHECKPOINT):
                            remote_setting_change = {A1111Config.SD_MODEL_CHECKPOINT: model_option.title}
                            self.update_settings(remote_setting_change)
                            assert self._webservice is not None
                            webui_config.load_all(self._webservice)
                        return
                raise RuntimeError(f'Selected model "{model_name}" not found in available options.')

            cache.connect(self, Cache.SD_MODEL, _update_remote_model_selection)

            def _update_local_model_selection(selected_model_title: str) -> None:
                if not self._connected:
                    return
                for model_option in model_options:
                    if model_option.title == selected_model_title:
                        cache.set(Cache.SD_MODEL, model_option.model_name)
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

        except (RuntimeError, KeyError, SDBackendError) as err:
            logger.error(f'Loading WebUI model connection failed: {err}')
        try:
            scripts = self._webservice.get_scripts()
            cache.set(Cache.SCRIPTS_TXT2IMG, scripts.txt2img)
            cache.set(Cache.SCRIPTS_IMG2IMG, scripts.img2img)
        except SDBackendError as err:
            logger.error(f'error loading scripts from {self._server_url}: {err}')
        try:
            styles = self._webservice.get_styles()
            cache.set(Cache.STYLES, [style.model_dump_json() for style in styles])
        except SDBackendError as err:
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
            thumbnail = self._webservice.get_thumbnail(path)
            return None if thumbnail is None else pil_to_qimage(thumbnail)
        except (KeyError, SDBackendError) as err:
            logger.error(f'error loading LoRA thumbnail from {self._server_url}: {err}')
            return None

    def is_available(self) -> bool:
        """Returns whether the generator is supported on the current system."""
        if self._webservice is None:
            self._webservice = create_webservice(self._server_url)
        try:
            # Login automatically if username/password are defined as env variables.
            if 'SD_UNAME' in os.environ and 'SD_PASS' in os.environ:
                login_without_prompt(self._webservice, os.environ['SD_UNAME'], os.environ['SD_PASS'])
                self._webservice.set_auth((os.environ['SD_UNAME'], os.environ['SD_PASS']))
            health_check_res = self._webservice.login_check()
            if health_check_res.ok or (health_check_res.status_code == 401
                                       and health_check_res.json()[AUTH_ERROR_DETAIL_KEY] == AUTH_ERROR_MESSAGE):
                return True
        except AuthError:
            self.status_signal.emit(AUTH_ERROR.format(url=self.server_url))
        except SDBackendError as req_err:
            self.status_signal.emit(MISC_CONNECTION_ERROR.format(url=self._server_url, error_text=str(req_err)))
            logger.error(f'Login check connection failed: {req_err}')
        return False

    def init_settings(self, settings_modal: SettingsModal) -> None:
        """Updates a settings modal to add settings relevant to this generator."""
        assert self._webservice is not None
        web_config = A1111Config()
        try:
            web_config.load_all(self._webservice)
            settings_modal.load_from_config(web_config)
        except (KeyError, SDBackendError) as err:
            logger.error(f'Failed to init WebUI API settings: {err}')
            show_error_dialog(None, ERROR_TITLE_SETTINGS_LOAD_FAILED, ERROR_MESSAGE_SETTINGS_LOAD_FAILED)
        app_config = AppConfig()
        settings_modal.load_from_config(app_config, [STABLE_DIFFUSION_CONFIG_CATEGORY])

    def refresh_settings(self, settings_modal: SettingsModal) -> None:
        """Reloads current values for this generator's settings, and updates them in the settings modal."""
        assert self._webservice is not None
        try:
            settings = self._webservice.get_config()
        except (KeyError, SDBackendError) as err:
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
        web_changes: dict[str, Any] = {}
        for key, value in changed_settings.items():
            if key in web_keys:
                web_changes[key] = value
            elif key in app_keys and not isinstance(value, (list, dict)):
                AppConfig().set(key, value)
        if len(web_changes) > 0:

            class _SettingsUpdateTask(AsyncTask):
                error_signal = Signal(Exception)

                def signals(self) -> list[SignalInstance]:
                    return [self.error_signal]

            def _update_config(error_signal: SignalInstance) -> None:
                assert self._webservice is not None
                try:
                    self._webservice.set_config(changed_settings)
                except (KeyError, SDBackendError) as err:
                    error_signal.emit(err)

            update_task = _SettingsUpdateTask(_update_config, True)

            def _update_setting() -> None:
                AppStateTracker.set_app_state(APP_STATE_EDITING if self._image_stack.has_image else APP_STATE_NO_IMAGE)
                for key, changed_value in web_changes.items():
                    web_config.set(key, changed_value)
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

        Sends the image generation area content to the Stable Diffusion WebUI API, where an image captioning model
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

            def signals(self) -> list[SignalInstance]:
                return [self.prompt_ready, self.error_signal]

        def _interrogate(prompt_ready: SignalInstance, error_signal: SignalInstance) -> None:
            try:
                assert self._webservice is not None
                prompt_ready.emit(self._webservice.interrogate(qimage_to_pil(image)))
            except BackendTimeoutError as err:
                raise RuntimeError(ERROR_MESSAGE_TIMEOUT) from err
            except (SDBackendError, RuntimeError, AssertionError) as err:
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

    def generate(self,
                 status_signal: SignalInstance,
                 source_image: Optional[QImage] = None,
                 mask_image: Optional[QImage] = None) -> None:
        """Generates new images. Image size, image count, prompts, etc. are loaded from AppConfig as needed.

        Parameters
        ----------
        status_signal : SignalInstance[str]
            Signal to emit when status updates are available.
        source_image : QImage
            Image to potentially use as a basis for the created or edited image.  This will be ignored if the editing
            mode is text-to-image and there are no ControlNet units using the image generation area.
        mask_image : QImage, optional
            Mask marking the edited image region.
        """
        webservice = self._webservice
        assert webservice is not None
        edit_mode = Cache().get(Cache.EDIT_MODE)
        if edit_mode == EDIT_MODE_INPAINT and self._image_stack.selection_layer.generation_area_fully_selected():
            edit_mode = EDIT_MODE_IMG2IMG
        if edit_mode != EDIT_MODE_INPAINT:
            mask_image = None
        elif self._image_stack.selection_layer.generation_area_is_empty():
            raise RuntimeError(GENERATE_ERROR_MESSAGE_EMPTY_MASK)

        # The WebUI computes its own inpaint full-res crop from the mask alone, so it can't see context pins. When pins
        # change the crop, crop on the client and send the crop with inpaint_full_res off.
        original_source_image: Optional[QImage] = None
        crop_bounds: Optional[QRect] = None
        if edit_mode == EDIT_MODE_INPAINT and source_image is not None and mask_image is not None \
                and self._context_pins_change_inpaint_crop():
            crop_bounds = self._inpaint_gen_area_crop_bounds()
            original_source_image = source_image
            source_image = self._scale_and_crop_gen_qimage(source_image)
            mask_image = self._scale_and_crop_gen_qimage(mask_image)

        request_body = build_webui_body(edit_mode, source_image, mask_image)
        if crop_bounds is not None:
            request_body.inpaint_full_res = False
            request_body.inpaint_full_res_padding = None
        if edit_mode == EDIT_MODE_INPAINT:
            submit = webservice.submit_inpaint
        elif edit_mode == EDIT_MODE_IMG2IMG:
            submit = webservice.submit_img2img
        else:
            assert edit_mode == EDIT_MODE_TXT2IMG
            submit = webservice.submit_txt2img

        try:
            result = self._wait_for_job(submit(request_body), status_signal)
            if result is None:
                return
            image_data = [pil_to_qimage(image) for image in result.images]
            if crop_bounds is not None:
                assert original_source_image is not None
                image_data = self._restore_cropped_inpainting_images(original_source_image, crop_bounds, image_data)
            for i, response_image in enumerate(image_data):
                self._cache_generated_image(response_image, i)
            info = result.raw_info
            if isinstance(info, GenerationInfoData):
                status_signal.emit({'seed': str(info.seed), 'subseed': str(info.subseed)})
        except BackendTimeoutError as err:
            raise RuntimeError(ERROR_MESSAGE_TIMEOUT) from err
        except SDBackendError as image_gen_error:
            logger.error(f'request failed: {image_gen_error}')
            raise RuntimeError(f'request failed: {image_gen_error}') from image_gen_error

    def upscale_image(self, image: QImage, new_size: QSize, status_signal: SignalInstance,
                      image_signal: SignalInstance) -> None:
        """Upscales an image using cached upscaling settings."""
        assert self._webservice is not None
        upscale_params = build_upscale_params(build_webui_body(EDIT_MODE_TXT2IMG))
        handle = self._webservice.submit_upscale(qimage_to_pil(image), new_size.width(), new_size.height(),
                                                 upscale_params)
        result = self._wait_for_job(handle, status_signal)
        if result is None:
            return
        if len(result.images) == 0:
            raise RuntimeError(GENERATE_ERROR_TITLE)
        image_signal.emit(pil_to_qimage(result.images[-1]))

    @menu_action(MENU_STABLE_DIFFUSION, 'prompt_style_shortcut', 200, [APP_STATE_EDITING],
                 condition_check=_check_prompt_styles_available)
    def show_style_window(self) -> None:
        """Show the saved prompt style window."""
        style_window = PromptStyleWindow()
        # TODO: update after the prompt style endpoint gets POST support
        # style_window.should_save_changes.connect(self._update_styles)
        style_window.exec()
