"""Utility functions for ComfyUI workflow builders."""
import random

from src.api.comfyui.comfyui_types import ImageFileReference

random.seed()


MAX_SEED = 0xffffffffffffffff


def random_seed() -> int:
    """Gets a random seed within the expected range valid seeds accepted by ComfyUI."""
    return random.randrange(0, MAX_SEED)


def image_ref_to_str(image_ref: ImageFileReference) -> str:
    """Converts an uploaded image/mask file reference to an API-compatible string representation."""
    if 'subfolder' in image_ref and image_ref['subfolder'] != '':
        return f'{image_ref["subfolder"]}/{image_ref["filename"]}'
    return image_ref['filename']
