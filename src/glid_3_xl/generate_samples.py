"""
Provides an image inpainting function using a local GLID-3-XL instance.
"""
import torch
from torchvision.transforms import functional as TF
from PIL import Image


def generate_samples(
        device,
        ldm_model,
        diffusion,
        sample_fn,
        save_sample,
        batch_size,
        num_batches,
        width=256,
        height=256,
        init_image=None,
        clip_score_fn=None):
    """Given a sample generation function and a sample save function, start generating image samples."""
    if init_image:
        init = Image.open(init_image).convert('RGB')
        init = init.resize((int(width), int(height)), Image.LANCZOS)
        init = TF.to_tensor(init).to(device).unsqueeze(0).clamp(0, 1)
        h = ldm_model.encode(init * 2 - 1).sample() * 0.18215
        init = torch.cat(batch_size * 2 * [h], dim=0)
    else:
        init = None
    for i in range(num_batches):
        samples = sample_fn(init)
        if samples is not None:
            sample = None
            for j, sample in enumerate(samples):
                if j % 5 == 0 and j != diffusion.num_timesteps - 1:
                    save_sample(i, sample)
            if sample is not None:
                save_sample(i, sample, clip_score_fn)
