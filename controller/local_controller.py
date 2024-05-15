"""
Provides image editing functionality through a local instance of GLID-3-XL.
"""
import gc
from PIL import Image
import torch

from PyQt5.QtCore import QSize

from startup.load_models import load_models
from startup.create_sample_function import create_sample_function
from startup.generate_samples import generate_samples
from startup.ml_utils import get_device, foreach_image_in_sample
from controller.base_controller import BaseInpaintController
from data_model.config import Config

class LocalDeviceController(BaseInpaintController):
    """Provides image editing functionality through a local instance of GLID-3-XL."""

    def __init__(self, args):
        super().__init__(args)
        self._device = get_device(args.cpu)
        print('Using device:', self._device)
        if args.seed >= 0:
            torch.manual_seed(args.seed)
        self._clip_guidance = args.clip_guidance
        self._ddim = args.ddim
        self._ddpm = args.ddpm

        self._model_params, self._model, self._diffusion, self._ldm, self._bert, self._clip_model, \
            self._clip_preprocess, self._normalize = load_models(
                self._device,
                model_path=args.model_path,
                bert_path=args.bert_path,
                kl_path=args.kl_path,
                steps = args.steps,
                clip_guidance = args.clip_guidance,
                cpu = args.cpu,
                ddpm = args.ddpm,
                ddim = args.ddim)


    def _inpaint(self, selection, mask, save_image, status_signal):
        gc.collect()
        if not isinstance(selection, Image.Image):
            raise TypeError(f'Expected PIL Image selection, got {selection}')
        if not isinstance(mask, Image.Image):
            raise TypeError(f'Expected PIL Image mask, got {mask}')
        if selection.width != mask.width:
            raise RuntimeError(f'Selection and mask widths should match, found {selection.width} and {mask.width}')
        if selection.height != mask.height:
            raise RuntimeError(f'Selection and mask widths should match, found {selection.width} and {mask.width}')

        batch_size = self._config.get(Config.BATCH_SIZE)
        batch_count = self._config.get(Config.BATCH_COUNT)
        sample_fn, clip_score_fn = create_sample_function(
                self._device,
                self._model,
                self._model_params,
                self._bert,
                self._clip_model,
                self._clip_preprocess,
                self._ldm,
                self._diffusion,
                self._normalize,
                image=None, # Inpainting uses edit instead of this param
                mask=mask,
                prompt=self._config.get(Config.PROMPT),
                negative=self._config.get(Config.NEGATIVE_PROMPT),
                guidance_scale=self._config.get(Config.GUIDANCE_SCALE),
                batch_size=batch_size,
                edit=selection,
                width=selection.width,
                height=selection.height,
                edit_width=selection.width,
                edit_height=selection.height,
                cutn=self._config.get(Config.CUTN),
                clip_guidance=self._clip_guidance,
                skip_timesteps=self._config.get(Config.SKIP_STEPS),
                ddpm=self._ddpm,
                ddim=self._ddim)
        def save_sample(i, sample, unused_clip_score=False):
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

    def refresh_settings(self, settings_modal):
        """Settings not in scope for GLID-3-XL controller."""

    def update_settings(self, changed_settings):
        """Settings not in scope for GLID-3-XL controller."""
