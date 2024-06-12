"""
Simplified script for glid-3-xl for image generation only, no inpainting functionality.
"""
import sys
import gc
import torch
from src.glid_3_xl.load_models import load_models
from src.glid_3_xl.create_sample_function import create_sample_function
from src.glid_3_xl.generate_samples import generate_samples
from src.glid_3_xl.ml_utils import get_device, get_save_fn
from src.util.arg_parser import build_arg_parser

# argument parsing:
parser = build_arg_parser(default_model='glid_3_xl/models/finetune.pt', include_edit_params=False)
args = parser.parse_args()

if args.model_path in ('glid_3_xl/models/inpaint.pt', 'glid_3_xl/models/ongo.pt'):
    print('Error: generate.py does not support inpainting. Use one of the following:')
    print('\tIntraPaint.py:          To use the inpainting UI, running both UI and generation on the same machine.')
    print('\ttIntraPaint_server.py:  To run inpainting operations for a remote UI client')
    print('\tglid_quickEdit.py:      To perform quick inpainting operations with a minimal UI.')
    sys.exit()

device = get_device(args.cpu)
if args.seed >= 0:
    torch.manual_seed(args.seed)
model_data = load_models(device, model_path=args.model_path, bert_path=args.bert_path, kl_path=args.kl_path,
                         steps=args.steps, clip_guidance=args.clip_guidance, cpu=args.cpu, ddpm=args.ddpm,
                         ddim=args.ddim)
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
    prompt=args.text,
    negative=args.negative,
    image=args.init_image,
    guidance_scale=args.guidance_scale,
    batch_size=batch_size,
    width=args.width,
    height=args.height,
    cutn=args.cutn,
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
                 init_image=args.init_image,
                 clip_score_fn=clip_score_fn if args.clip_score else None)
