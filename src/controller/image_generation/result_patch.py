"""Turns a generated inpainting result into a patch that holds only what the result changed.

A patch is a color and an alpha that reproduce the result when drawn Normal over the image that was sent to the backend.

The backends return the result already blended into the sent image C through a blurred mask, so writing it into a
layer copies C, which may be the flattened composite of every layer, into that layer. A patch keeps only what the
result changed. When the backend reports its unblended output and blend mask (`ResultLayers`), the patch is built from
those. Otherwise it is recovered from the blended result.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from src.util.visual.image_utils import image_data_as_numpy_8bit, ARGB32_ALPHA, ARGB32_COLOR


@dataclass(frozen=True)
class ResultLayers:
    """A backend's unblended output for one inpainting result, and the mask it blended that output through.

    Both are the size of the result. `compositing_mask` alpha is the weight of `uncomposited`, so drawing
    `uncomposited` through it over the sent image gives the result.
    """
    uncomposited: QImage
    compositing_mask: QImage


def _alpha_channel(image: Optional[QImage], size: QSize) -> np.ndarray:
    """Returns the image's alpha as floats in 0-1, or all ones if there is no image."""
    if image is None or image.size() != size:
        return np.ones((size.height(), size.width()), dtype=np.float32)
    converted = image.convertToFormat(QImage.Format.Format_ARGB32)
    return image_data_as_numpy_8bit(converted)[:, :, ARGB32_ALPHA].astype(np.float32) / 255.0


def _color_channels(image: QImage) -> np.ndarray:
    """Returns the image's straight-alpha color as floats in 0-1."""
    return image_data_as_numpy_8bit(image.convertToFormat(QImage.Format.Format_ARGB32))[:, :, ARGB32_COLOR] \
        .astype(np.float32) / 255.0


def _patch(result_rgb: np.ndarray, sent_rgb: np.ndarray, alpha_floor: Optional[np.ndarray]) -> QImage:
    """Returns the patch with the smallest alpha at or above `alpha_floor` that gives `result_rgb` over `sent_rgb`."""
    height, width = result_rgb.shape[:2]
    diff = result_rgb - sent_rgb
    with np.errstate(divide='ignore', invalid='ignore'):
        needed = np.where(diff > 0, diff / (1.0 - sent_rgb), -diff / sent_rgb)
    needed = np.nan_to_num(needed, nan=0.0, posinf=1.0)
    alpha = np.minimum(needed.max(axis=2), 1.0)
    if alpha_floor is not None:
        alpha = np.maximum(alpha, alpha_floor)
    # Rounding up in 8 bits keeps the alpha at or above the minimum:
    alpha8 = np.ceil(alpha * 255.0 - 1e-4).clip(0, 255)
    alpha = alpha8 / 255.0
    safe_alpha = np.where(alpha > 0, alpha, 1.0)[:, :, np.newaxis]
    color = np.where(alpha[:, :, np.newaxis] > 0, sent_rgb + diff / safe_alpha, result_rgb)
    patch = np.empty((height, width, 4), dtype=np.uint8)
    patch[:, :, ARGB32_COLOR] = np.rint(color.clip(0.0, 1.0) * 255.0)
    patch[:, :, ARGB32_ALPHA] = alpha8
    straight = QImage(patch.data, width, height, QImage.Format.Format_ARGB32).copy()
    return straight.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)


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
    floor = None
    if blend_estimate is not None:
        floor = _alpha_channel(blend_estimate, size) * _alpha_channel(source_alpha, size)
    return _patch(_color_channels(result), _color_channels(sent), floor)


def make_exact_result_patch(layers: ResultLayers, sent: QImage, source_alpha: Optional[QImage] = None) -> QImage:
    """Returns an ARGB32_Premultiplied patch built from the backend's unblended output and blend mask.

    The patch gives `sent` blended with `layers.uncomposited` through `layers.compositing_mask` when drawn Normal over
    `sent`, which must be opaque. Its alpha is the mask alpha times `source_alpha` (all ones when None), raised where
    needed to keep the result exact, as in `make_result_patch`. Wherever the source was opaque, the patch is
    `layers.uncomposited` at the mask's alpha.

    Raises ValueError if any of the three images differ in size.
    """
    size = sent.size()
    for name, image in (('uncomposited', layers.uncomposited), ('compositing mask', layers.compositing_mask)):
        if image.size() != size:
            raise ValueError(f'{name} size {image.size()} does not match sent size {size}')
    sent_rgb = _color_channels(sent)
    mask = _alpha_channel(layers.compositing_mask, size)
    blended = sent_rgb + mask[:, :, np.newaxis] * (_color_channels(layers.uncomposited) - sent_rgb)
    return _patch(blended, sent_rgb, mask * _alpha_channel(source_alpha, size))
