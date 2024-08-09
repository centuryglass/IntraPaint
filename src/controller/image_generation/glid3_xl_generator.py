"""Generate images using GLID-3-XL running locally."""
import logging
import os
from argparse import Namespace
from typing import Optional, Any, Dict

from PySide6.QtCore import Signal, QSize
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QWidget

from src.config.application_config import AppConfig
from src.controller.image_generation.image_generator import ImageGenerator
from src.image.layers.image_stack import ImageStack
from src.ui.modal.settings_modal import SettingsModal
from src.ui.panel.generators.glid_panel import GlidPanel
from src.ui.window.main_window import MainWindow
from src.util.image_utils import qimage_to_pil_image, pil_image_to_qimage
from src.util.optional_import import optional_import, check_import
from src.util.shared_constants import EDIT_MODE_INPAINT, PROJECT_DIR
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
GLID_GENERATOR_NAME = _tr('GLID-3-XL image generation')
GLID_GENERATOR_DESCRIPTION = _tr('<h1>GLID-3-XL</h1>'
                                 '<p>GLID-3-XL was the best inpainting model available until August 2022, and the '
                                 'first model supported by IntraPaint. IntraPaint continues to support it for '
                                 'the sake of preserving historically interesting image generation models.'
                                 '<h2>Generator capabilities and limits:</h2>'
                                 '<ul>'
                                 '<li>Requires approximately 8GB of VRAM.</li>'
                                 '<li>Inpainting is supported at an ideal resolution of 256x256, with limited'
                                 ' support for other resolutions.</li>'
                                 '<li>Supports positive and negative prompting with variable guidance strength</li>'
                                 '<li>Capable of generating images in batches, with max batch size dependent on '
                                 'available VRAM.</li>'
                                 '<li>Some stylistic flexibility, but limited ability to understand complex prompts.'
                                 '</ul>')
GLID_PREVIEW_IMAGE = f'{PROJECT_DIR}/resources/generator_preview/glid-3-xl.png'
GLID_WEB_GENERATOR_SETUP = _tr('<h2>GLID-3-XL server setup</h2>'
                               '<p>NOTE: Because GLID-3-XL is mainly a historical curiosity at this point, few steps '
                               'have been taken to simplify the setup process. As the software involved becomes '
                               'increasingly outdated, further steps may be necessary to get this generator to work. '
                               'Currently, completing the following steps should allow IntraPaint to run GLID-3-XL:</p>'
                               '<ol>'
                               '<li>Make sure your computer has a NVIDIA GPU with at least 8GB of VRAM. Other GPUs'
                               'or slightly less memory may work, but are not tested.</li>'
                               '<li>If you are using the pre-built version of IntraPaint, you will need to switch to'
                               ' the Git version. Here\'s how you do that:</li>'
                               '<ol>'
                               '<li>Ensure that all of the following are installed:</li>'
                               '<ol><li><a href="https://www.python.org/">Python3</a></li>'
                               '<li><a href="https://git-scm.com/">Git</a></li>'
                               '<li><a href="https://developer.nvidia.com/cuda-toolkit">CUDA</a> (if using a NVIDIA'
                               ' graphics card)</li>'
                               '<li><a href="https://www.anaconda.com/download/">Anaconda</a></li></ol>'
                               '<li>Depending on your system, you may need to take extra steps to add Python, Git, '
                               'and Anaconda to your system path, or perform other configuration steps. Refer to the '
                               'sites linked above for full documentation.</li>'
                               '<li>In a terminal window, run <code>git clone https://github.com/centuryglass/'
                               'IntraPaint.git</code> to download the full IntraPaint repository, then change directory'
                               ' to the new IntraPaint folder that this creates.</li></ol>'
                               '<li>In a terminal window, run `<code>conda create -n intrapaint-glid</code>`, then '
                               '`<code>conda activate intrapaint-glid</code>` to prepare to install additional'
                               ' dependencies.</li>'       
                               '<li>Within the the terminal in the IntraPaint directory with the `intrapaint-glid`'
                               'environment active, install the appropriate versions of torch and torchvision found '
                               '<a href="https://pytorch.org/get-started/locally/">here</a>.'
                               '<li>Run `<code>conda install pip</code>` to make sure the environment has its own copy'
                               ' of the python package manager.</li>'
                               '<li>Run `<code>pip install -r requirements.txt</code>` to install primary IntraPaint'
                               ' requirements within the anaconda environment.</li>'
                               '<li>Run `<code>pip install -r requirements-glid.txt</code>` to install additional'
                               ' dependencies for GLID-3-XL.</li>'
                               '<li>Run the following Git commands to add two other required dependencies:<li><ol>'
                               '<li>`<code>git clone https://github.com/CompVis/taming-transformers.git</code>`</li>'
                               '<li>`<code>git clone https://github.com/CompVis/latent-diffusion.git</code>`</li>'
                               '<li>Download one or more GLID-3-XL inpainting models, and place them in the IntraPaint/'
                               'models/ directory. These are the main options available:<li><ol>'
                               '<li><a href="https://dall-3.com/models/glid-3-xl/">inpaint.pt</a>, the original GLID-3-'
                               'XL inpainting model</li>'
                               '<li><a href="https://huggingface.co/laion/ongo/resolve/main/ongo.pt>ongo.pt</a>, '
                               'trained by LAION on paintings from the Wikiart dataset</li>'
                               '<li><a href="https://huggingface.co/laion/erlich/resolve/main/model/ema_0.9999_120000'
                               '.pt">erlich.pt</a>, trained on the LAION large logo dataset</li>'
                               '</ol>'
                               '<li>Start IntraPaint by running `<code>python IntraPaint.py</code>`. If you are using a'
                               ' model other than the default inpaint.pt, instead run `<code>python'
                               ' Intrapaint_server.py  --model_path models/model.pt</code>`, replacing "model.pt" with'
                               ' the file name of whatever model you are using.</li>'
                               '<li>If all steps were performed correctly, you should be able to activate this '
                               'generator without any errors.</li>')

MISSING_DEPS_ERROR = _tr('Required dependencies are missing: <code>{dependency_list}</code>')
NOT_ENOUGH_VRAM_ERROR = _tr('Not enough VRAM for the GLID-3-XL generator: {mem_free} free memory found, expected at'
                            ' least {min_vram}')
MISSING_MODEL_ERROR = _tr('{model_name} model file expected at "{model_path}" is missing')

EXPECTED_MODULE_NAMES = ['torch', 'torchvision', 'pytorch-lightning', 'transformers', 'PyYAML', 'tqdm', 'scipy',
                         'regex', 'numpy', 'blobfile', 'einops', 'openai-clip', 'setuptools']
MISSING_REPO_ERROR = _tr('Missing required {repo_name} repository, please run `git clone {repo_url}` within the '
                         'IntraPaint directory.')
TAMING_TRANSFORMERS_REPO = 'https://github.com/CompVis/taming-transformers.git'
LATENT_DIFFUSION_REPO = 'https://github.com/CompVis/latent-diffusion.git'


GLID_MODEL = 'GLID-3-XL'
BERT_MODEL = 'BERT'
KL_MODEL = 'KL'


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
        self._preview = QImage(GLID_PREVIEW_IMAGE)

    def get_display_name(self) -> str:
        """Returns a display name identifying the generator."""
        return GLID_GENERATOR_NAME

    def get_description(self) -> str:
        """Returns an extended description of this generator."""
        return GLID_GENERATOR_DESCRIPTION

    def get_preview_image(self) -> QImage:
        """Returns a preview image for this generator."""
        return self._preview

    def get_setup_text(self) -> str:
        """Returns a rich text description of how to set up this generator."""
        return GLID_WEB_GENERATOR_SETUP

    def is_available(self) -> bool:
        """Returns whether the generator is supported on the current system."""
        for import_name, repo_name, repo_url in (('taming', 'taming-transformers', TAMING_TRANSFORMERS_REPO),
                                                 ('ldm', 'latent-diffusion', LATENT_DIFFUSION_REPO)):
            if not check_import(import_name):
                self.status_signal.emit(MISSING_REPO_ERROR.format(repo_name=repo_name, repo_url=repo_url))
                return False
        if None in (torch, get_device, foreach_image_in_sample, generate_samples, create_sample_function, load_models):
            missing_modules = ', '.join([module for module in EXPECTED_MODULE_NAMES if check_import(module) is False])
            self.status_signal.emit(MISSING_DEPS_ERROR.format(dependency_list=missing_modules))
            return False
        device = get_device()
        (mem_free, _) = torch.cuda.mem_get_info(device)
        if mem_free < MIN_GLID_VRAM:
            self.status_signal.emit(NOT_ENOUGH_VRAM_ERROR.format(mem_free=mem_free, min_vram=MIN_GLID_VRAM))
            return False
        for model_name, model_path in ((GLID_MODEL, self._model_path), (BERT_MODEL, self._bert_path),
                                       (KL_MODEL, self._kl_path)):
            if not os.path.exists(model_path):
                self.status_signal.emit(MISSING_MODEL_ERROR.format(model_name=model_name, model_path=model_path))
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
