"""Geometry of the inpainting mask blur band, shared by everything that needs to know how wide it is.

Both Stable Diffusion backends blur the mask at generation resolution and treat `AppConfig.MASK_BLUR` as a Gaussian
standard deviation. The band's real extent is about 2.5 standard deviations, and in image pixels it scales with the
area the backend blurred: `extent * blurred_size / generation_resolution`, per axis. Inpaint crop growth and the
paste clip take their widths from here, so they cannot disagree.
"""
import math

import cv2
import numpy as np
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from src.util.visual.image_utils import image_data_as_numpy_8bit

# Distance, in standard deviations, past which a blurred hard edge is effectively gone.
BLUR_EXTENT_SIGMAS = 2.5


def blur_extent(mask_blur: float) -> int:
    """Returns the band's reach on each side of the selection edge, in generation-size pixels."""
    if mask_blur <= 0:
        return 0
    return math.ceil(BLUR_EXTENT_SIGMAS * mask_blur)


def _axis_scale(crop_length: int, generation_length: int) -> float:
    return crop_length / generation_length if generation_length > 0 else 1.0


def blur_extent_in_image(mask_blur: float, crop_size: QSize, generation_resolution: QSize) -> tuple[int, int]:
    """Returns the band's (horizontal, vertical) reach in image pixels when the backend blurs an area of crop_size
    scaled to generation_resolution."""
    extent = blur_extent(mask_blur)
    return (math.ceil(extent * _axis_scale(crop_size.width(), generation_resolution.width())),
            math.ceil(extent * _axis_scale(crop_size.height(), generation_resolution.height())))


def grow_mask(mask: QImage, reach_x: int, reach_y: int) -> QImage:
    """Returns a copy of mask with its selected area grown by reach_x and reach_y pixels, as ARGB32_Premultiplied.

    Selected pixels are the ones with nonzero alpha. Grown pixels are opaque, so the result stays a hard mask.
    """
    grown = mask.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    if reach_x <= 0 and reach_y <= 0 or grown.isNull():
        return grown
    pixels = image_data_as_numpy_8bit(grown)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * max(reach_x, 0) + 1, 2 * max(reach_y, 0) + 1))
    added = (cv2.dilate(np.ascontiguousarray(pixels[:, :, 3]), kernel) > 0) & (pixels[:, :, 3] == 0)
    pixels[added] = (0, 0, 0, 255)
    return grown


def shrink_mask(mask: QImage, reach: int) -> QImage:
    """Returns a copy of mask with its selected area shrunk by reach pixels, as ARGB32_Premultiplied.

    Selected pixels are the ones with nonzero alpha. Returns the unshrunk mask if shrinking would leave nothing
    selected, so a selection narrower than the blur band is still inpainted.
    """
    shrunk = mask.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    if reach <= 0 or shrunk.isNull():
        return shrunk
    pixels = image_data_as_numpy_8bit(shrunk)
    alpha = np.ascontiguousarray(pixels[:, :, 3])
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * reach + 1, 2 * reach + 1))
    # Pixels outside the image count as unselected, so a selection touching the edge shrinks away from it too:
    eroded = cv2.erode((alpha > 0).astype(np.uint8), kernel, borderType=cv2.BORDER_CONSTANT, borderValue=0)
    if not eroded.any():
        return shrunk
    pixels[:, :, :] = 0
    pixels[eroded > 0] = (0, 0, 0, 255)
    return shrunk


def blurred_mask_estimate(mask: QImage, mask_blur: float) -> QImage:
    """Returns the mask's alpha blurred by a Gaussian of `mask_blur` standard deviations, as ARGB32_Premultiplied.

    This approximates the blend weight the backends blur the mask into. The estimate is only a floor for result
    patches, so the real blur differing from it changes how much of the source a patch removes, not its result.
    """
    estimate = mask.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    if mask_blur <= 0 or estimate.isNull():
        return estimate
    pixels = image_data_as_numpy_8bit(estimate)
    blurred = cv2.GaussianBlur(np.ascontiguousarray(pixels[:, :, 3]), (0, 0), mask_blur)
    pixels[:, :, :] = 0
    pixels[:, :, 3] = blurred
    return estimate
