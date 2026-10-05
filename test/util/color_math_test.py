"""Test color space conversions in color_math."""
import numpy as np

from src.util.visual.color_math import srgb_to_linear, linear_to_srgb, srgb_to_oklab, oklab_to_srgb, \
    srgb_to_oklch, oklch_to_srgb, srgb_to_okhsv, okhsv_to_srgb, is_in_srgb_gamut
from test.base_test_case import IntraPaintTestCase

ONE_8BIT_STEP = 1.0 / 255.0

# sRGB colors with OKLab values published in Ottosson's "A perceptual color space for image processing" and CSS Color 4.
OKLAB_REFERENCE_VALUES = [
    ((1.0, 1.0, 1.0), (1.0, 0.0, 0.0)),
    ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
    ((1.0, 0.0, 0.0), (0.62796, 0.22486, 0.12585)),
    ((0.0, 1.0, 0.0), (0.86644, -0.23389, 0.17950)),
    ((0.0, 0.0, 1.0), (0.45201, -0.03246, -0.31153)),
]

PRIMARIES_AND_SECONDARIES = [(1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0),
                             (0.0, 1.0, 1.0), (0.0, 0.0, 1.0), (1.0, 0.0, 1.0)]


def _srgb_grid(steps: int) -> np.ndarray:
    axis = np.linspace(0.0, 1.0, steps)
    return np.stack(np.meshgrid(axis, axis, axis, indexing='ij'), axis=-1).reshape(-1, 3)


def _okhsv_grid(hue_steps: int, steps: int) -> np.ndarray:
    hue = np.linspace(0.0, 360.0, hue_steps, endpoint=False)
    axis = np.linspace(0.0, 1.0, steps)
    return np.stack(np.meshgrid(hue, axis, axis, indexing='ij'), axis=-1).reshape(-1, 3)


class TestColorMath(IntraPaintTestCase):
    """Test color space conversions in color_math."""

    def test_transfer_curve_round_trip(self) -> None:
        """sRGB to linear and back is lossless, including the mirrored negative range out-of-gamut colors use."""
        values = np.linspace(-1.0, 1.0, 201)
        colors = np.stack((values, values, values), axis=-1)
        np.testing.assert_allclose(linear_to_srgb(srgb_to_linear(colors)), colors, atol=1e-12)
        self.assertAlmostEqual(float(srgb_to_linear((0.5, 0.5, 0.5))[0]), 0.21404, places=5)

    def test_oklab_reference_values(self) -> None:
        """sRGB white, black and primaries convert to their published OKLab values."""
        for rgb, expected_lab in OKLAB_REFERENCE_VALUES:
            np.testing.assert_allclose(srgb_to_oklab(rgb), expected_lab, atol=1e-4, err_msg=str(rgb))

    def test_oklab_round_trip(self) -> None:
        """sRGB to OKLab and back stays within one 8-bit step across the gamut."""
        colors = _srgb_grid(18)
        np.testing.assert_allclose(oklab_to_srgb(srgb_to_oklab(colors)), colors, atol=ONE_8BIT_STEP)

    def test_oklch_round_trip(self) -> None:
        """sRGB to OKLCH and back stays within one 8-bit step, and OKLCH hue stays in 0-360."""
        colors = _srgb_grid(18)
        lch = srgb_to_oklch(colors)
        self.assertTrue(np.all((lch[:, 2] >= 0.0) & (lch[:, 2] < 360.0)))
        np.testing.assert_allclose(oklch_to_srgb(lch), colors, atol=ONE_8BIT_STEP)

    def test_oklch_grays(self) -> None:
        """Grays have zero chroma and hue 0, and white has lightness 1."""
        for gray in (0.0, 0.25, 0.5, 1.0):
            lch = srgb_to_oklch((gray, gray, gray))
            self.assertAlmostEqual(float(lch[1]), 0.0, places=6)
            self.assertEqual(float(lch[2]), 0.0)
        self.assertAlmostEqual(float(srgb_to_oklch((1.0, 1.0, 1.0))[0]), 1.0, places=4)

    def test_okhsv_square_in_gamut(self) -> None:
        """Every OKHSV color over a sweep of hues, saturations and values is a valid sRGB color."""
        rgb = okhsv_to_srgb(_okhsv_grid(720, 33))
        self.assertFalse(np.any(np.isnan(rgb)))
        self.assertTrue(np.all(is_in_srgb_gamut(rgb, tolerance=0.0)))

    def test_okhsv_square_reaches_gamut_edge(self) -> None:
        """At full saturation and value, every hue has one channel at 1 and one at 0, so the square spans the gamut."""
        hue = np.linspace(0.0, 360.0, 720, endpoint=False)
        rgb = okhsv_to_srgb(np.stack((hue, np.ones_like(hue), np.ones_like(hue)), axis=-1))
        np.testing.assert_allclose(rgb.max(axis=-1), 1.0, atol=1e-6)
        np.testing.assert_allclose(rgb.min(axis=-1), 0.0, atol=2 * ONE_8BIT_STEP)

    def test_okhsv_round_trip(self) -> None:
        """sRGB to OKHSV and back stays within one 8-bit step across the gamut."""
        colors = _srgb_grid(18)
        np.testing.assert_allclose(okhsv_to_srgb(srgb_to_okhsv(colors)), colors, atol=ONE_8BIT_STEP)

    def test_okhsv_known_values(self) -> None:
        """Black, white, grays and the sRGB primaries and secondaries land on the expected OKHSV edges."""
        np.testing.assert_allclose(srgb_to_okhsv((0.0, 0.0, 0.0)), (0.0, 0.0, 0.0), atol=1e-9)
        np.testing.assert_allclose(srgb_to_okhsv((1.0, 1.0, 1.0)), (0.0, 0.0, 1.0), atol=1e-6)
        gray = srgb_to_okhsv((0.5, 0.5, 0.5))
        self.assertEqual(float(gray[1]), 0.0)
        self.assertTrue(0.0 < gray[2] < 1.0)
        for rgb in PRIMARIES_AND_SECONDARIES:
            _, saturation, value = srgb_to_okhsv(rgb)
            self.assertAlmostEqual(float(saturation), 1.0, delta=1e-3, msg=str(rgb))
            self.assertAlmostEqual(float(value), 1.0, delta=1e-6, msg=str(rgb))
        np.testing.assert_allclose(okhsv_to_srgb((123.0, 0.7, 0.0)), (0.0, 0.0, 0.0), atol=1e-9)

    def test_okhsv_hue_matches_oklch_hue(self) -> None:
        """OKHSV and OKLCH share their hue angle."""
        colors = _srgb_grid(10)
        lch = srgb_to_oklch(colors)
        hsv = srgb_to_okhsv(colors)
        chromatic = lch[:, 1] > 1e-4
        np.testing.assert_allclose(hsv[chromatic, 0], lch[chromatic, 2], atol=1e-6)

    def test_array_and_scalar_paths_agree(self) -> None:
        """Converting colors one at a time gives the same results as converting them as one array."""
        colors = _srgb_grid(5)
        conversions = [srgb_to_oklab, srgb_to_oklch, srgb_to_okhsv]
        for convert in conversions:
            as_array = convert(colors)
            one_at_a_time = np.array([convert(tuple(color)) for color in colors])
            np.testing.assert_allclose(one_at_a_time, as_array, atol=1e-12, err_msg=convert.__name__)
        hsv = _okhsv_grid(12, 5)
        as_array = okhsv_to_srgb(hsv)
        one_at_a_time = np.array([okhsv_to_srgb(tuple(color)) for color in hsv])
        np.testing.assert_allclose(one_at_a_time, as_array, atol=1e-12)
        plane = okhsv_to_srgb(hsv.reshape(12, 25, 3))
        self.assertEqual(plane.shape, (12, 25, 3))
        np.testing.assert_allclose(plane.reshape(-1, 3), as_array, atol=1e-12)

    def test_rejects_wrong_channel_count(self) -> None:
        """Arrays without three channels on the last axis raise ValueError."""
        with self.assertRaises(ValueError):
            srgb_to_oklab((1.0, 0.0))
        with self.assertRaises(ValueError):
            okhsv_to_srgb(np.zeros((4, 4)))
