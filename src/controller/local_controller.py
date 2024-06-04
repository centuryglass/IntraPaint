"""
Provides image editing functionality through a local instance of GLID-3-XL.
"""
import gc
from argparse import Namespace
from typing import Callable
import logging
from PIL import Image
import torch
from PyQt5.QtCore import pyqtSignal, QSize
from src.glid_3_xl.load_models import load_models
from src.glid_3_xl.create_sample_function import create_sample_function
from src.glid_3_xl.generate_samples import generate_samples
from src.glid_3_xl.ml_utils import get_device, foreach_image_in_sample
from src.controller.base_controller import BaseInpaintController
from src.config.application_config import AppConfig
from src.ui.modal.settings_modal import SettingsModal
from src.util.validation import assert_types

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
        generate_size = self._config.get(AppConfig.GENERATION_SIZE)
        if generate_size.width() > 256 or generate_size.height() > 256:
            self._config.set(AppConfig.GENERATION_SIZE, QSize(256, 256))

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

    def _inpaint(self,
                 selection: Image.Image,
                 mask: Image.Image,
                 save_image: Callable[[Image.Image, int], None],
                 status_signal: pyqtSignal) -> None:
        gc.collect()
        assert_types((selection, mask), Image.Image)
        if selection.width != mask.width:
            raise RuntimeError(f'Selection and mask widths should match, found {selection.width} and {mask.width}')
        if selection.height != mask.height:
            raise RuntimeError(f'Selection and mask heights should match, found {selection.height} and {mask.height}')
        if selection.mode == 'RGBA':
            selection = selection.convert('RGB')
        print(f'gen size: {selection.width}x{selection.height}')

        batch_size = self._config.get(AppConfig.BATCH_SIZE)
        batch_count = self._config.get(AppConfig.BATCH_COUNT)
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
            prompt=self._config.get(AppConfig.PROMPT),
            negative=self._config.get(AppConfig.NEGATIVE_PROMPT),
            guidance_scale=self._config.get(AppConfig.GUIDANCE_SCALE),
            batch_size=batch_size,
            edit=selection,
            width=selection.width,
            height=selection.height,
            edit_width=selection.width,
            edit_height=selection.height,
            cutn=self._config.get(AppConfig.CUTN),
            clip_guidance=self._clip_guidance,
            skip_timesteps=self._config.get(AppConfig.SKIP_STEPS),
            ddpm=self._ddpm,
            ddim=self._ddim)

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
            selection.width,
            selection.height)

    def refresh_settings(self, settings_modal: SettingsModal) -> None:
        """Settings not in scope for GLID-3-XL controller."""

    def update_settings(self, changed_settings: dict) -> None:
        """Settings not in scope for GLID-3-XL controller."""
