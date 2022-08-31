# Simplified script for single glid-3-xl inpainting operations.
import argparse
import sys
import sys
import gc
import os

from PIL import Image
import torch
from torchvision.transforms import functional as TF
import numpy as np

from startup.load_models import loadModels
from startup.create_sample_function import createSampleFunction
from startup.generate_samples import generateSamples
from startup.utils import *
from startup.ml_utils import *

# argument parsing:
parser = buildArgParser(includeGenParams=False)
args = parser.parse_args()

if not args.mask:
    from edit_ui.quickedit_window import getDrawnMask
    args.mask = getDrawnMask(args.width, args.height, args.edit)

device = getDevice(args.cpu)
if args.seed >= 0:
    torch.manual_seed(args.seed)

model_params, model, diffusion, ldm, bert, clip_model, clip_preprocess, normalize = loadModels(device,
        model_path=args.model_path,
        bert_path=args.bert_path,
        kl_path=args.kl_path,
        steps = args.steps,
        clip_guidance = args.clip_guidance,
        cpu = args.cpu,
        ddpm = args.ddpm,
        ddim = args.ddim)

sample_fn, clip_score_fn = createSampleFunction(
        device,
        model,
        model_params,
        bert,
        clip_model,
        clip_preprocess,
        ldm,
        diffusion,
        normalize,
        edit=args.edit,
        mask=args.mask,
        prompt=args.text,
        negative=args.negative,
        guidance_scale=args.guidance_scale,
        batch_size=args.batch_size,
        width=args.width,
        height=args.height,
        cutn=args.cutn,
        edit_width=args.edit_width,
        edit_height=args.edit_height,
        edit_x=args.edit_x,
        edit_y=args.edit_y,
        clip_guidance=args.clip_guidance,
        clip_guidance_scale=args.clip_guidance_scale,
        skip_timesteps=args.skip_timesteps,
        ddpm=args.ddpm,
        ddim=args.ddim)

gc.collect()
generateSamples(device,
        ldm,
        diffusion,
        sample_fn,
        getSaveFn(args.prefix, args.batch_size, ldm, clip_model, clip_preprocess, device),
        args.batch_size,
        args.num_batches,
        width=args.width,
        height=args.height,
        clip_score_fn=clip_score_fn if args.clip_score else None)
