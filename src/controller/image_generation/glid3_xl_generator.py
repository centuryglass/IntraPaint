"""Generate images using GLID-3-XL running locally."""
import logging
from argparse import Namespace
from typing import Optional, Any, Dict

from PyQt6.QtCore import pyqtSignal, QSize
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication, QWidget

from src.config.application_config import AppConfig
from src.controller.image_generation.image_generator import ImageGenerator
from src.image.layers.image_stack import ImageStack
from src.ui.modal.settings_modal import SettingsModal
from src.ui.panel.generators.glid_panel import GlidPanel
from src.ui.window.main_window import MainWindow
from src.util.image_utils import qimage_to_pil_image, pil_image_to_qimage
from src.util.optional_import import optional_import
from src.util.shared_constants import EDIT_MODE_INPAINT
from src.util.validation import assert_types

# Imports require considerable setup and many extra nested dependencies, so all of them are imported as optional to
# prevent crashing when GLID-3-XL isn't fully configured.
torch = optional_import('torch')
get_device = optional_import('src.glid_3_xl.ml_utils', attr_name='get_device')
foreach_image_in_sample = optional_import('src.glid_3_xl.ml_utils', attr_name='foreach_image_in_sample')
create_sample_function = optional_import('src.glid_3_xl.create_sample_function',
                                         attr_name='create_sample_function')
load_models = optional_import('src.glid_3_xl.load_models', attr_name='load_models')
generate_samples = optional_import('src.glid_3_xl.generate_samples', attr_name='generate_samples')

logger = logging.getLogger(__name__)

# The QCoreApplication.translate context for strings in this file
TR_ID = 'controller.image_generation.glid3_xl_generator'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


DEFAULT_GLID_MODEL = 'models/inpaint.pt'
MIN_GLID_VRAM = 8000000000  # This is just a rough estimate.
GLID_CONFIG_CATEGORY = 'GLID-3-XL'
GLID_WEB_GENERATOR_NAME = _tr('GLID-3-XL image generation')
GLID_WEB_GENERATOR_DESCRIPTION = _tr('<p>Generate images by running a GLID-3-XL image generation model.</p></br>  <p>'
                                     'This mode is included mostly for historical reasons, GLID-3-XL is primitive by '
                                     'modern standards, only supporting inpainting and only generating images up to '
                                     '256x256 pixels.  This mode was one of the two supported modes available when '
                                     'IntraPaint alpha was released in 2022.  Instructions for setting it up can be '
                                     'found '
                                     '<a href="https://github.com/centuryglass/IntraPaint?tab=readme-ov-file#setup">'
                                     'here</a></p>')


class Glid3XLGenerator(ImageGenerator):
    """Interface for providing image generation capabilities."""

    def __init__(self, window: MainWindow, image_stack: ImageStack, args: Namespace) -> None:
        super().__init__(window, image_stack)
        self._control_panel: Optional[GlidPanel] = None
        self._clip_guidance = args.clip_guidance
        self._ddim = args.ddim
        self._ddpm = args.ddpm
        self._model_path = DEFAULT_GLID_MODEL if args.model_path is None else args.model_path
        self._bert_path = args.bert_path
        self._kl_path = args.kl_path
        self._steps = args.steps
        self._clip_guidance = args.clip_guidance
        self._cpu = args.cpu
        self._ddpm = args.ddpm
        self._ddim = args.ddim

        self._model_params: Optional[Dict[str, Any]] = None
        self._model: Optional[Any] = None
        self._diffusion: Optional[Any] = None
        self._ldm: Optional[Any] = None
        self._bert: Optional[Any] = None
        self._clip_model: Optional[Any] = None
        self._clip_preprocess: Optional[Any] = None
        self._normalize: Optional[Any] = None

    def get_display_name(self) -> str:
        """Returns a display name identifying the generator."""
        return GLID_WEB_GENERATOR_NAME

    def get_description(self) -> str:
        """Returns an extended description of this generator."""
        return GLID_WEB_GENERATOR_DESCRIPTION

    def is_available(self) -> bool:
        """Returns whether the generator is supported on the current system."""
        if None in (torch, get_device, foreach_image_in_sample, generate_samples, create_sample_function, load_models):
            return False
        device = get_device()
        (mem_free, mem_total) = torch.cuda.mem_get_info(device)
        if mem_free < MIN_GLID_VRAM:
            return False
        return True

    def configure_or_connect(self) -> bool:
        """Handles any required steps necessary to configure the generator, install required components, and/or
           connect to required external services, returning whether the process completed correctly."""
        if not self.is_available():
            return False
        AppConfig().set(AppConfig.GENERATION_SIZE, QSize(256, 256))
        AppConfig().set(AppConfig.EDIT_MODE, EDIT_MODE_INPAINT)
        device = get_device()
        logger.info('Using device: %s', device)
        self._model_params, self._model, self._diffusion, self._ldm, self._bert, self._clip_model, \
            self._clip_preprocess, self._normalize = load_models(device,
                                                                 model_path=self._model_path,
                                                                 bert_path=self._bert_path,
                                                                 kl_path=self._kl_path,
                                                                 steps=self._steps,
                                                                 clip_guidance=self._clip_guidance,
                                                                 cpu=self._cpu,
                                                                 ddpm=self._ddpm,
                                                                 ddim=self._ddim)
        return True

    def disconnect_or_disable(self) -> None:
        """Unload GLID-3-XL models."""
        assert torch is not None
        self._model_params = None
        self._model = None
        self._diffusion = None
        self._ldm = None
        self._bert = None
        self._clip_model = None
        self._clip_preprocess = None
        self._normalize = None
        torch.cuda.empty_cache()

    def init_settings(self, settings_modal: SettingsModal) -> None:
        """Updates a settings modal to add settings relevant to this generator."""
        settings_modal.load_from_config(AppConfig(), [GLID_CONFIG_CATEGORY])

    def refresh_settings(self, settings_modal: SettingsModal) -> None:
        """Reloads current values for this generator's settings, and updates them in the settings modal."""
        config = AppConfig()
        settings = {}
        for key in config.get_category_keys(GLID_CONFIG_CATEGORY):
            settings[key] = config.get(key)
        settings_modal.update_settings(settings)

    def update_settings(self, changed_settings: dict[str, Any]) -> None:
        """Applies any changed settings from a SettingsModal that are relevant to the image generator and require
           special handling."""
        config = AppConfig()
        glid_keys = config.get_category_keys(GLID_CONFIG_CATEGORY)
        for key, value in changed_settings.items():
            if key in glid_keys:
                config.set(key, value)

    def unload_settings(self, settings_modal: SettingsModal) -> None:
        """Unloads this generator's settings from the settings modal."""
        settings_modal.remove_category(AppConfig(), GLID_CONFIG_CATEGORY)

    def get_control_panel(self) -> QWidget:
        """Returns a widget with inputs for controlling this generator."""
        if self._control_panel is None:
            self._control_panel = GlidPanel()
            self._control_panel.generate_signal.connect(self.start_and_manage_image_generation)
        return self._control_panel

    def generate(self,
                 status_signal: pyqtSignal,
                 source_image: Optional[QImage] = None,
                 mask_image: Optional[QImage] = None) -> None:
        """Generates new images. Image size, image count, prompts, etc. are loaded from AppConfig as needed.

        Parameters
        ----------
        status_signal : pyqtSignal[str]
            Signal to emit when status updates are available.
        source_image : QImage, optional
            Image used as a basis for the edited image.
        mask_image : QImage, optional
            Mask marking edited image region.
        """
        try:
            assert_types((source_image, mask_image), QImage)
        except TypeError as err:
            raise RuntimeError('GLID-3-XL inpainting always requires a source and mask image') from err
        config = AppConfig()
        assert source_image is not None
        assert mask_image is not None
        if source_image.size() != mask_image.size():
            raise RuntimeError(f'Selection and mask widths should match, found {source_image.size()}'
                               f' and {mask_image.size()}')
        if source_image.hasAlphaChannel():
            source_image = source_image.convertToFormat(QImage.Format.Format_RGB32)

        batch_size = config.get(AppConfig.BATCH_SIZE)
        batch_count = config.get(AppConfig.BATCH_COUNT)
        device = get_device()
        sample_fn, unused_clip_score_fn = create_sample_function(
            device,
            self._model,
            self._model_params,
            self._bert,
            self._clip_model,
            self._clip_preprocess,
            self._ldm,
            self._diffusion,
            self._normalize,
            image=None,  # Inpainting uses edit instead of this param
            mask=qimage_to_pil_image(mask_image),
            prompt=config.get(AppConfig.PROMPT),
            negative=config.get(AppConfig.NEGATIVE_PROMPT),
            guidance_scale=config.get(AppConfig.GUIDANCE_SCALE),
            batch_size=batch_size,
            edit=qimage_to_pil_image(source_image),
            width=source_image.width(),
            height=source_image.height(),
            edit_width=source_image.width(),
            edit_height=source_image.height(),
            cutn=config.get(AppConfig.CUTN),
            clip_guidance=self._clip_guidance,
            skip_timesteps=config.get(AppConfig.SKIP_STEPS),
            ddpm=self._ddpm,
            ddim=self._ddim)

        # noinspection PyUnusedLocal
        def save_sample(i, sample, unused_clip_score=False) -> None:
            """Extract generated samples and repackage into the appropriate structure."""
            print(f'save sample {i}')
            foreach_image_in_sample(
                sample,
                batch_size,
                self._ldm,
                lambda k, img: self._cache_generated_image(pil_image_to_qimage(img), (i * batch_size) + k))

        generate_samples(
            device,
            self._ldm,
            self._diffusion,
            sample_fn,
            save_sample,
            batch_size,
            batch_count,
            source_image.width,
            source_image.height)
        print('exit')
