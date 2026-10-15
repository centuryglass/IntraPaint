"""Tests the mask blur band geometry and the soft paste mask."""
from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QColor, QImage, QPainter

from src.controller.image_generation.mask_blur import blur_extent, blur_extent_in_image, soft_paste_mask
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

    def test_soft_mask_fades_through_the_edge(self) -> None:
        """Blurring keeps the interior opaque and spreads alpha beyond the selection edge."""
        size = QSize(100, 100)
        soft = soft_paste_mask(_mask(size, QRect(30, 30, 40, 40)), size, size, 4)
        self.assertEqual(soft.size(), size)
        self.assertEqual(soft.pixelColor(50, 50).alpha(), 255)
        self.assertEqual(soft.pixelColor(2, 2).alpha(), 0)
        outside = soft.pixelColor(28, 50).alpha()
        self.assertTrue(0 < outside < 128, outside)

    def test_zero_blur_returns_the_mask(self) -> None:
        """Without blur the mask is untouched."""
        size = QSize(20, 20)
        mask = _mask(size, QRect(5, 5, 10, 10))
        self.assertEqual(soft_paste_mask(mask, size, size, 0), mask)

    def test_non_square_scale_blurs_less_along_the_narrow_axis(self) -> None:
        """Different scales per axis give different spread horizontally and vertically."""
        size = QSize(100, 100)
        selected = QRect(30, 30, 40, 40)
        soft = soft_paste_mask(_mask(size, selected), QSize(100, 50), size, 8)  # sigma 8 across, 4 down
        across = soft.pixelColor(26, 50).alpha()
        down = soft.pixelColor(50, 26).alpha()
        self.assertGreater(across, down)
