"""Handles flood fill and color fill algorithms using perceptual color spaces."""
from typing import Optional, TypeAlias, Any

import cython
from cython.cimports.cython.view import array as cvarray
from cython.cimports.libc.math import sqrt
import numpy as np
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage, QColor

from src.util.visual.image_utils import image_data_as_numpy_8bit, create_transparent_image

@cython.nogil
@cython.cfunc
@cython.boundscheck(False)
@cython.wraparound(False)
def calculate_color_distance(l1: cython.float,
                             a1: cython.float,
                             b1: cython.float,
                             alpha1: cython.uint,
                             r: cython.uint,
                             g: cython.uint,
                             b: cython.uint,
                             alpha2: cython.uint) -> float:
    """
    Calculate perceptual color distance using LAB colorspace, with one color preconverted.
    Alpha is handled separately to maintain edge detection.


    Parameters
    ----------
        l1: cython.float
            Pre-converted LAB color lightness component.
        a1: cython.float
            Pre-converted LAB color red-green axis component.
        b1: cython.float
            Pre-converted LAB color blue-yellow axis component.
        alpha1: cython.uint
            Pre-converted LAB color alpha component (0 - 255)
        r: cython.uint
            BGRA color red component (0 - 255).
        g: cython.uint
            BGRA color green component (0 - 255).
        b: cython.uint
            BGRA color blue component (0 - 255).
        alpha2: cython.uint
            BGRA color alpha component (0 - 255).
    Returns
    -------
        distance: float
            A float value used to represent the distance between colors.  Range is between 0 and 300 in theory.  In
            practice, I haven't found any pairs within RGB colorspace with distance>278, and more precise calculation
            of extremes will likely take longer than it's worth.
    """
    lab2 = cython.declare(cython.float[3])
    lab2_ptr = cython.cast(cython.pointer[cython.float], cython.address(lab2))
    rgb_to_lab(r, g, b, lab2_ptr)
    # Calculate LAB color difference (deltaE)
    d_l = l1 - lab2[0]
    d_a = a1 - lab2[1]
    d_b = b1 - lab2[2]

    # Calculate alpha difference separately (normalized to similar scale as LAB)
    d_alpha = (float(alpha1) - float(alpha2)) / 2.55  # Scale from [0,255] to [0,100]
    # Combine LAB difference with alpha difference
    # Weight factors can be adjusted if needed
    return sqrt(d_l * d_l + d_a * d_a + d_b * d_b + d_alpha * d_alpha)


@cython.nogil
@cython.cfunc
@cython.inline
@cython.boundscheck(False)
@cython.wraparound(False)
def rgb_to_lab(r: cython.uint, g: cython.uint, b: cython.uint,
               out: cython.pointer[cython.float]) -> cython.int:
    """
    Convert RGB to LAB colorspace.

    Parameters
    ----------
    r: cython.uint
        Red color component (range [0, 255]).
    g: cython.uint
        Green color component (range [0, 255]).
    b: cython.uint
        Blue color component (range [0, 255]).

    out:
        Size 3 floating point array where LAB components will be assigned
        lightness: float
            Lightness LAB component (range [0, 100]).
        a: float
            a* color axis LAB component (unbound).
        b: float
            b* color axis LAB component (unbound).
    """
    # Convert to XYZ
    r_f: cython.float = r / 255.0
    g_f: cython.float = g / 255.0
    b_f: cython.float = b / 255.0

    # Linearize sRGB values
    r_f = ((r_f + 0.055) / 1.055) ** 2.4 if r_f > 0.04045 else r_f / 12.92
    g_f = ((g_f + 0.055) / 1.055) ** 2.4 if g_f > 0.04045 else g_f / 12.92
    b_f = ((b_f + 0.055) / 1.055) ** 2.4 if b_f > 0.04045 else b_f / 12.92

    # Convert to XYZ using D65 illuminant
    x: cython.float = (r_f * 0.4124 + g_f * 0.3576 + b_f * 0.1805) * 100
    y: cython.float = (r_f * 0.2126 + g_f * 0.7152 + b_f * 0.0722) * 100
    z: cython.float = (r_f * 0.0193 + g_f * 0.1192 + b_f * 0.9505) * 100

    # Convert XYZ to LAB
    # D65 reference white
    xn: cython.float = 95.047
    yn: cython.float = 100.0
    zn: cython.float = 108.883

    x = x / xn
    y = y / yn
    z = z / zn

    x = x ** (1 / 3) if x > 0.008856 else (7.787 * x) + (16 / 116)
    y = y ** (1 / 3) if y > 0.008856 else (7.787 * y) + (16 / 116)
    z = z ** (1 / 3) if z > 0.008856 else (7.787 * z) + (16 / 116)

    out[0] = (116 * y) - 16
    out[1] = 500 * (x - y)
    out[2] = 200 * (y - z)
    return 0

@cython.cfunc
@cython.boundscheck(False)
@cython.wraparound(False)
def make_lab_mask(pixels: cython.uchar[:],
                  width: cython.long,
                  height: cython.long,
                  target_l: cython.float,
                  target_a: cython.float,
                  target_b: cython.float,
                  target_alpha: cython.int,
                  threshold: float) -> np.ndarray:
    """
    Creates a boolean mask marking each pixel in an image within a certain distance of a LAB color value.

    Parameters
    ----------
        pixels: cython.uchar[:]
            A 1-dimensional array of ARGB32 (b, g, r, a) image pixel values, range 0-255
        width: cython.long
            Width of the pixels parameter array
        height: cython.long
            Height of the pixels parameter array
        target_l: cython.float
            Target LAB color L-component.
        target_a: cython.float
            Target LAB color A-component.
        target_b: cython.float
            Target LAB color B-component.
        target_alpha: cython.uint
            Target LAB color alpha-component.
        threshold: float
            Maximum distance allowed between an image pixel and target_lab_color in order for it to be flagged.
    Returns
    -------
        mask: np.ndarray
            A 1-dimensional array of 0/1 int flags indicating if pixels are within the threshold.
    """
    mask = np.zeros(width * height, dtype=np.uint8)
    mask_view = cython.declare(cython.uchar[:], mask)
    with cython.nogil:
        i: cython.longlong
        for i in range(width * height):
            px_index: cython.long = i * 4
            b: cython.uint = pixels[px_index]
            g: cython.uint = pixels[px_index + 1]
            r: cython.uint = pixels[px_index + 2]
            a: cython.uint = pixels[px_index + 3]
            dist = calculate_color_distance(target_l, target_a, target_b, target_alpha, r, g, b, a)
            if dist <= threshold:
                mask_view[i] = 1
    return mask

@cython.cfunc
@cython.boundscheck(False)
@cython.wraparound(False)
def fast_flood_fill(image: cython.uchar[:, :, :], width: cython.long, height: cython.long,
                    seed_x: cython.long, seed_y: cython.long, threshold: cython.float):
    """
    Perform flood fill operation using a numba-optimized approach.

     Parameters
    ----------
        image: cython.uchar[:, :, :]
            A 2-dimensional array of ARGB32 (b, g, r, a) image pixel values, range 0-255
        width: cython.long
            image width
        height: cython.long
            image height
        seed_x: cython.long
            x coordinate where the flood fill operation should start.
        seed_y: cython.long
            y coordinate where the flood fill operation should start.
        threshold: float
            Maximum distance allowed between an image pixel and the seed pixel in order for it to be filled.
    Returns
    -------
        mask: np.ndarray
            A uint8 boolean mask of filled pixels.
    """
    mask = np.zeros((height, width), dtype=np.uint8)
    mask_view = cython.declare(cython.uchar[:, :], mask)

    # Early exit if seed point is out of bounds
    if not (0 <= seed_x < width and 0 <= seed_y < height):
        return mask

    seed_color = image[seed_y, seed_x]
    r: cython.uint = image[seed_y, seed_x, 2]
    g: cython.uint = image[seed_y, seed_x, 1]
    b: cython.uint = image[seed_y, seed_x, 0]

    lab = cython.declare(cython.float[3])
    lab_ptr = cython.cast(cython.pointer[cython.float], cython.address(lab))
    rgb_to_lab(r, g, b, lab_ptr)
    lab_l: cython.float = lab[0]
    lab_a: cython.float = lab[1]
    lab_b: cython.float = lab[2]
    alpha: cython.uint = seed_color[3]

    # Using a standard 4-connected flood fill to avoid horizontal artifacts
    max_stack_size: cython.longlong = width * height  # Safety limit
    stack = np.zeros((max_stack_size, 2), dtype=np.long)
    stack_view = cython.declare(cython.long[:, :], stack)
    stack_view[0][0], stack_view[0][1] = seed_y, seed_x
    stack_size: cython.longlong = 1
    r_last: cython.uint = r
    g_last: cython.uint = g
    b_last: cython.uint = b
    a_last: cython.uint = alpha
    with cython.nogil:
        while 0 < stack_size <= max_stack_size:
            y: cython.long = stack_view[stack_size - 1][0]
            x: cython.long = stack_view[stack_size - 1][1]
            stack_size -= 1

            if mask_view[y, x]:  # Skip if already filled
                continue
            r_curr: cython.uint = image[y, x, 2]
            g_curr: cython.uint = image[y, x, 1]
            b_curr: cython.uint = image[y, x, 0]
            a_curr: cython.uint = image[y, x, 3]
            if (r_last == r_curr and g_last == g_curr and b_last == b_curr and a_last == a_curr) \
                    or calculate_color_distance(lab_l, lab_a, lab_b, alpha, r_curr, g_curr, b_curr, a_curr) <= threshold:
                mask_view[y, x] = True
                r_last, g_last, b_last, a_last = r_curr, g_curr, b_curr, a_curr

                # Check 4-connected neighbors
                i: cython.int
                for i in range(4):
                    dy: cython.int = 0 if i < 2 else i * 2 - 5 # 0, 0, -1, 1
                    dx: cython.int = 0 if i > 1 else i * 2 - 1 # -1, 1, 0, 0
                    new_y: cython.long = y + dy
                    new_x: cython.long = x + dx
                    if (0 <= new_x < width and 0 <= new_y < height and
                            not mask_view[new_y, new_x]) and stack_size < max_stack_size:
                        stack_view[stack_size][0], stack_view[stack_size][1] = new_y, new_x
                        stack_size += 1
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
    image_view: cython.uchar[:, :, :] = cython.declare(cython.uchar[:, :, :], np_image)

    # Get filled mask using our fast implementation
    filled_mask = fast_flood_fill(image_view, image.width(), image.height(), pos.x(), pos.y(), threshold)

    if not in_place:
        # Create new mask image
        result = QImage(image.width(), image.height(), QImage.Format.Format_ARGB32)
        result.fill(Qt.GlobalColor.transparent)
        mask_data = image_data_as_numpy_8bit(result)

        # Set color for filled pixels
        mask_data[filled_mask.astype(bool)] = [0, 0, 0, 255]

        return result
    else:
        # Modify original image directly
        src_np_image = image_data_as_numpy_8bit(image)
        if image.format() == QImage.Format.Format_ARGB32_Premultiplied:
            alpha_mult = color.alpha() / 255.0
        else:
            alpha_mult = 1.0
        src_np_image[filled_mask.astype(bool)] = [
            color.blue() * alpha_mult,
            color.green() * alpha_mult,
            color.red() * alpha_mult,
            color.alpha()
        ]
        return None


def color_fill(image: QImage, color: QColor, threshold: float) -> QImage:
    """Return an image mask marking all pixels where the color value matches a given color within a threshold range."""
    un_multiplied_image = image.convertToFormat(QImage.Format.Format_ARGB32)

    lab = cython.declare(cython.float[3])
    lab_ptr = cython.cast(cython.pointer[cython.float], cython.address(lab))
    rgb_to_lab(color.red(), color.green(), color.blue(), lab_ptr)
    l: cython.float = lab[0]
    a: cython.float = lab[1]
    b: cython.float = lab[2]

    pixels = cython.declare(cython.uchar[:], un_multiplied_image.bits())
    mask_flat = make_lab_mask(pixels, image.width(), image.height(), l, a, b, color.alpha(), threshold)
    mask = mask_flat.reshape((image.height(), image.width()))

    mask_image = create_transparent_image(image.size())
    np_mask_image = image_data_as_numpy_8bit(mask_image)
    np_mask_image[mask.astype(bool), 3] = 255
    return mask_image
