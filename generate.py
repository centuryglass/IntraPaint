"""
Simplified script for glid-3-xl for image generation only, no inpainting functionality.
"""
import sys, gc
import torch
from startup.load_models import load_models
from startup.create_sample_function import create_sample_function
from startup.generate_samples import generate_samples
from startup.utils import build_arg_parser
from startup.ml_utils import get_device

# argument parsing:
parser = build_arg_parser(default_model='finetune.pt', include_edit_params=False)
args = parser.parse_args()

if args.model_path == 'inpaint.pt':
    print("Error: generate.py does not support inpainting. Use one of the following:")
    print("\tquickEdit.py:          To perform quick inpainting operations with a minimal UI.")
    print("\tinpainting_ui.py:      To use the inpainting UI, running both UI and generation on the same machine.")
    print("\tinpainting_server.py:  To run inpainting operations for a remote UI client")
    print("\tautoedit.py:           To run experimental automated random inpainting operations")
    sys.exit()

device = get_device(args.cpu)
if args.seed >= 0:
    torch.manual_seed(args.seed)

model_params, model, diffusion, ldm, bert, clip_model, clip_preprocess, normalize = load_models(device,
        model_path=args.model_path,
        bert_path=args.bert_path,
        kl_path=args.kl_path,
        steps = args.steps,
        clip_guidance = args.clip_guidance,
        cpu = args.cpu,
        ddpm = args.ddpm,
        ddim = args.ddim)


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
        batch_size=args.batch_size,
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
        get_save_fn(args.prefix, args.batch_size, ldm, clip_model, clip_preprocess, device),
        args.batch_size,
        args.num_batches,
        width=args.width,
        height=args.height,
        init_image=args.init_image,
        clip_score_fn=clip_score_fn if args.clip_score else None)
