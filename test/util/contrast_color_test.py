"""Tests contrast ratio calculation and contrast-preserving color adjustment."""
from PySide6.QtGui import QColor

from src.util.visual.contrast_color import contrast_ratio, with_min_contrast
from test.base_test_case import IntraPaintTestCase

DARK_BACKGROUND = QColor('#1b1e20')
LIGHT_BACKGROUND = QColor('#eff0f1')


class ContrastRatioTest(IntraPaintTestCase):
    """Tests contrast_ratio against WCAG reference values."""

    def test_black_and_white(self) -> None:
        """Black and white have the maximum ratio, in either order."""
        self.assertAlmostEqual(contrast_ratio(QColor('black'), QColor('white')), 21.0, places=2)
        self.assertAlmostEqual(contrast_ratio(QColor('white'), QColor('black')), 21.0, places=2)

    def test_identical_colors(self) -> None:
        """A color has the minimum ratio against itself."""
        self.assertAlmostEqual(contrast_ratio(QColor('#3daee9'), QColor('#3daee9')), 1.0)


class WithMinContrastTest(IntraPaintTestCase):
    """Tests with_min_contrast."""

    def test_lightens_dark_color_on_dark_background(self) -> None:
        """A dark color on a dark background is lightened until it reaches the ratio, keeping its hue."""
        color = QColor('#995f5555')
        adjusted = with_min_contrast(color, DARK_BACKGROUND, 4.5)
        self.assertGreaterEqual(contrast_ratio(adjusted, DARK_BACKGROUND), 4.5)
        self.assertGreater(adjusted.lightnessF(), color.lightnessF())
        self.assertAlmostEqual(adjusted.hslHueF(), color.hslHueF(), places=2)
        self.assertEqual(adjusted.alpha(), 255)

    def test_darkens_light_color_on_light_background(self) -> None:
        """A light color on a light background is darkened until it reaches the ratio."""
        color = QColor('#ffe0e0')
        adjusted = with_min_contrast(color, LIGHT_BACKGROUND, 4.5)
        self.assertGreaterEqual(contrast_ratio(adjusted, LIGHT_BACKGROUND), 4.5)
        self.assertLess(adjusted.lightnessF(), color.lightnessF())

    def test_keeps_color_that_already_contrasts(self) -> None:
        """A color that already reaches the ratio only loses its transparency."""
        color = QColor('#80ffff00')
        adjusted = with_min_contrast(color, DARK_BACKGROUND, 4.5)
        self.assertEqual(adjusted.rgb(), color.rgb())
        self.assertEqual(adjusted.alpha(), 255)

    def test_unreachable_ratio_stops_at_extreme(self) -> None:
        """When the ratio can't be reached, the result is as far from the background as the hue allows."""
        adjusted = with_min_contrast(QColor('#808080'), QColor('#ffffff'), 22.0)
        self.assertEqual(adjusted.name(), '#000000')
