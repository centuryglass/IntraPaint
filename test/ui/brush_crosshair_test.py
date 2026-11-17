"""Tests for the generated brush crosshair cursors."""
from PySide6.QtCore import QPoint

from src.ui.brush_crosshair import (CENTER_CUTOUT, CROSSHAIR_SIZE, CrosshairVariant, crosshair_cursor, crosshair_image,
                                    crosshair_pixel_scale)
from test.base_test_case import IntraPaintTestCase

GOLDEN_DIR = 'test/resources/brush_crosshairs'


class BrushCrosshairTest(IntraPaintTestCase):
    """Checks crosshair images, hotspots and pixel scaling."""

    def test_variant_images_match_goldens(self) -> None:
        """Each variant's crosshair matches its golden image at 1x and 2x."""
        for variant in CrosshairVariant:
            for scale in (1, 2):
                with self.subTest(variant=variant.value, scale=scale):
                    self.assert_image_matches_golden(crosshair_image(variant, scale),
                                                     f'{GOLDEN_DIR}/{variant.value}_{scale}x.png')

    def test_center_cutout_is_clear(self) -> None:
        """No halo covers the pixels around the hotspot, so the target pixel stays visible."""
        center = CROSSHAIR_SIZE // 2
        for variant in CrosshairVariant:
            image = crosshair_image(variant)
            for y in range(center - CENTER_CUTOUT, center + CENTER_CUTOUT + 1):
                for x in range(center - CENTER_CUTOUT, center + CENTER_CUTOUT + 1):
                    with self.subTest(variant=variant.value, x=x, y=y):
                        self.assertEqual(image.pixelColor(x, y).alpha(), 0)

    def test_cursor_hotspot_is_center_pixel(self) -> None:
        """The cursor's hotspot is the crosshair's centre pixel, in logical pixels at every screen density."""
        center = CROSSHAIR_SIZE // 2
        for ratio in (1.0, 2.0):
            with self.subTest(ratio=ratio):
                cursor = crosshair_cursor(CrosshairVariant.PLAIN, ratio)
                self.assertEqual(cursor.hotSpot(), QPoint(center, center))
                pixmap = cursor.pixmap()
                self.assertEqual(pixmap.deviceIndependentSize().toSize().width(), CROSSHAIR_SIZE)

    def test_pixel_scale(self) -> None:
        """Whole ratios keep their scale, and fractional ratios round up unless they are at most 0.25 above a whole
           number."""
        for ratio, expected in ((0.75, 1), (1.0, 1), (1.25, 1), (1.5, 2), (2.0, 2), (2.25, 2), (3.0, 3)):
            with self.subTest(ratio=ratio):
                self.assertEqual(crosshair_pixel_scale(ratio), expected)
