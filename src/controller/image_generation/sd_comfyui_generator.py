"""Generates images through the Stable-Diffusion ComfyUI"""
import logging
from argparse import Namespace
from typing import Optional, cast, Any

from PySide6.QtCore import Signal, QSize, QThread, QRect, QPoint
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication
from requests import ReadTimeout

from src.api.a1111_webservice import AuthError
from src.api.comfyui.comfyui_types import ImageFileReference
from src.api.comfyui_webservice import ComfyUiWebservice, ComfyModelType, AsyncTaskProgress, AsyncTaskStatus
from src.api.controlnet.controlnet_constants import ControlTypeDef
from src.api.controlnet.controlnet_preprocessor import ControlNetPreprocessor
from src.api.webservice import WebService
from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_generation.sd_generator import SDGenerator, SD_BASE_DESCRIPTION, \
    STABLE_DIFFUSION_CONFIG_CATEGORY
from src.image.filter.blur import BlurFilter, MODE_GAUSSIAN
from src.image.layers.image_stack import ImageStack
from src.ui.modal.settings_modal import SettingsModal
from src.ui.panel.generators.comfyui_extras_tab import ComfyUIExtrasTab
from src.ui.panel.generators.generator_panel import GeneratorPanel
from src.ui.panel.generators.stable_diffusion_panel import StableDiffusionPanel
from src.ui.window.extra_network_window import LORA_KEY_NAME, LORA_KEY_ALIAS, LORA_KEY_PATH
from src.ui.window.main_window import MainWindow
from src.util.application_state import AppStateTracker, APP_STATE_LOADING
from src.util.parameter import TYPE_LIST, TYPE_STR
from src.util.shared_constants import EDIT_MODE_TXT2IMG, EDIT_MODE_INPAINT, EDIT_MODE_IMG2IMG, AUTH_ERROR, \
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

MENU_STABLE_DIFFUSION = 'Stable-Diffusion'


def _check_prompt_styles_available(_) -> bool:
    cache = Cache()
    return len(cache.get(Cache.STYLES)) > 0


def _check_lora_available(_) -> bool:
    cache = Cache()
    return len(cache.get(Cache.LORA_MODELS)) > 0


class SDComfyUIGenerator(SDGenerator):
    """Interface for providing image generation capabilities."""

    def __init__(self, window: MainWindow, image_stack: ImageStack, args: Namespace) -> None:
        super().__init__(window, image_stack, args, Cache.SD_COMFYUI_SERVER_URL)
        self._image_stack = image_stack
        self._webservice: Optional[ComfyUiWebservice] = ComfyUiWebservice(self.server_url)
        self._gen_extras_tab = ComfyUIExtrasTab()
        self._active_task_id = ''
        self._active_task_number = 0

    def get_display_name(self) -> str:
        """Returns a display name identifying the generator."""
        return SD_COMFYUI_GENERATOR_NAME

    def get_setup_text(self) -> str:
        """Returns a rich text description of how to set up this generator."""
        return SD_COMFYUI_GENERATOR_SETUP

    def get_description(self) -> str:
        """Returns an extended description of this generator."""
        return SD_COMFYUI_GENERATOR_DESCRIPTION

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
        self._webservice = ComfyUiWebservice(url)
        return self._webservice

    def interrogate(self) -> None:
        """Update the prompt to match image content using an AI image description model."""
        raise RuntimeError('ComfyUI lacks interrogate support')

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
            return self._webservice.get_controlnets()
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
        return [Cache.CONTROLNET_ARGS_0_COMFYUI, Cache.CONTROLNET_ARGS_1_COMFYUI, Cache.CONTROLNET_ARGS_2_COMFYUI]

    def get_diffusion_model_names(self) -> list[str]:
        """Return the list of available image generation models."""
        assert self._webservice is not None
        try:
            return self._webservice.get_sd_checkpoints()
        except (RuntimeError, KeyError) as err:
            logger.error(f'Loading stable-diffusion model list failed: {err}')
            return []

    def get_lora_model_info(self) -> list[dict[str, str]]:
        """Return available LoRA model extensions."""
        assert self._webservice is not None
        try:
            lora_names = self._webservice.get_lora_models()
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
        except (RuntimeError, KeyError) as err:
            logger.error(f'Loading stable-diffusion LoRA model list failed: {err}')
            return []

    def get_diffusion_sampler_names(self) -> list[str]:
        """Return the list of available samplers."""
        assert self._webservice is not None
        try:
            return self._webservice.get_sampler_names()
        except (RuntimeError, KeyError) as err:
            logger.error(f'Loading stable-diffusion sampler option list failed: {err}')
            return []

    def get_upscale_method_names(self) -> list[str]:
        """Return the list of available upscale methods."""
        assert self._webservice is not None
        try:
            return self._webservice.get_models(ComfyModelType.UPSCALING)
        except (RuntimeError, KeyError) as err:
            logger.error(f'Loading stable-diffusion LoRA model list failed: {err}')
            return []

    def cache_generator_specific_data(self) -> None:
        """When activating the generator, after the webservice is connected, this method should be implemented to
           load and cache any generator-specific API data."""
        cache = Cache()
        assert self._webservice is not None
        for model_type, cache_key in ((ComfyModelType.CONFIG, Cache.COMFYUI_MODEL_CONFIG),
                                      (ComfyModelType.HYPERNETWORKS, Cache.HYPERNETWORK_MODELS)):
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
        try:
            cache.update_options(Cache.SCHEDULER, self._webservice.get_scheduler_names())
        except (RuntimeError, KeyError) as err:
            logger.error(f'Loading scheduler options failed: {err}')
            cache.restore_default_options(Cache.SCHEDULER)

    def clear_cached_generator_data(self) -> None:
        """Clear any cached data specific to this image generator."""
        Cache().restore_default_options(Cache.COMFYUI_MODEL_CONFIG)

    def cancel_generation(self) -> None:
        """Cancels image generation, if in-progress"""
        assert self._webservice is not None
        if AppStateTracker.app_state() == APP_STATE_LOADING:
            self._webservice.interrupt(self._active_task_id)

    def load_lora_thumbnail(self, lora_info: Optional[dict[str, str]]) -> Optional[QImage]:
        """Attempt to load a LoRA model thumbnail image from the API."""
        return None  # ComfyUI doesn't provide LoRA thumbnails.

    def load_preprocessor_preview(self, preprocessor: ControlNetPreprocessor,
                                  image: QImage, mask: Optional[QImage],
                                  status_signal: Signal,
                                  image_signal: Signal) -> None:
        """Requests a ControlNet preprocessor preview image."""
        assert self._webservice is not None
        queue_info = self._webservice.controlnet_preprocessor_preview(image, mask, preprocessor)
        self._active_task_number = queue_info['number']
        self._active_task_id = queue_info['prompt_id']
        final_status = self._repeated_progress_check(self._active_task_id, self._active_task_number, 0, 1,
                                                     status_signal)

        if 'outputs' not in final_status:
            preview_image = image
        else:
            assert self._webservice is not None
            image_data = self._webservice.download_images(final_status['outputs']['images'])
            if len(image_data) != 1:
                logger.warning(f'Expected one preprocessor preview image, got {len(image_data)}')
            preview_image = image_data[0]
        image_signal.emit(preview_image)

    def get_gen_area_image(self, init_image: Optional[QImage] = None) -> QImage:
        """Gets the contents of the image generation area, handling any necessary preprocessing."""
        image = init_image if init_image is not None else self._image_stack.qimage_generation_area_content()
        return self._scale_and_crop_gen_qimage(image)

    def get_gen_area_mask(self, init_mask: Optional[QImage] = None) -> QImage:
        """Gets the inpainting mask for the image generation area, handling any necessary preprocessing."""
        selection_layer = self._image_stack.selection_layer
        mask = init_mask if init_mask is not None else selection_layer.mask_image
        mask = self._scale_and_crop_gen_qimage(mask)
        # ComfyUI doesn't blur masks unless you add another node to do it, so me might as well just do it here:
        blur_radius = AppConfig().get(AppConfig.MASK_BLUR)
        if blur_radius > 0:
            mask = BlurFilter.blur(mask, MODE_GAUSSIAN, blur_radius)
        # ComfyUI expects inverted masks:
        mask.invertPixels(QImage.InvertMode.InvertRgba)
        return mask

    def is_available(self) -> bool:
        """Returns whether the generator is supported on the current system."""
        if self._webservice is None:
            self._webservice = ComfyUiWebservice(self._server_url)
        try:
            # Use the system status endpoint to check for ComfyUI:
            system_status = self._webservice.get_system_stats()
            return 'system' in system_status and 'comfyui_version' in system_status['system']
        except RuntimeError as req_err:
            logger.error(f'Login check connection failed: {req_err}')
        except AuthError:
            self.status_signal.emit(AUTH_ERROR)
        return False

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

    # def interrogate(self) -> None:
    #     """ Use CLIP interrogation to automatically generate image prompts.
    #
    #     TODO: ComfyUI doesn't support this by default, I'll probably need to track down a custom node that does it.
    #           Of course, I'll also need to scan installed nodes to make sure that one is actually there, and I'll need
    #           to add and remove the "Interrogate" button based on that node's availability.
    #     """
    #     print('CLIP interrogate not yet available for ComfyUI!')

    def get_control_panel(self) -> Optional[GeneratorPanel]:
        """Returns a widget with inputs for controlling this generator."""
        if self._control_panel is None:
            self._control_panel = StableDiffusionPanel(False, False)
            self._control_panel.hide()
            self._control_panel.generate_signal.connect(self.start_and_manage_image_generation)

            # self._control_panel.interrogate_signal.connect(self.interrogate)

            # Configure "extras" tab in control panel:
            def _clear_comfyui_memory() -> None:
                assert self._webservice is not None
                self._webservice.free_memory()

            self._gen_extras_tab.clear_comfyui_memory_signal.connect(_clear_comfyui_memory)
            self._control_panel.add_extras_tab(self._gen_extras_tab)
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
                        status_text = (
                            f'{TASK_STATUS_BATCH_NUMBER.format(batch_num=batch_num, num_batches=num_batches)}'
                            f' {status_text}')
                    status_text = f'{status_text}\n{last_percentage}%'
                    if external_status_signal is not None:
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

    def _inpaint_gen_area_crop_bounds(self) -> QRect:
        cache = Cache()
        edit_mode = cache.get(Cache.EDIT_MODE)
        gen_area = self._image_stack.generation_area
        if edit_mode != EDIT_MODE_INPAINT or not cache.get(Cache.INPAINT_FULL_RES):
            return QRect(QPoint(), gen_area.size())

        selection_layer = self._image_stack.selection_layer
        selection_gen_area = selection_layer.get_selection_gen_area()
        if selection_gen_area is None or selection_gen_area.size() == gen_area.size():
            return QRect(QPoint(), gen_area.size())
        return selection_gen_area.translated(-selection_layer.position - gen_area.topLeft())

    def _scale_and_crop_gen_qimage(self, image: QImage) -> QImage:
        crop_bounds = self._inpaint_gen_area_crop_bounds()
        if crop_bounds.size() != image.size():
            image = image.copy(crop_bounds)
        gen_size = Cache().get(Cache.GENERATION_SIZE)
        if image.size() != gen_size:
            return pil_image_scaling(image, gen_size)
        return image

    def _restore_cropped_inpainting_images(self, initial_image: QImage, crop_bounds: QRect,
                                           cropped_images: list[QImage]) -> list[QImage]:
        assert QRect(QPoint(), initial_image.size()).contains(crop_bounds)
        gen_area = self._image_stack.generation_area
        if gen_area.size() == crop_bounds.size():
            return cropped_images
        restored_images: list[QImage] = []
        for cropped_image in cropped_images:
            if cropped_image.size() != crop_bounds.size():
                cropped_image = pil_image_scaling(cropped_image, crop_bounds.size())
            final_image = initial_image.copy()
            painter = QPainter(final_image)
            painter.drawImage(crop_bounds, cropped_image)
            painter.end()
            restored_images.append(final_image)
        return restored_images

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
            if inpaint_inner_bounds.size() != gen_area.size():
                original_source_image = source_image

        # Pre-process image and mask as necessary:
        source_image = self.get_gen_area_image(source_image)
        if mask_image is not None:
            mask_image = self.get_gen_area_mask(mask_image)

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
                # If using "inpaint full res", scale and pad images to make them match the gen. area size again.
                if inpaint_inner_bounds.size() != gen_area.size() and original_source_image is not None:
                    image_data = self._restore_cropped_inpainting_images(original_source_image, inpaint_inner_bounds,
                                                                         image_data)
                for i, response_image in enumerate(image_data):
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

    def upscale_image(self, image: QImage, new_size: QSize, status_signal: Signal, image_signal: Signal) -> None:
        """Upscales an image using cached upscaling settings."""
        assert self._webservice is not None
        queue_info = self._webservice.upscale(self._image_stack.qimage(), new_size.width(),
                                              new_size.height())
        if 'error' in queue_info:
            raise RuntimeError(str(queue_info['error']))
        assert 'number' in queue_info
        assert 'prompt_id' in queue_info
        self._active_task_number = queue_info['number']
        self._active_task_id = queue_info['prompt_id']

        # Check progress in a loop until it finishes or something goes wrong:
        final_status = self._repeated_progress_check(self._active_task_id, self._active_task_number, 0,
                                                     1, status_signal)
        if 'outputs' not in final_status:
            raise RuntimeError(GENERATE_ERROR_TITLE)
        image_data = self._webservice.download_images(final_status['outputs']['images'])
        assert len(image_data) > 0
        upscaled_image = image_data[0]
        if upscaled_image.size() != new_size:
            # Apply final scaling, necessary if width and height scale don't exactly match, or if using an
            # upscaling model with a fixed scale:
            upscaled_image = pil_image_scaling(upscaled_image, new_size)
        image_signal.emit(upscaled_image)
