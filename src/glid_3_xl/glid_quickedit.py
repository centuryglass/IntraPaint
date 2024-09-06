"""
Simplified script for single glid-3-xl inpainting operations.
"""
import gc
# noinspection PyPackageRequirements
import torch

from src.glid_3_xl.load_models import load_models
from src.glid_3_xl.create_sample_function import create_sample_function
from src.glid_3_xl.generate_samples import generate_samples
from src.util.arg_parser import build_arg_parser
from src.glid_3_xl.ml_utils import get_device, get_save_fn

# argument parsing:
parser = build_arg_parser(include_gen_params=False)
args = parser.parse_args()

if not args.mask:
    from src.ui.window.quickedit_window import get_drawn_mask

    args.mask = get_drawn_mask(args.edit)

device = get_device(args.cpu)
if args.seed >= 0:
    torch.manual_seed(args.seed)

model_data = load_models(device, model_path=args.model_path, bert_path=args.bert_path, kl_path=args.kl_path,
                         clip_model_name=args.clip_model, steps=args.steps, clip_guidance=args.clip_guidance,
                         cpu=args.cpu, ddpm=args.ddpm,  ddim=args.ddim)
model_params, model, diffusion, ldm, bert, clip_model, clip_preprocess, normalize = model_data
batch_size, batch_count = (param if param is not None else 1 for param in (args.batch_size, args.num_batches))
sample_fn, clip_score_fn = create_sample_function(
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
    batch_size=batch_size,
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
generate_samples(device,
                 ldm,
                 diffusion,
                 sample_fn,
                 get_save_fn(args.prefix, batch_size, ldm, clip_model, clip_preprocess, device),
                 batch_size,
                 batch_count,
                 width=args.width,
                 height=args.height,
                 clip_score_fn=clip_score_fn if args.clip_score else None)
