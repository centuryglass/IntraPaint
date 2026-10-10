"""Generates images through Stable Diffusion and ComfyUI, using the `sd_backend_client` library's ComfyUI client."""
import logging
from argparse import Namespace
from typing import Optional, cast, Any

from PySide6.QtCore import QSize, QRect, QPoint, SignalInstance
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from sd_backend_client import AuthError, BackendOption, BackendTimeoutError, ComfyUiWebservice, \
    PREPROCESSOR_NONE, SDBackendError, ControlNetPreprocessor, ControlTypeDef
# Not in the library's public API. The model config list has no `Backend` equivalent.
from sd_backend_client.api.comfyui_webservice import ComfyModelType

from src.api.controlnet.controlnet_unit import ControlKeyType
from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_generation.sd_adapters.image_adapter import pil_to_qimage, qimage_to_pil
from src.controller.image_generation.sd_adapters.params_adapter import build_comfy_params, build_upscale_params
from src.controller.image_generation.sd_generator import SDGenerator, SD_BASE_DESCRIPTION, \
    STABLE_DIFFUSION_CONFIG_CATEGORY, GETTING_SD_MODELS, INSTALLATION_STABILITY_MATRIX
from src.image.filter.blur import BlurFilter, MODE_GAUSSIAN
from src.image.layers.image_stack import ImageStack
from src.ui.modal.settings_modal import SettingsModal
from src.ui.panel.generators.comfyui_extras_tab import ComfyUIExtrasTab
from src.ui.panel.generators.generator_panel import GeneratorPanel
from src.ui.panel.generators.stable_diffusion_panel import StableDiffusionPanel
from src.ui.window.extra_network_window import LORA_KEY_NAME, LORA_KEY_ALIAS, LORA_KEY_PATH
from src.ui.window.main_window import MainWindow
from src.util.parameter import TYPE_LIST, TYPE_STR
from src.util.shared_constants import EDIT_MODE_TXT2IMG, EDIT_MODE_INPAINT, EDIT_MODE_IMG2IMG, AUTH_ERROR, \
    GENERATE_ERROR_MESSAGE_EMPTY_MASK, GENERATE_ERROR_TITLE, ERROR_MESSAGE_TIMEOUT, MISC_CONNECTION_ERROR
from src.util.visual.pil_image_utils import pil_image_scaling

logger = logging.getLogger(__name__)

# The QCoreApplication.translate context for strings in this file
TR_ID = 'controller.image_generation.sd_comfyui_generator'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


SD_COMFYUI_GENERATOR_NAME = _tr('Stable Diffusion ComfyUI API')
SD_COMFYUI_GENERATOR_DESCRIPTION_HEADER = _tr('<h2>Stable Diffusion: via ComfyUI API</h2>')
SD_COMFYUI_GENERATOR_DESCRIPTION_COMFYUI = _tr("""
<h3>About ComfyUI</h3>
<p>
    <a href="https://www.comfy.org/">ComfyUI</a> is a popular Stable Diffusion interface with complex and powerful
    node-based controls. When the ComfyUI is running, IntraPaint can access Stable Diffusion image generation by
    sending requests to ComfyUI.  You can run ComfyUI on the same computer as IntraPaint, or remotely on a separate
     server.
</p>
<p>
    When connected, IntraPaint provides controls for ComfyUI in the <b>Image Generation</b> tab and in the <b>settings
    window</b> under the Stable Diffusion category. You can also access ComfyUI's interface directly through a web 
    browser at <a href="http://localhost:8188/">localhost:8188</a>.
</p>
""")
SD_COMFYUI_GENERATOR_DESCRIPTION = (f'{SD_COMFYUI_GENERATOR_DESCRIPTION_HEADER}\n{SD_BASE_DESCRIPTION}'
                                    f'\n{SD_COMFYUI_GENERATOR_DESCRIPTION_COMFYUI}')

# noinspection SpellCheckingInspection
SD_COMFYUI_GENERATOR_SETUP_OPTIONS = _tr("""
<h1>Stable Diffusion ComfyUI Generator Setup</h1>
<p>
    To use the Stable Diffusion ComfyUI generator, you will to download at least one Stable Diffusion model file, 
    install ComfyUI, and start it.  This guide will explain each of those steps.
</p>""" + GETTING_SD_MODELS + """
<hr/>
<h2>Installing ComfyUI: Available options</h2>
<p>
    There are a few different ways you can install ComfyUI. The recommended method is to use
    <a href="https://github.com/LykosAI/StabilityMatrix?tab=readme-ov-file#stability-matrix">Stability Matrix</a>,
    but other methods are covered here for the sake of completeness.
</p>
<hr/>
<h2>Option 1: Stability Matrix</h2>
<p>
    Installation through Stability Matrix is the recommended method. This method is the simplest option, provides a lot
    of helpful extra resources, and supports Windows, macOS and Linux.  This method also lets you easily install and use
    Stable Diffusion WebUI, the other Stable Diffusion client that IntraPaint can use.
</p>""")
SD_COMFYUI_GENERATOR_STABILITY_MATRIX_PACKAGE = 'ComfyUI'
SD_COMFYUI_GENERATOR_SETUP_STABILITY_MATRIX = INSTALLATION_STABILITY_MATRIX.format(
    generator_package=SD_COMFYUI_GENERATOR_STABILITY_MATRIX_PACKAGE,
    post_install_generator_setup=''
)
SD_COMFYUI_GENERATOR_SETUP_ALTERNATIVES = _tr("""
<hr/>
<h2>Option 2: Prepackaged Windows version</h2>
<p>
    If you're using Windows and don't need any of the extra features in Stability Matrix, you can download a 
    prepackaged version of ComfyUI from GitHub.
</p>
<ol>
    <li>
        Download <b>ComfyUI_windows_portable_nvidia.7z</b> from the most recent version listed on the <a href=
        "https://github.com/comfyanonymous/ComfyUI/releases">ComfyUI GitHub release page</a>.<br/>
    </li>
    <li>
        Extract the downloaded package into a new folder. If you're not using Windows 11, you may need to install
        <a href="https://www.7-zip.org">7-Zip</a> to extract the compressed files.<br/>
    </li>
    <li>
        If you haven't already found at least one Stable Diffusion model file, do that now. Copy it into the 
        ComfyUI folder under <b>ComfyUI\\models\\checkpoints</b>.<br/>
    </li>
    <li>
        Launch the <b>run_nvidia_gpu.bat</b> file in the ComfyUI folder to start Stable Diffusion. A terminal window
        will open and print startup information as Comfy initializes.<br/>
    </li>
    <li>
        Once you see <b>"To see the GUI go to: http://127.0.0.1:8188"</b> in the terminal window, Stable Diffusion is
        ready to use.  Back in IntraPaint, click the "Activate" button below to connect to Stable Diffusion. <br/>
    </li>
    <li>
        In the future, the only step you'll need to repeat from this list is launching <b>run_nvidia_gpu.bat</b> and
        waiting for it to finish starting up. If you do this before launching IntraPaint, it will automatically connect
        to the ComfyUI image generator on startup.
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
    Because this option isn't recommended, IntraPaint won't provide a full guide.
    <a href="https://github.com/comfyanonymous/ComfyUI?tab=readme-ov-file#manual-install-windows-linux">
    ComfyUI's manual installation instructions</a> should help you get started. If you run into any problems,
    searching the <a href="https://github.com/comfyanonymous/ComfyUI/issues">ComfyUI issues page</a> will 
    probably help you find a solution.
</p>
""")
SD_COMFYUI_GENERATOR_SETUP = SD_COMFYUI_GENERATOR_SETUP_OPTIONS + SD_COMFYUI_GENERATOR_SETUP_STABILITY_MATRIX \
                             + SD_COMFYUI_GENERATOR_SETUP_ALTERNATIVES


DEFAULT_COMFYUI_URL = 'http://localhost:8188'


def _check_prompt_styles_available(_) -> bool:
    cache = Cache()
    return len(cache.get(Cache.STYLES)) > 0


def _check_lora_available(_) -> bool:
    cache = Cache()
    return len(cache.get(Cache.LORA_MODELS)) > 0


def _option_names(options: list[BackendOption]) -> list[str]:
    return [option.name for option in options]


class SDComfyUIGenerator(SDGenerator):
    """Interface for providing image generation capabilities."""

    def __init__(self, window: MainWindow, image_stack: ImageStack, args: Namespace) -> None:
        super().__init__(window, image_stack, args, Cache.SD_COMFYUI_SERVER_URL, ControlKeyType.COMFYUI)
        self._image_stack = image_stack
        self._webservice: Optional[ComfyUiWebservice] = ComfyUiWebservice(self.server_url)
        self._gen_extras_tab = ComfyUIExtrasTab()
        # The job the worker thread is waiting on, which `cancel_generation` cancels from the main thread:

    def get_display_name(self) -> str:
        """Returns a display name identifying the generator."""
        return SD_COMFYUI_GENERATOR_NAME

    def get_setup_text(self) -> str:
        """Returns a rich text description of how to set up this generator."""
        return SD_COMFYUI_GENERATOR_SETUP

    def get_description(self) -> str:
        """Returns an extended description of this generator."""
        return SD_COMFYUI_GENERATOR_DESCRIPTION

    def get_webservice(self) -> Optional[ComfyUiWebservice]:
        """Return the webservice object this module uses to connect to Stable Diffusion, if initialized."""
        return self._webservice

    def remove_webservice(self) -> None:
        """Destroy and remove any active webservice object."""
        self._webservice = None

    def create_or_get_webservice(self, url: str) -> ComfyUiWebservice:
        """Return the webservice object this module uses to connect to Stable Diffusion.  If the webservice already
           exists but the url doesn't match, a new webservice should replace the existing one, using the new url."""
        if self._webservice is not None:
            if self._webservice.server_url == url.rstrip('/'):
                return self._webservice
            self._webservice.disconnect()
            self._webservice = None
        self._webservice = ComfyUiWebservice(url)
        return self._webservice

    def interrogate(self) -> None:
        """Update the prompt to match image content using an AI image description model."""
        raise RuntimeError('ComfyUI lacks interrogate support')

    def get_controlnet_preprocessors(self) -> list[ControlNetPreprocessor]:
        """Return the list of available Controlnet preprocessors."""
        assert self._webservice is not None
        try:
            library_preprocessors = self._webservice.get_controlnet_preprocessors()
        except SDBackendError as err:
            logger.error(f'Loading ControlNet preprocessors failed: {err}')
            return []
        preprocessors = list(library_preprocessors)
        if not any(preprocessor.name == PREPROCESSOR_NONE for preprocessor in preprocessors):
            preprocessors.append(ControlNetPreprocessor(name=PREPROCESSOR_NONE))
        return preprocessors

    def get_controlnet_models(self) -> list[str]:
        """Return the list of available ControlNet models."""
        assert self._webservice is not None
        try:
            return [model.full_model_name for model in self._webservice.list_controlnet_models()]
        except SDBackendError as err:
            logger.error(f'Loading ControlNet models failed: {err}')
            return []

    def get_controlnet_types(self) -> dict[str, ControlTypeDef]:
        """Return available ControlNet categories."""
        assert self._webservice is not None
        try:
            return self._webservice.get_controlnet_type_categories()
        except SDBackendError as err:
            logger.error(f'Loading ControlNet types failed: {err}')
            return {}

    def get_controlnet_unit_cache_keys(self) -> list[str]:
        """Return keys used to cache serialized ControlNet units as strings."""
        return [Cache.CONTROLNET_ARGS_0_COMFYUI, Cache.CONTROLNET_ARGS_1_COMFYUI, Cache.CONTROLNET_ARGS_2_COMFYUI]

    def get_diffusion_model_names(self) -> list[str]:
        """Return the list of available image generation models."""
        assert self._webservice is not None
        try:
            return _option_names(self._webservice.list_checkpoints())
        except SDBackendError as err:
            logger.error(f'Loading Stable Diffusion model list failed: {err}')
            return []

    def get_lora_model_info(self) -> list[dict[str, str]]:
        """Return available LoRA model extensions."""
        assert self._webservice is not None
        try:
            lora_names = _option_names(self._webservice.list_loras())
            lora_info: list[dict[str, str]] = []
            for lora_file in lora_names:
                if '.' in lora_file:
                    name = lora_file[:lora_file.rindex('.')]
                else:
                    name = lora_file
                lora_info.append({
                    LORA_KEY_NAME: name,
                    LORA_KEY_ALIAS: name,
                    LORA_KEY_PATH: lora_file
                })
            return lora_info
        except SDBackendError as err:
            logger.error(f'Loading Stable Diffusion LoRA model list failed: {err}')
            return []

    def get_diffusion_sampler_names(self) -> list[str]:
        """Return the list of available samplers."""
        assert self._webservice is not None
        try:
            return _option_names(self._webservice.list_samplers())
        except SDBackendError as err:
            logger.error(f'Loading Stable Diffusion sampler option list failed: {err}')
            return []

    def get_upscale_method_names(self) -> list[str]:
        """Return the list of available upscale methods."""
        assert self._webservice is not None
        try:
            return _option_names(self._webservice.list_upscalers())
        except SDBackendError as err:
            logger.error(f'Loading Stable Diffusion upscaling model list failed: {err}')
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
        cache = Cache()
        webservice = self._webservice
        assert webservice is not None

        def _list_model_configs() -> list[str]:
            assert webservice is not None
            return webservice.get_models(ComfyModelType.CONFIG)

        def _list_hypernetworks() -> list[str]:
            assert webservice is not None
            return _option_names(webservice.list_hypernetworks())

        for list_models, cache_key in ((_list_model_configs, Cache.COMFYUI_MODEL_CONFIG),
                                       (_list_hypernetworks, Cache.HYPERNETWORK_MODELS)):
            cache_data_type = cache.get_data_type(cache_key)
            try:
                model_list = list_models()
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
            except SDBackendError as err:
                logger.error(f'Loading {cache_key} model options failed: {err}')
                if cache_data_type == TYPE_LIST:
                    cache.set(cache_key, [])
                else:
                    assert cache_data_type == TYPE_STR
                    cache.restore_default_options(cache_key)
        try:
            cache.update_options(Cache.SCHEDULER, _option_names(webservice.list_schedulers()))
        except SDBackendError as err:
            logger.error(f'Loading scheduler options failed: {err}')
            cache.restore_default_options(Cache.SCHEDULER)

    def clear_cached_generator_data(self) -> None:
        """Clear any cached data specific to this image generator."""
        Cache().restore_default_options(Cache.COMFYUI_MODEL_CONFIG)

    def load_lora_thumbnail(self, lora_info: Optional[dict[str, str]]) -> Optional[QImage]:
        """Attempt to load a LoRA model thumbnail image from the API."""
        return None  # ComfyUI doesn't provide LoRA thumbnails.

    def get_gen_area_image(self, init_image: Optional[QImage] = None) -> QImage:
        """Gets the contents of the image generation area, handling any necessary preprocessing."""
        image = init_image if init_image is not None else self._image_stack.qimage_generation_area_content()
        return self._scale_and_crop_gen_qimage(image)

    def get_gen_area_mask(self, init_mask: Optional[QImage] = None) -> QImage:
        """Gets the inpainting mask for the image generation area, blurred by `AppConfig.MASK_BLUR`.

        ComfyUI doesn't blur masks, so the blur is applied here. The mask is opaque where content changes; the library
        converts it to ComfyUI's format when uploading it.
        """
        selection_layer = self._image_stack.selection_layer
        mask = init_mask if init_mask is not None else selection_layer.mask_image
        mask = self._scale_and_crop_gen_qimage(mask)
        blur_radius = AppConfig().get(AppConfig.MASK_BLUR)
        if blur_radius > 0:
            mask = BlurFilter.blur(mask, MODE_GAUSSIAN, blur_radius)
        return mask

    def is_available(self) -> bool:
        """Returns whether the generator is supported on the current system."""
        if self._webservice is None:
            self._webservice = ComfyUiWebservice(self._server_url)
        try:
            # Use the system status endpoint to check for ComfyUI. A server that isn't ComfyUI fails the request or
            # returns a response that fails validation:
            self._webservice.get_system_stats()
            return True
        except AuthError:
            self.status_signal.emit(AUTH_ERROR.format(url=self._server_url))
        except (SDBackendError, ValueError) as req_err:
            self.status_signal.emit(MISC_CONNECTION_ERROR.format(url=self._server_url,
                                                                 error_text=str(req_err)))
            logger.error(f'Login check connection failed: {req_err}')
        return False

    def init_settings(self, settings_modal: SettingsModal) -> None:
        """Updates a settings modal to add settings relevant to this generator."""
        assert self._webservice is not None
        # TODO: remote config options, similar to A1111Config
        app_config = AppConfig()
        settings_modal.load_from_config(app_config, [STABLE_DIFFUSION_CONFIG_CATEGORY])

    def refresh_settings(self, settings_modal: SettingsModal) -> None:
        """Reloads current values for this generator's settings, and updates them in the settings modal."""
        settings = {}
        app_config = AppConfig()
        for key in app_config.get_category_keys(STABLE_DIFFUSION_CONFIG_CATEGORY):
            settings[key] = app_config.get(key)
        settings_modal.update_settings(settings)

    def update_settings(self, changed_settings: dict[str, Any]) -> None:
        """Applies any changed settings from a SettingsModal that are relevant to the image generator and require
           special handling."""
        web_keys: list[str] = []

        app_keys = AppConfig().get_category_keys(STABLE_DIFFUSION_CONFIG_CATEGORY)
        web_changes = {}
        for key, value in changed_settings.items():
            if key in web_keys:
                web_changes[key] = value
            elif key in app_keys and not isinstance(value, (list, dict)):
                AppConfig().set(key, value)

    def unload_settings(self, settings_modal: SettingsModal) -> None:
        """Unloads this generator's settings from the settings modal."""
        settings_modal.remove_category(AppConfig(), STABLE_DIFFUSION_CONFIG_CATEGORY)

    def get_control_panel(self) -> Optional[GeneratorPanel]:
        """Returns a widget with inputs for controlling this generator."""
        if self._control_panel is None:
            self._control_panel = StableDiffusionPanel(False, False)
            self._control_panel.hide()
            self._control_panel.generate_signal.connect(self.start_and_manage_image_generation)

            # Configure "extras" tab in control panel:
            def _clear_comfyui_memory() -> None:
                assert self._webservice is not None
                self._webservice.free_memory()

            self._gen_extras_tab.clear_comfyui_memory_signal.connect(_clear_comfyui_memory)
            self._control_panel.add_extras_tab(self._gen_extras_tab)
        return self._control_panel

    def generate(self,
                 status_signal: SignalInstance,
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
        webservice = self._webservice
        assert webservice is not None
        cache = Cache()
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
            inpaint_inner_bounds = self._inpaint_gen_area_crop_bounds()
            if inpaint_inner_bounds.size() != source_image.size():
                original_source_image = source_image

        # Pre-process image and mask as necessary:
        source_image = self.get_gen_area_image(source_image)
        if mask_image is not None:
            mask_image = self.get_gen_area_mask(mask_image)

        if edit_mode == EDIT_MODE_INPAINT:
            submit = webservice.submit_inpaint
        elif edit_mode == EDIT_MODE_IMG2IMG:
            submit = webservice.submit_img2img
        else:
            assert edit_mode == EDIT_MODE_TXT2IMG
            submit = webservice.submit_txt2img

        num_batches = cache.get(Cache.BATCH_COUNT)
        seed: Optional[int] = None
        first_image_idx = 0
        for batch_num in range(num_batches):
            try:
                # Later batches continue from the first batch's seed, which the library picks when Cache.SEED is -1:
                sequence_seed = None if seed is None else seed + batch_num
                diffusion_params = build_comfy_params(edit_mode, source_image, mask_image, sequence_seed)
                result = self._wait_for_job(submit(diffusion_params), status_signal, batch_num, num_batches)
                if result is None:
                    return
                if seed is None:
                    seed = result.seed
                image_data = [pil_to_qimage(image) for image in result.images]
                # If using "inpaint full res", scale and pad images to make them match the gen. area size again.
                if inpaint_inner_bounds.size() != gen_area.size() and original_source_image is not None:
                    image_data = self._restore_cropped_inpainting_images(original_source_image, inpaint_inner_bounds,
                                                                         image_data)
                for i, response_image in enumerate(image_data):
                    self._cache_generated_image(response_image, i + first_image_idx)
                first_image_idx = first_image_idx + len(image_data)
            except BackendTimeoutError as err:
                raise RuntimeError(ERROR_MESSAGE_TIMEOUT) from err
            except SDBackendError as image_gen_error:
                logger.error(f'request failed: {image_gen_error}')
                raise RuntimeError(f'request failed: {image_gen_error}') from image_gen_error
        if seed is not None:
            status_signal.emit({'seed': str(seed)})

    def upscale_image(self, image: QImage, new_size: QSize, status_signal: SignalInstance,
                      image_signal: SignalInstance) -> None:
        """Upscales an image using cached upscaling settings."""
        assert self._webservice is not None
        upscale_params = build_upscale_params(build_comfy_params(EDIT_MODE_TXT2IMG))
        handle = self._webservice.submit_upscale(qimage_to_pil(image), new_size.width(), new_size.height(),
                                                 upscale_params)
        result = self._wait_for_job(handle, status_signal)
        if result is None:
            return
        if len(result.images) == 0:
            raise RuntimeError(GENERATE_ERROR_TITLE)
        upscaled_image = pil_to_qimage(result.images[0])
        if upscaled_image.size() != new_size:
            # Apply final scaling, necessary if width and height scale don't exactly match, or if using an
            # upscaling model with a fixed scale:
            upscaled_image = pil_image_scaling(upscaled_image, new_size)
        image_signal.emit(upscaled_image)
