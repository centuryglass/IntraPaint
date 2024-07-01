"""
Provides image editing functionality through a local instance of GLID-3-XL.
"""
import logging
from argparse import Namespace
from typing import Callable, List

import torch
from PIL import Image
from PyQt5.QtCore import pyqtSignal, QSize

from src.config.application_config import AppConfig
from src.controller.base_controller import BaseInpaintController
from src.glid_3_xl.create_sample_function import create_sample_function
from src.glid_3_xl.generate_samples import generate_samples
from src.glid_3_xl.load_models import load_models
from src.glid_3_xl.ml_utils import get_device, foreach_image_in_sample
from src.ui.modal.settings_modal import SettingsModal
from src.util.validation import assert_types

GLID_CONFIG_CATEGORY = 'GLID-3-XL'

logger = logging.getLogger(__name__)


class LocalDeviceController(BaseInpaintController):
    """Provides image editing functionality through a local instance of GLID-3-XL."""

    def __init__(self, args: Namespace):
        super().__init__(args)
        self._device = get_device(args.cpu)
        logger.info('Using device: %s', self._device)
        if args.seed >= 0:
            torch.manual_seed(args.seed)
        self._clip_guidance = args.clip_guidance
        self._ddim = args.ddim
        self._ddpm = args.ddpm
        config = AppConfig.instance()
        generate_size = config.get(AppConfig.GENERATION_SIZE)
        if generate_size.width() > 256 or generate_size.height() > 256:
            config.set(AppConfig.GENERATION_SIZE, QSize(256, 256))

        self._model_params, self._model, self._diffusion, self._ldm, self._bert, self._clip_model, \
            self._clip_preprocess, self._normalize = load_models(self._device,
                                                                 model_path=args.model_path,
                                                                 bert_path=args.bert_path,
                                                                 kl_path=args.kl_path,
                                                                 steps=args.steps,
                                                                 clip_guidance=args.clip_guidance,
                                                                 cpu=args.cpu,
                                                                 ddpm=args.ddpm,
                                                                 ddim=args.ddim)

    def get_config_categories(self) -> List[str]:
        """Return the list of AppConfig categories this controller supports."""
        categories = super().get_config_categories()
        categories.append(GLID_CONFIG_CATEGORY)
        return categories

    def _inpaint(self,
                 source_image_section: Image.Image,
                 mask: Image.Image,
                 save_image: Callable[[Image.Image, int], None],
                 status_signal: pyqtSignal) -> None:
        assert_types((source_image_section, mask), Image.Image)
        config = AppConfig.instance()
        if source_image_section.width != mask.width:
            raise RuntimeError(f'Selection and mask widths should match, found {source_image_section.width} and {mask.width}')
        if source_image_section.height != mask.height:
            raise RuntimeError(f'Selection and mask heights should match, found {source_image_section.height} and {mask.height}')
        if source_image_section.mode == 'RGBA':
            source_image_section = source_image_section.convert('RGB')
        print(f'gen size: {source_image_section.width}x{source_image_section.height}')

        batch_size = config.get(AppConfig.BATCH_SIZE)
        batch_count = config.get(AppConfig.BATCH_COUNT)
        sample_fn, unused_clip_score_fn = create_sample_function(
            self._device,
            self._model,
            self._model_params,
            self._bert,
            self._clip_model,
            self._clip_preprocess,
            self._ldm,
            self._diffusion,
            self._normalize,
            image=None,  # Inpainting uses edit instead of this param
            mask=mask,
            prompt=config.get(AppConfig.PROMPT),
            negative=config.get(AppConfig.NEGATIVE_PROMPT),
            guidance_scale=config.get(AppConfig.GUIDANCE_SCALE),
            batch_size=batch_size,
            edit=source_image_section,
            width=source_image_section.width,
            height=source_image_section.height,
            edit_width=source_image_section.width,
            edit_height=source_image_section.height,
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
                lambda k, img: save_image(img, (i * batch_size) + k))

        generate_samples(
            self._device,
            self._ldm,
            self._diffusion,
            sample_fn,
            save_sample,
            batch_size,
            batch_count,
            source_image_section.width,
            source_image_section.height)

    def refresh_settings(self, settings_modal: SettingsModal) -> None:
        """Settings not in scope for GLID-3-XL controller."""

    def update_settings(self, changed_settings: dict) -> None:
        """Settings not in scope for GLID-3-XL controller."""
