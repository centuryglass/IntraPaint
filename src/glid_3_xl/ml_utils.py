"""
Miscellaneous utility functions for handling torch-related functionality
"""
import os
# noinspection PyPackageRequirements
import torch
# noinspection PyPep8Naming,PyPackageRequirements
from torchvision.transforms import functional as TF
import numpy as np


def get_device(use_cpu=False):
    """Initializes the Torch device."""
    if use_cpu or (not torch.cuda.is_available()):
        print('Warning: CPU mode is not supported, image generation will almost certainly fail.')
        return torch.device('cpu')
    return torch.device('cuda:0')


def image_from_numpy_data(numpy_data, ldm_model):
    """Extracts a PIL image from numpy image data"""
    image_data = numpy_data / 0.18215
    image_data = image_data.unsqueeze(0)
    numpy_data = ldm_model.decode(image_data)
    return TF.to_pil_image(numpy_data.squeeze(0).add(1).div(2).clamp(0, 1))


def foreach_in_sample(sample, batch_size, action):
    """Runs a function for each numpy image data object in a sample"""
    for k, image_data in enumerate(sample['pred_xstart'][:batch_size]):
        action(k, image_data)


def foreach_image_in_sample(sample, batch_size, ldm_model, action):
    """Runs a function for each PIL image extracted from a sample"""
    def _convert_param(k, numpy_data):
        action(k, image_from_numpy_data(numpy_data, ldm_model))
    foreach_in_sample(sample, batch_size, _convert_param)


# noinspection PyUnusedLocal
def get_save_fn(prefix, batch_size, ldm_model, unused_clip_model, unused_clip_preprocess, unused_device):
    """Creates and returns a function that saves sample data to disk."""
    def _save_sample(i, sample, clip_score_fn=None):
        def _save_image(k, numpy_data):
            npy_filename = f'output_npy/{prefix}{i * batch_size + k:05}.npy'
            with open(npy_filename, 'wb') as outfile:
                np.save(outfile, numpy_data.detach().cpu().numpy())
            pil_image = image_from_numpy_data(numpy_data, ldm_model)
            filename = f'output/{prefix}{i * batch_size + k:05}.png'
            pil_image.save(filename)
            if clip_score_fn:
                score = clip_score_fn(pil_image)
                final_filename = f'output/{prefix}_{score:0.3f}_{i * batch_size + k:05}.png'
                os.rename(filename, final_filename)
                npy_final = f'output_npy/{prefix}_{score:0.3f}_{i * batch_size + k:05}.npy'
                os.rename(npy_filename, npy_final)
        foreach_in_sample(sample, batch_size, _save_image)
    return _save_sample
