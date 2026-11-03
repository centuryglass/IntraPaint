"""Turns a generated inpainting result into a patch: a color and an alpha that reproduce the result when drawn
Normal over the image that was sent to the backend.

The backends return the result already blended into the sent image C through a blurred mask, so writing it into a
layer copies C, which may be the flattened composite of every layer, into that layer. A patch keeps only what the
result changed.
"""
from typing import Optional

import numpy as np
from PySide6.QtGui import QImage

from src.util.visual.image_utils import image_data_as_numpy_8bit


def _alpha_channel(image: Optional[QImage], size) -> np.ndarray:
    """Returns the image's alpha as floats in 0-1, or all ones if there is no image."""
    if image is None or image.size() != size:
        return np.ones((size.height(), size.width()), dtype=np.float32)
    converted = image.convertToFormat(QImage.Format.Format_ARGB32)
    return image_data_as_numpy_8bit(converted)[:, :, 3].astype(np.float32) / 255.0


def make_result_patch(result: QImage, sent: QImage, blend_estimate: Optional[QImage] = None,
                      source_alpha: Optional[QImage] = None) -> QImage:
    """Returns an ARGB32_Premultiplied patch that gives `result` when drawn Normal over `sent`.

    `result` and `sent` must be the same size, and `sent` must be opaque. For each pixel the patch alpha is the larger
    of two values:
    - The minimum alpha for which a valid color reproduces the result, as in color-to-alpha. This term makes the
      patch exact whatever the other inputs are.
    - `blend_estimate` alpha times `source_alpha`, so wherever the source was opaque the patch stays close to the
      backend's own blend. Each is skipped when None. Where the source was transparent the term is zero, and alpha is
      only what the result changed.

    Raises ValueError if the sizes differ.
    """
    if result.size() != sent.size():
        raise ValueError(f'result size {result.size()} does not match sent size {sent.size()}')
    size = result.size()
    result_px = image_data_as_numpy_8bit(result.convertToFormat(QImage.Format.Format_ARGB32))
    sent_px = image_data_as_numpy_8bit(sent.convertToFormat(QImage.Format.Format_ARGB32))
    result_rgb = result_px[:, :, :3].astype(np.float32) / 255.0
    sent_rgb = sent_px[:, :, :3].astype(np.float32) / 255.0
    diff = result_rgb - sent_rgb
    with np.errstate(divide='ignore', invalid='ignore'):
        needed = np.where(diff > 0, diff / (1.0 - sent_rgb), -diff / sent_rgb)
    needed = np.nan_to_num(needed, nan=0.0, posinf=1.0)
    alpha = np.minimum(needed.max(axis=2), 1.0)
    if blend_estimate is not None:
        estimate = _alpha_channel(blend_estimate, size) * _alpha_channel(source_alpha, size)
        alpha = np.maximum(alpha, estimate)
    # Rounding up in 8 bits keeps the alpha at or above the minimum:
    alpha8 = np.ceil(alpha * 255.0 - 1e-4).clip(0, 255)
    alpha = alpha8 / 255.0
    safe_alpha = np.where(alpha > 0, alpha, 1.0)[:, :, np.newaxis]
    color = np.where(alpha[:, :, np.newaxis] > 0, sent_rgb + diff / safe_alpha, result_rgb)
    patch = np.empty((size.height(), size.width(), 4), dtype=np.uint8)
    patch[:, :, :3] = np.rint(color.clip(0.0, 1.0) * 255.0)
    patch[:, :, 3] = alpha8
    straight = QImage(patch.data, size.width(), size.height(), QImage.Format.Format_ARGB32).copy()
    return straight.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
