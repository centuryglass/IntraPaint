"""
Loads the ML models that make up GLID-3-XL.
"""
import gc
import torch
from torchvision import transforms
import clip
from src.glid_3_xl.guided_diffusion.script_util import create_model_and_diffusion, model_and_diffusion_defaults
from encoders.modules import BERTEmbedder


# noinspection SpellCheckingInspection
def load_models(device,
                model_path='inpaint.pt',
                bert_path='bert.pt',
                kl_path='kl-f8.pt',
                clip_model_name='ViT-L/14',
                steps=None,
                clip_guidance=False,
                cpu=False,
                ddpm=False,
                ddim=False):
    """Loads all ML models and associated variables."""

    model_state_dict = torch.load(model_path, map_location='cpu')

    model_params = {
        'attention_resolutions': '32,16,8',
        'class_cond': False,
        'diffusion_steps': 1000,
        'rescale_timesteps': True,
        'timestep_respacing': '27',  # Modify this value to decrease the number of
        # timesteps.
        'image_size': 32,
        'learn_sigma': False,
        'noise_schedule': 'linear',
        'num_channels': 320,
        'num_heads': 8,
        'num_res_blocks': 2,
        'resblock_updown': False,
        'use_fp16': False,
        'use_scale_shift_norm': False,
        'clip_embed_dim': 768 if 'clip_proj.weight' in model_state_dict else None,
        'image_condition': bool(model_state_dict['input_blocks.0.0.weight'].shape[1] == 8),
        'super_res_condition': bool('external_block.0.0.weight' in model_state_dict)
    }

    if ddpm:
        model_params['timestep_respacing'] = 1000
    if ddim:
        if steps:
            model_params['timestep_respacing'] = 'ddim' + str(steps)
        else:
            model_params['timestep_respacing'] = 'ddim50'
    elif steps:
        model_params['timestep_respacing'] = str(steps)

    model_config = model_and_diffusion_defaults()
    model_config.update(model_params)

    if cpu:
        model_config['use_fp16'] = False

    # Load models
    model, diffusion = create_model_and_diffusion(**model_config)
    model.load_state_dict(model_state_dict, strict=False)
    model.requires_grad_(clip_guidance).eval().to(device)

    if model_config['use_fp16']:
        model.convert_to_fp16()
    else:
        model.convert_to_fp32()

    def set_requires_grad(model, value):
        for param in model.parameters():
            param.requires_grad = value

    print(f'loaded and configured primary model from {model_path}')
    gc.collect()

    # vae
    ldm = torch.load(kl_path, map_location='cpu')
    ldm.to(device)
    ldm.eval()
    ldm.requires_grad_(clip_guidance)
    set_requires_grad(ldm, clip_guidance)
    print(f'loaded and configured latent diffusion model from {kl_path}')
    gc.collect()

    bert = BERTEmbedder(1280, 32)
    sd = torch.load(bert_path, map_location='cpu')
    bert.load_state_dict(sd)
    bert.to(device)
    bert.half().eval()
    set_requires_grad(bert, False)
    print(f'loaded and configured BERT model from {bert_path}')
    gc.collect()

    # clip
    clip_model, clip_preprocess = clip.load(clip_model_name, device=device, jit=False)
    clip_model.eval().requires_grad_(False)
    print(f'loaded and configured CLIP model from {clip_model_name}')
    gc.collect()

    normalize = transforms.Normalize(mean=[0.48145466, 0.4578275, 0.40821073],
                                     std=[0.26862954, 0.26130258, 0.27577711])
    return model_params, model, diffusion, ldm, bert, clip_model, clip_preprocess, normalize
