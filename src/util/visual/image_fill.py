"""Handles flood fill and color fill algorithms using perceptual color spaces."""
from typing import Optional

import numpy as np
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage, QColor
try:
    from numba import njit
except ImportError:
    from src.util.numba_placeholder import njit

from src.util.visual.image_utils import NpAnyArray, image_data_as_numpy_8bit, create_transparent_image


@njit
def rgb_to_lab(r: int, g: int, b: int) -> tuple[float, float, float]:
    """
    Convert RGB to LAB colorspace.

    Parameters
    ----------
    r: int
        Red color component (range [0, 255]).
    g: int
        Green color component (range [0, 255]).
    b: int
        Blue color component (range [0, 255]).

    Returns
    -------
        lightness: float
            Lightness LAB component (range [0, 100]).
        a: float
            a* color axis LAB component (unbound).
        b: float
            b* color axis LAB component (unbound).
    """
    # Convert to XYZ
    r_f = r / 255.0
    g_f = g / 255.0
    b_f = b / 255.0

    # Linearize sRGB values
    r_f = ((r_f + 0.055) / 1.055) ** 2.4 if r_f > 0.04045 else r_f / 12.92
    g_f = ((g_f + 0.055) / 1.055) ** 2.4 if g_f > 0.04045 else g_f / 12.92
    b_f = ((b_f + 0.055) / 1.055) ** 2.4 if b_f > 0.04045 else b_f / 12.92

    # Convert to XYZ using D65 illuminant
    x = (r_f * 0.4124 + g_f * 0.3576 + b_f * 0.1805) * 100
    y = (r_f * 0.2126 + g_f * 0.7152 + b_f * 0.0722) * 100
    z = (r_f * 0.0193 + g_f * 0.1192 + b_f * 0.9505) * 100

    # Convert XYZ to LAB
    # D65 reference white
    xn, yn, zn = 95.047, 100.0, 108.883

    x = x / xn
    y = y / yn
    z = z / zn

    x = x ** (1 / 3) if x > 0.008856 else (7.787 * x) + (16 / 116)
    y = y ** (1 / 3) if y > 0.008856 else (7.787 * y) + (16 / 116)
    z = z ** (1 / 3) if z > 0.008856 else (7.787 * z) + (16 / 116)

    l_component = (116 * y) - 16
    a_component = 500 * (x - y)
    b_component = 200 * (y - z)

    return float(l_component), float(a_component), float(b_component)


@njit
def calculate_color_distance(lab_plus_alpha_color: tuple[float, float, float, int],
                             bgra_color: tuple[int, int, int, int] | NpAnyArray) -> float:
    """
    Calculate perceptual color distance using LAB colorspace, with one color preconverted.
    Alpha is handled separately to maintain edge detection.


    Parameters
    ----------
        lab_plus_alpha_color: tuple[float, float, float, int]
            Pre-converted LAB color, as a tuple of  L A B float components plus an int alpha component.
        bgra_color: tuple[int, int, int, int]
            Second color, as a tuple of BGRA int components (range [0, 255]).
    Returns
    -------
        distance: float
            A float value used to represent the distance between colors.  Range is between 0 and 300 in theory.  In
            practice, I haven't found any pairs within RGB colorspace with distance>278, and more precise calculation
            of extremes will likely take longer than it's worth.
    """
    l1, a1, b1, alpha1 = lab_plus_alpha_color
    b, g, r, alpha2 = bgra_color
    l2, a2, b2 = rgb_to_lab(r, g, b)

    # Calculate LAB color difference (deltaE)
    d_l = l1 - l2
    d_a = a1 - a2
    d_b = b1 - b2

    # Calculate alpha difference separately (normalized to similar scale as LAB)
    d_alpha = (float(alpha1) - float(alpha2)) / 2.55  # Scale from [0,255] to [0,100]
    # Combine LAB difference with alpha difference
    # Weight factors can be adjusted if needed
    return np.sqrt(d_l * d_l + d_a * d_a + d_b * d_b + d_alpha * d_alpha)


@njit
def make_lab_mask(pixels: np.ndarray, target_lab_color: tuple[float, float, float, int],
                  threshold: float) -> np.ndarray:
    """
    Creates a boolean mask marking each pixel in an image within a certain distance of a LAB color value.

    Parameters
    ----------
        pixels: np.ndarray
            A 1-dimensional array of ARGB32 (b, g, r, a) image pixel values, range 0-255
        target_lab_color: tuple[float, float, float, int]
            The target color to match, pre-converted to LAB format, with alpha appended at the final index.
        threshold: float
            Maximum distance allowed between an image pixel and target_lab_color in order for it to be flagged.
    Returns
    -------
        mask: np.ndarray
            A 1-dimensional array of 0/1 int flags indicating if pixels are within the threshold.
    """
    mask = np.zeros(pixels.shape[0], dtype=np.float64)
    for i in range(pixels.shape[0]):
        dist = calculate_color_distance(target_lab_color, pixels[i])
        if dist <= threshold:
            mask[i] = 1
    return mask


@njit
def fast_flood_fill(image: NpAnyArray, seed_x: int, seed_y: int, threshold: float):
    """
    Perform flood fill operation using a numba-optimized approach.

     Parameters
    ----------
        image: np.ndarray
            A 2-dimensional array of ARGB32 (b, g, r, a) image pixel values, range 0-255
        seed_x: int
            x coordinate where the flood fill operation should start.
        seed_y: int
            y coordinate where the flood fill operation should start.
        threshold: float
            Maximum distance allowed between an image pixel and the seed pixel in order for it to be filled.
    Returns
    -------
        mask: np.ndarray
            A boolean mask of filled pixels.
    """
    height, width = image.shape[:2]
    mask = np.zeros((height, width), dtype=np.bool_)

    # Early exit if seed point is out of bounds
    if not (0 <= seed_x < width and 0 <= seed_y < height):
        return mask

    seed_color = image[seed_y, seed_x]
    l, a, b = rgb_to_lab(int(seed_color[2]), int(seed_color[1]), int(seed_color[0]))
    lab_seed_color = (l, a, b, int(seed_color[3]))

    # Using a standard 4-connected flood fill to avoid horizontal artifacts
    stack = [(seed_y, seed_x)]
    max_stack_size = width * height  # Safety limit
    while stack and len(stack) < max_stack_size:
        y, x = stack.pop()

        if mask[y, x]:  # Skip if already filled
            continue
        if calculate_color_distance(lab_seed_color, image[y, x]) <= threshold:
            mask[y, x] = True

            # Check 4-connected neighbors
            for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                new_y, new_x = y + dy, x + dx
                if (0 <= new_x < width and 0 <= new_y < height and
                        not mask[new_y, new_x]):
                    stack.append((new_y, new_x))
    return mask


def flood_fill(image: QImage, pos: QPoint, color: QColor, threshold: float, in_place: bool = False) -> Optional[QImage]:
    """Returns a mask image marking all areas of similar color directly connected to a point in an image.

    Parameters
    ----------
        image: QImage
            Source image, in format Format_ARGB32_Premultiplied.
        pos: QPoint
            Seed point for the fill operation.
        color: QColor
            Color used to draw filled pixels in the final mask image.
        threshold: float
            Maximum color difference to ignore when determining which pixels to fill.
        in_place: bool, default=False
            If True, modify the image in-place and do not return a mask.
    Returns
    -------
        mask: Optional[QImage]
            Mask image marking the area to be filled, returned only if in_place=False. The mask image will be the same
            size as the source image. filled pixels will be set to black, while unfilled pixels will be
            fully transparent.
    """
    # Convert image to proper format and get numpy array
    un_multiplied_image = image.convertToFormat(QImage.Format.Format_ARGB32)
    np_image = image_data_as_numpy_8bit(un_multiplied_image)

    # Get filled mask using our fast implementation
    filled_mask = fast_flood_fill(np_image, pos.x(), pos.y(), threshold)

    if not in_place:
        # Create new mask image
        result = QImage(image.width(), image.height(), QImage.Format.Format_ARGB32)
        result.fill(Qt.GlobalColor.transparent)
        mask_data = image_data_as_numpy_8bit(result)

        # Set color for filled pixels
        mask_data[filled_mask] = [0, 0, 0, 255]

        return result
    else:
        # Modify original image directly
        src_np_image = image_data_as_numpy_8bit(image)
        if image.format() == QImage.Format.Format_ARGB32_Premultiplied:
            alpha_mult = color.alpha() / 255.0
        else:
            alpha_mult = 1.0
        src_np_image[filled_mask] = [
            color.blue() * alpha_mult,
            color.green() * alpha_mult,
            color.red() * alpha_mult,
            color.alpha()
        ]
        return None


def color_fill(image: QImage, color: QColor, threshold: float) -> QImage:
    """Return an image mask marking all pixels where the color value matches a given color within a threshold range."""
    un_multiplied_image = image.convertToFormat(QImage.Format.Format_ARGB32)
    np_image = image_data_as_numpy_8bit(un_multiplied_image)
    l, a, b = rgb_to_lab(color.red(), color.green(), color.blue())
    lab_color_with_alpha = (l, a, b, color.alpha())

    pixels = np_image.reshape((-1, 4))
    mask_flat = make_lab_mask(pixels, lab_color_with_alpha, threshold)
    mask = mask_flat.reshape((image.height(), image.width()))

    mask_image = create_transparent_image(image.size())
    np_mask_image = image_data_as_numpy_8bit(mask_image)
    np_mask_image[mask.astype(bool), 3] = 255
    return mask_image
