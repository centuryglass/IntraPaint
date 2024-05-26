"""
Provides functions used to start up a local GLID-3-XL instance.
"""
import io

import requests
import torch
import clip
import numpy as np
from PIL import Image, ImageOps
from torchvision import transforms
from torchvision.transforms import functional as TF
from torch.nn import functional as F
from encoders.modules import MakeCutouts


def create_sample_function(
        device,
        model,
        model_params,
        bert_model,
        clip_model,
        clip_preprocess,
        ldm_model,
        diffusion,
        normalize,
        image=None,
        mask=None,
        prompt='',
        negative='',
        guidance_scale=5.0,
        batch_size=1,
        width=256,
        height=256,
        cutn=16,
        edit=None,
        edit_width=None,
        edit_height=None,
        edit_x=0,
        edit_y=0,
        clip_guidance=False,
        clip_guidance_scale=None,
        skip_timesteps=False,
        ddpm=False,
        ddim=False):
    """
    Creates a function that will generate a set of sample images, along with an accompanying clip ranking function.
    """
    # bert context
    text_emb = bert_model.encode([prompt] * batch_size).to(device).float()
    text_blank = bert_model.encode([negative] * batch_size).to(device).float()

    text = clip.tokenize([prompt] * batch_size, truncate=True).to(device)
    text_clip_blank = clip.tokenize([negative] * batch_size, truncate=True).to(device)

    # clip context
    text_emb_clip = clip_model.encode_text(text)
    text_emb_clip_blank = clip_model.encode_text(text_clip_blank)
    if clip_guidance and not clip_guidance_scale:
        clip_guidance_scale = 150

    make_cutouts = MakeCutouts(clip_model.visual.input_resolution, cutn)

    text_emb_norm = text_emb_clip[0] / text_emb_clip[0].norm(dim=-1, keepdim=True)

    image_embed = None

    # image context
    if edit:
        input_image = torch.zeros(1, 4, height // 8, width // 8, device=device)
        input_image_pil = None
        np_image = None
        if isinstance(edit, Image.Image):
            input_image = torch.zeros(1, 4, height // 8, width // 8, device=device)
            input_image_pil = edit
        elif isinstance(edit, str) and edit.endswith('.npy'):
            with open(edit, 'rb') as f:
                np_image = np.load(f)
                np_image = torch.from_numpy(np_image).unsqueeze(0).to(device)
                input_image = torch.zeros(1, 4, height // 8, width // 8, device=device)
        elif isinstance(edit, str):
            w = edit_width if edit_width else width
            h = edit_height if edit_height else height
            input_image_pil = Image.open(fetch(edit)).convert('RGB')
            input_image_pil = ImageOps.fit(input_image_pil, (w, h))
        if input_image_pil is not None:
            np_image = transforms.ToTensor()(input_image_pil).unsqueeze(0).to(device)
            np_image = 2 * np_image - 1
            np_image = ldm_model.encode(np_image).sample()

        y = edit_y // 8
        x = edit_x // 8
        y_crop = y + np_image.shape[2] - input_image.shape[2]
        x_crop = x + np_image.shape[3] - input_image.shape[3]

        y_crop = y_crop if y_crop > 0 else 0
        x_crop = x_crop if x_crop > 0 else 0

        input_image[
        0,
        :,
        y if y >= 0 else 0:y + np_image.shape[2],
        x if x >= 0 else 0:x + np_image.shape[3]
        ] = np_image[
            :,
            :,
            0 if y > 0 else -y:np_image.shape[2] - y_crop,
            0 if x > 0 else -x:np_image.shape[3] - x_crop
            ]
        input_image_pil = ldm_model.decode(input_image)
        input_image_pil = TF.to_pil_image(input_image_pil.squeeze(0).add(1).div(2).clamp(0, 1))
        input_image *= 0.18215

        if isinstance(mask, Image.Image):
            mask_image = mask.convert('L').point(lambda p: 255 if p < 1 else 0)
            mask_image.save('mask.png')
            mask_image = mask_image.resize((width // 8, height // 8), Image.LANCZOS)
            mask = transforms.ToTensor()(mask_image).unsqueeze(0).to(device)
        elif isinstance(edit, str):
            mask_image = Image.open(fetch(mask)).convert('L')
            mask_image = mask_image.resize((width // 8, height // 8), Image.LANCZOS)
            mask = transforms.ToTensor()(mask_image).unsqueeze(0).to(device)
        else:
            raise ValueError(f'Expected PIL image or image path for mask, found {mask}')
        mask1 = mask > 0.5
        mask1 = mask1.float()
        input_image *= mask1

        image_embed = torch.cat(batch_size * 2 * [input_image], dim=0).float()
    elif model_params['image_condition']:
        # using inpaint model but no image is provided
        image_embed = torch.zeros(batch_size * 2, 4, height // 8, width // 8, device=device)

    model_kwargs = {
        'context': torch.cat([text_emb, text_blank], dim=0).float(),
        'clip_embed': torch.cat([text_emb_clip, text_emb_clip_blank], dim=0).float()
        if model_params['clip_embed_dim'] else None,
        'image_embed': image_embed
    }

    # noinspection SpellCheckingInspection
    def model_fn(x_t, ts, **kwargs):
        """Create a classifier-free guidance sampling function"""
        half = x_t[: len(x_t) // 2]
        combined = torch.cat([half, half], dim=0)
        model_out = model(combined, ts, **kwargs)
        eps, rest = model_out[:, :3], model_out[:, 3:]
        cond_eps, uncond_eps = torch.split(eps, len(eps) // 2, dim=0)
        half_eps = uncond_eps + guidance_scale * (cond_eps - uncond_eps)
        eps = torch.cat([half_eps, half_eps], dim=0)
        return torch.cat([eps, rest], dim=1)

    def cond_fn(x, unused_t, context=None, clip_embed=None, image_embed=None):
        with torch.enable_grad():
            cur_t = diffusion.num_timesteps - 1
            x = x[:batch_size].detach().requires_grad_()

            n = x.shape[0]

            my_t = torch.ones([n], device=device, dtype=torch.long) * cur_t

            kw = {
                'context': context[:batch_size],
                'clip_embed': clip_embed[:batch_size] if model_params['clip_embed_dim'] else None,
                'image_embed': image_embed[:batch_size] if image_embed is not None else None
            }

            out = diffusion.p_mean_variance(model, x, my_t, clip_denoised=False, model_kwargs=kw)

            fac = diffusion.sqrt_one_minus_alphas_cumprod[cur_t]
            x_in = out['pred_xstart'] * fac + x * (1 - fac)

            x_in /= 0.18215

            x_img = ldm_model.decode(x_in)

            clip_in = normalize(make_cutouts(x_img.add(1).div(2)))
            clip_embeds = clip_model.encode_image(clip_in).float()

            def spherical_dist_loss(x, y):
                x = F.normalize(x, dim=-1)
                y = F.normalize(y, dim=-1)
                return (x - y).norm(dim=-1).div(2).arcsin().pow(2).mul(2)

            dists = spherical_dist_loss(clip_embeds.unsqueeze(1), text_emb_clip.unsqueeze(0))
            dists = dists.view([cutn, n, -1])

            losses = dists.sum(2).mean(0)

            loss = losses.sum() * clip_guidance_scale

            return -torch.autograd.grad(loss, x)[0]

    if ddpm:
        base_sample_fn = diffusion.ddpm_sample_loop_progressive
    elif ddim:
        base_sample_fn = diffusion.ddim_sample_loop_progressive
    else:
        base_sample_fn = diffusion.plms_sample_loop_progressive

    def sample_fn(init):
        return base_sample_fn(
            model_fn,
            (batch_size * 2, 4, int(height / 8), int(width / 8)),
            clip_denoised=False,
            model_kwargs=model_kwargs,
            cond_fn=cond_fn if clip_guidance else None,
            device=device,
            progress=True,
            init_image=init,
            skip_timesteps=skip_timesteps
        )

    def clip_score_fn(image):
        """Provides a CLIP score ranking image closeness to text"""
        image_emb = clip_model.encode_image(clip_preprocess(image).unsqueeze(0).to(device))
        image_emb_norm = image_emb / image_emb.norm(dim=-1, keepdim=True)
        similarity = torch.nn.functional.cosine_similarity(image_emb_norm, text_emb_norm, dim=-1)
        return similarity.item()

    return sample_fn, clip_score_fn


def fetch(url_or_path, timeout=180):
    """Open a file from either a path or a URL."""
    if str(url_or_path).startswith('http://') or str(url_or_path).startswith('https://'):
        r = requests.get(url_or_path, timeout=timeout)
        r.raise_for_status()
        fd = io.BytesIO()
        fd.write(r.content)
        fd.seek(0)
        return fd
    return open(url_or_path, 'rb')
