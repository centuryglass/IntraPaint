"""Geometry of the inpainting mask blur band, shared by everything that needs to know how wide it is.

Both Stable Diffusion backends blur the mask after the inpaint crop is scaled to `Cache.GENERATION_SIZE`, and treat
`AppConfig.MASK_BLUR` as a Gaussian standard deviation. The band's real extent is about 2.5 standard deviations, and in
image pixels it scales with the crop: `extent * crop_size / generation_size`, per axis. Soft paste, inpaint crop growth
and the canvas outline all take their widths from here, so they cannot disagree.
"""
import math

from PIL import Image, ImageFilter
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from src.util.visual.pil_image_utils import pil_image_to_qimage, qimage_to_pil_image

# Distance, in standard deviations, past which a blurred hard edge is effectively gone.
BLUR_EXTENT_SIGMAS = 2.5


def blur_extent(mask_blur: float) -> int:
    """Returns the band's reach on each side of the selection edge, in generation-size pixels."""
    if mask_blur <= 0:
        return 0
    return math.ceil(BLUR_EXTENT_SIGMAS * mask_blur)


def _axis_scale(crop_length: int, generation_length: int) -> float:
    return crop_length / generation_length if generation_length > 0 else 1.0


def blur_extent_in_image(mask_blur: float, crop_size: QSize, generation_size: QSize) -> tuple[int, int]:
    """Returns the band's (horizontal, vertical) reach in image pixels for an inpaint crop of crop_size."""
    extent = blur_extent(mask_blur)
    return (math.ceil(extent * _axis_scale(crop_size.width(), generation_size.width())),
            math.ceil(extent * _axis_scale(crop_size.height(), generation_size.height())))


def soft_paste_mask(mask: QImage, crop_bounds_size: QSize, generation_size: QSize, mask_blur: float) -> QImage:
    """Returns mask with the backend's blur applied, at mask's size.

    The mask is blurred at generation resolution, as the backends do, so the transition covers the same pixels the
    backend blended. The mask's alpha channel is the selection, and the result keeps that convention.

    Parameters
    ----------
    mask : QImage
        Selection mask for the whole generation area, selected pixels opaque.
    crop_bounds_size : QSize
        Size of the area the backend sees, in the mask's pixels. Equals the mask size unless inpaint full-res crops it.
    generation_size : QSize
        `Cache.GENERATION_SIZE`.
    mask_blur : float
        `AppConfig.MASK_BLUR`, a Gaussian standard deviation at generation resolution.
    """
    if mask_blur <= 0 or mask.isNull():
        return mask
    # Scale by the same factors the crop gets, so sigma in image pixels is mask_blur * crop / generation.
    alpha = qimage_to_pil_image(mask).convert('RGBA').getchannel('A')
    sigma_x, sigma_y = (mask_blur * _axis_scale(crop_bounds_size.width(), generation_size.width()),
                        mask_blur * _axis_scale(crop_bounds_size.height(), generation_size.height()))
    blurred = _anisotropic_blur(alpha, sigma_x, sigma_y)
    soft = Image.new('RGBA', blurred.size, (0, 0, 0, 0))
    soft.putalpha(blurred)
    return pil_image_to_qimage(soft)


def _anisotropic_blur(alpha: Image.Image, sigma_x: float, sigma_y: float) -> Image.Image:
    """Gaussian-blurs an 'L' image with separate standard deviations per axis."""
    width, height = alpha.size
    if width == 0 or height == 0:
        return alpha
    # Pillow's blur is isotropic. Shrink each axis by smallest_sigma / axis_sigma so one sigma applies, blur, then
    # restore the size.
    if math.isclose(sigma_x, sigma_y, rel_tol=1e-3):
        return alpha.filter(ImageFilter.GaussianBlur(sigma_x))
    sigma = min(sigma_x, sigma_y)
    squashed = alpha.resize((max(1, round(width * sigma / sigma_x)), max(1, round(height * sigma / sigma_y))),
                            Image.Resampling.BILINEAR)
    return squashed.filter(ImageFilter.GaussianBlur(sigma)).resize((width, height), Image.Resampling.BILINEAR)
