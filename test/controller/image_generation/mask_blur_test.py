"""Tests the mask blur band geometry and growing a mask by the band's reach."""
from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QColor, QImage, QPainter

from src.controller.image_generation.mask_blur import blur_extent, blur_extent_in_image, grow_mask
from test.base_test_case import IntraPaintTestCase


def _mask(size: QSize, selected: QRect) -> QImage:
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    painter.fillRect(selected, QColor(255, 0, 0, 255))
    painter.end()
    return image


class MaskBlurTest(IntraPaintTestCase):
    """Tests the shared blur band helpers."""

    def test_extent_is_two_and_a_half_sigmas(self) -> None:
        """The band reaches ceil(2.5 * blur) generation pixels, and nothing without blur."""
        self.assertEqual(blur_extent(0), 0)
        self.assertEqual(blur_extent(4), 10)
        self.assertEqual(blur_extent(3), 8)

    def test_extent_scales_per_axis_with_the_crop(self) -> None:
        """A crop smaller than the generation size narrows the band in image pixels, per axis."""
        self.assertEqual(blur_extent_in_image(4, QSize(256, 128), QSize(512, 512)), (5, 3))
        self.assertEqual(blur_extent_in_image(4, QSize(1024, 512), QSize(512, 512)), (20, 10))

    def test_grow_mask_reaches_per_axis(self) -> None:
        """Growing covers reach_x pixels across and reach_y pixels down, and stays hard-edged."""
        mask = _mask(QSize(100, 100), QRect(40, 40, 20, 20))
        grown = grow_mask(mask, 6, 3)
        self.assertEqual(grown.pixelColor(34, 50).alpha(), 255)
        self.assertEqual(grown.pixelColor(33, 50).alpha(), 0)
        self.assertEqual(grown.pixelColor(50, 37).alpha(), 255)
        self.assertEqual(grown.pixelColor(50, 36).alpha(), 0)
        self.assertEqual({grown.pixelColor(x, 50).alpha() for x in range(100)}, {0, 255})
        self.assertEqual(mask.pixelColor(34, 50).alpha(), 0, 'the source mask must not change')

    def test_grow_mask_without_reach_copies(self) -> None:
        """Without reach the result matches the mask."""
        mask = _mask(QSize(20, 20), QRect(5, 5, 10, 10))
        self.assertEqual(grow_mask(mask, 0, 0), mask)
