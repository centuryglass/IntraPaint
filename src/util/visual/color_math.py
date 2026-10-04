"""Color space conversions between sRGB, linear sRGB, OKLab, OKLCH and OKHSV.

Pure numpy functions with no Qt dependency, used by the color picker. Every function takes an array whose last axis
holds the three channels, so a single color and a whole rendered plane share one code path. Inputs may be any array
shape (..., 3), or a plain 3-tuple; outputs are float64 arrays of the same shape.

Channel ranges:
- sRGB and linear sRGB: 0.0-1.0 per channel inside the sRGB gamut. Conversions out of OKLab and OKLCH do not clip, so
  out-of-gamut colors come back with channels outside that range (see `is_in_srgb_gamut`).
- OKLab: L in 0.0-1.0, a and b roughly -0.4-0.4.
- OKLCH: L in 0.0-1.0, chroma 0.0 and up, hue in degrees, 0.0-360.0.
- OKHSV: hue in degrees, 0.0-360.0; saturation and value in 0.0-1.0. Every OKHSV triple in range maps into the sRGB
  gamut (see `okhsv_to_srgb`), which is why the picker's square uses it.

The OKLab matrices and the OKHSV functions are ported from Bjorn Ottosson's `ok_color.h`
(https://bottosson.github.io/posts/colorpicker/), distributed under the MIT license:

    Copyright (c) 2021 Bjorn Ottosson

    Permission is hereby granted, free of charge, to any person obtaining a copy of
    this software and associated documentation files (the "Software"), to deal in
    the Software without restriction, including without limitation the rights to
    use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
    of the Software, and to permit persons to whom the Software is furnished to do
    so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
"""
from typing import Any

import numpy as np
from numpy.typing import NDArray

ColorArray = NDArray[np.float64]

# Chroma at or below this is treated as gray: its hue is undefined and reported as 0.
ACHROMATIC_CHROMA = 1e-7

# OKHSV's fixed saturation constant (S_0 in ok_color.h).
_OKHSV_S0 = 0.5

# Constants for the OKHSV lightness "toe" curve.
_TOE_K1 = 0.206
_TOE_K2 = 0.03
_TOE_K3 = (1.0 + _TOE_K1) / (1.0 + _TOE_K2)

# Refinement steps in _max_saturation. ok_color.h uses one, which leaves channels up to 0.004 below zero near the blue
# cusp.
_HALLEY_STEPS = 2

_LINEAR_SRGB_TO_LMS = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                                [0.2119034982, 0.6806995451, 0.1073969566],
                                [0.0883024619, 0.2817188376, 0.6299787005]])
_LMS_CBRT_TO_OKLAB = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                               [1.9779984951, -2.4285922050, 0.4505937099],
                               [0.0259040371, 0.7827717662, -0.8086757660]])
_OKLAB_TO_LMS_CBRT = np.array([[1.0, 0.3963377774, 0.2158037573],
                               [1.0, -0.1055613458, -0.0638541728],
                               [1.0, -0.0894841775, -1.2914855480]])
_LMS_TO_LINEAR_SRGB = np.array([[4.0767416621, -3.3077115913, 0.2309699292],
                                [-1.2684380046, 2.6097574011, -0.3413193965],
                                [-0.0041960863, -0.7034186147, 1.7076147010]])


def _as_color_array(color: Any) -> ColorArray:
    array = np.asarray(color, dtype=np.float64)
    if array.shape[-1:] != (3,):
        raise ValueError(f'Expected a color array with 3 channels on its last axis, got shape {array.shape}')
    return array


def _channels(color: ColorArray) -> tuple[ColorArray, ColorArray, ColorArray]:
    return color[..., 0], color[..., 1], color[..., 2]


def srgb_to_linear(rgb: Any) -> ColorArray:
    """Removes the sRGB transfer curve. Negative values mirror the curve, so out-of-gamut colors round-trip."""
    rgb = _as_color_array(rgb)
    magnitude = np.abs(rgb)
    linear = np.where(magnitude >= 0.04045, ((magnitude + 0.055) / 1.055) ** 2.4, magnitude / 12.92)
    return np.copysign(linear, rgb)


def linear_to_srgb(linear: Any) -> ColorArray:
    """Applies the sRGB transfer curve. Negative values mirror the curve, so out-of-gamut colors round-trip."""
    linear = _as_color_array(linear)
    magnitude = np.abs(linear)
    rgb = np.where(magnitude >= 0.0031308, 1.055 * magnitude ** (1.0 / 2.4) - 0.055, magnitude * 12.92)
    return np.copysign(rgb, linear)


def linear_srgb_to_oklab(linear: Any) -> ColorArray:
    """Converts linear sRGB to OKLab."""
    lms = _as_color_array(linear) @ _LINEAR_SRGB_TO_LMS.T
    return np.cbrt(lms) @ _LMS_CBRT_TO_OKLAB.T


def oklab_to_linear_srgb(lab: Any) -> ColorArray:
    """Converts OKLab to linear sRGB, without clipping to the sRGB gamut."""
    lms_cbrt = _as_color_array(lab) @ _OKLAB_TO_LMS_CBRT.T
    return (lms_cbrt ** 3) @ _LMS_TO_LINEAR_SRGB.T


def srgb_to_oklab(rgb: Any) -> ColorArray:
    """Converts sRGB to OKLab."""
    return linear_srgb_to_oklab(srgb_to_linear(rgb))


def oklab_to_srgb(lab: Any) -> ColorArray:
    """Converts OKLab to sRGB, without clipping to the sRGB gamut."""
    return linear_to_srgb(oklab_to_linear_srgb(lab))


def oklab_to_oklch(lab: Any) -> ColorArray:
    """Converts OKLab to OKLCH. Grays get hue 0."""
    lightness, a, b = _channels(_as_color_array(lab))
    chroma = np.hypot(a, b)
    hue = np.where(chroma > ACHROMATIC_CHROMA, np.degrees(np.arctan2(b, a)) % 360.0, 0.0)
    return np.stack((lightness, chroma, hue), axis=-1)


def oklch_to_oklab(lch: Any) -> ColorArray:
    """Converts OKLCH to OKLab."""
    lightness, chroma, hue = _channels(_as_color_array(lch))
    hue_radians = np.radians(hue)
    return np.stack((lightness, chroma * np.cos(hue_radians), chroma * np.sin(hue_radians)), axis=-1)


def srgb_to_oklch(rgb: Any) -> ColorArray:
    """Converts sRGB to OKLCH."""
    return oklab_to_oklch(srgb_to_oklab(rgb))


def oklch_to_srgb(lch: Any) -> ColorArray:
    """Converts OKLCH to sRGB, without clipping to the sRGB gamut."""
    return oklab_to_srgb(oklch_to_oklab(lch))


def is_in_srgb_gamut(rgb: Any, tolerance: float = 1e-4) -> NDArray[np.bool_]:
    """Returns whether each sRGB or linear sRGB color has every channel within 0.0-1.0, give or take `tolerance`."""
    rgb = _as_color_array(rgb)
    return np.all((rgb >= -tolerance) & (rgb <= 1.0 + tolerance), axis=-1)


def _toe(x: ColorArray) -> ColorArray:
    """Maps OKLab lightness to OKHSV's estimate of perceived lightness."""
    shifted = _TOE_K3 * x - _TOE_K1
    return 0.5 * (shifted + np.sqrt(shifted * shifted + 4.0 * _TOE_K2 * _TOE_K3 * x))


def _toe_inv(x: ColorArray) -> ColorArray:
    """Inverse of `_toe`."""
    return (x * x + _TOE_K1 * x) / (_TOE_K3 * (x + _TOE_K2))


def _max_saturation(a: ColorArray, b: ColorArray) -> ColorArray:
    """Returns the largest saturation (chroma / lightness) inside the sRGB gamut for each normalized hue (a, b).

    a and b must satisfy a^2 + b^2 == 1.
    """
    # Each hue range is bounded by the first of red, green or blue to fall below zero. A polynomial estimates the
    # boundary and Halley's method refines it.
    red_first = (-1.88170328 * a - 0.80936493 * b) > 1.0
    green_first = ~red_first & ((1.81444104 * a - 1.19445276 * b) > 1.0)
    conditions = [red_first, green_first]

    def pick(red: float, green: float, blue: float) -> ColorArray:
        return np.select(conditions, [red, green], blue)

    k0 = pick(1.19086277, 0.73956515, 1.35733652)
    k1 = pick(1.76576728, -0.45954404, -0.00915799)
    k2 = pick(0.59662641, 0.08285427, -1.15130210)
    k3 = pick(0.75515197, 0.12541070, -0.50559606)
    k4 = pick(0.56771245, 0.14503204, 0.00692167)
    wl = pick(4.0767416621, -1.2684380046, -0.0041960863)
    wm = pick(-3.3077115913, 2.6097574011, -0.7034186147)
    ws = pick(0.2309699292, -0.3413193965, 1.7076147010)

    saturation = k0 + k1 * a + k2 * b + k3 * a * a + k4 * a * b

    k_l = 0.3963377774 * a + 0.2158037573 * b
    k_m = -0.1055613458 * a - 0.0638541728 * b
    k_s = -0.0894841775 * a - 1.2914855480 * b

    for _ in range(_HALLEY_STEPS):
        l_ = 1.0 + saturation * k_l
        m_ = 1.0 + saturation * k_m
        s_ = 1.0 + saturation * k_s
        f = wl * l_ ** 3 + wm * m_ ** 3 + ws * s_ ** 3
        f1 = 3.0 * (wl * k_l * l_ * l_ + wm * k_m * m_ * m_ + ws * k_s * s_ * s_)
        f2 = 6.0 * (wl * k_l * k_l * l_ + wm * k_m * k_m * m_ + ws * k_s * k_s * s_)
        saturation = saturation - f * f1 / (f1 * f1 - 0.5 * f * f2)
    return saturation


def _cusp_st(a: ColorArray, b: ColorArray) -> tuple[ColorArray, ColorArray]:
    """Returns OKHSV's (S_max, T_max) for each normalized hue: the slopes of the gamut triangle's two sides.

    The cusp is the most saturated in-gamut color of the hue. a and b must satisfy a^2 + b^2 == 1.
    """
    max_saturation = _max_saturation(a, b)
    rgb_at_max = oklab_to_linear_srgb(np.stack((np.ones_like(a), max_saturation * a, max_saturation * b), axis=-1))
    cusp_lightness = np.cbrt(1.0 / np.max(rgb_at_max, axis=-1))
    cusp_chroma = cusp_lightness * max_saturation
    return cusp_chroma / cusp_lightness, cusp_chroma / (1.0 - cusp_lightness)


def _gamut_scale(lightness: ColorArray, chroma: ColorArray, a: ColorArray, b: ColorArray) -> ColorArray:
    """Returns the factor that scales an OKLab color along its line to black onto the curved top of the sRGB gamut."""
    rgb = oklab_to_linear_srgb(np.stack((lightness, a * chroma, b * chroma), axis=-1))
    return np.cbrt(1.0 / np.maximum(np.max(rgb, axis=-1), 0.0))


def okhsv_to_srgb(hsv: Any) -> ColorArray:
    """Converts OKHSV to sRGB, clipped to the sRGB gamut.

    OKHSV approximates the gamut's curved top edge by scaling the largest channel to 1, which leaves another channel up
    to about 0.007 below 0 near the blue cusp (hue 264). Clipping removes that, so every result is a valid color, at
    the cost of an off-by-two 8-bit round trip for those colors.
    """
    hue, saturation, value = _channels(_as_color_array(hsv))
    hue_radians = np.radians(hue)
    a = np.cos(hue_radians)
    b = np.sin(hue_radians)
    s_max, t_max = _cusp_st(a, b)
    k = 1.0 - _OKHSV_S0 / s_max

    with np.errstate(divide='ignore', invalid='ignore'):
        # Lightness and chroma at value 1, treating the gamut as a triangle.
        denominator = _OKHSV_S0 + t_max - t_max * k * saturation
        lightness_v = 1.0 - saturation * _OKHSV_S0 / denominator
        chroma_v = saturation * t_max * _OKHSV_S0 / denominator
        lightness = value * lightness_v
        chroma = value * chroma_v

        # Compensate for the toe and the curved top of the real gamut.
        lightness_vt = _toe_inv(lightness_v)
        chroma_vt = chroma_v * lightness_vt / lightness_v
        new_lightness = _toe_inv(lightness)
        chroma = chroma * new_lightness / lightness
        lightness = new_lightness

        scale = _gamut_scale(lightness_vt, chroma_vt, a, b)
        lightness = lightness * scale
        chroma = chroma * scale

    black = value <= 0.0
    lightness = np.where(black, 0.0, lightness)
    chroma = np.where(black, 0.0, chroma)
    return np.clip(oklab_to_srgb(np.stack((lightness, chroma * a, chroma * b), axis=-1)), 0.0, 1.0)


def srgb_to_okhsv(rgb: Any) -> ColorArray:
    """Converts sRGB to OKHSV. Grays get hue and saturation 0; black also gets value 0."""
    lightness, lab_a, lab_b = _channels(srgb_to_oklab(rgb))
    chroma = np.hypot(lab_a, lab_b)
    achromatic = chroma <= ACHROMATIC_CHROMA
    safe_chroma = np.where(achromatic, 1.0, chroma)
    a = np.where(achromatic, 1.0, lab_a / safe_chroma)
    b = np.where(achromatic, 0.0, lab_b / safe_chroma)
    chroma = np.where(achromatic, 0.0, chroma)
    hue = np.where(achromatic, 0.0, np.degrees(np.arctan2(b, a)) % 360.0)

    s_max, t_max = _cusp_st(a, b)
    k = 1.0 - _OKHSV_S0 / s_max

    with np.errstate(divide='ignore', invalid='ignore'):
        t = t_max / (chroma + lightness * t_max)
        lightness_v = t * lightness
        chroma_v = t * chroma
        lightness_vt = _toe_inv(lightness_v)
        chroma_vt = chroma_v * lightness_vt / lightness_v

        scale = _gamut_scale(lightness_vt, chroma_vt, a, b)
        lightness = lightness / scale
        chroma = chroma / scale
        chroma = chroma * _toe(lightness) / lightness
        lightness = _toe(lightness)

        value = lightness / lightness_v
        saturation = (_OKHSV_S0 + t_max) * chroma_v / (t_max * _OKHSV_S0 + t_max * k * chroma_v)

    black = (lightness <= 0.0) | ~np.isfinite(value)
    hue = np.where(black, 0.0, hue)
    saturation = np.where(black | achromatic, 0.0, saturation)
    value = np.where(black, 0.0, value)
    return np.stack((hue, saturation, value), axis=-1)
