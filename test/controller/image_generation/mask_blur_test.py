"""Tests the mask blur band geometry and growing a mask by the band's reach."""
from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QColor, QImage, QPainter

from src.controller.image_generation.mask_blur import (blur_extent, blur_extent_in_image, blurred_mask_estimate, grow_mask,
                                                             shrink_mask)
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
        """A crop smaller than the generation resolution narrows the band in image pixels, per axis."""
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

    def test_shrink_mask_removes_the_reach_from_every_edge(self) -> None:
        """Shrinking leaves a hard mask smaller by the reach on each side."""
        mask = _mask(QSize(40, 40), QRect(10, 10, 20, 20))
        shrunk = shrink_mask(mask, 3)
        self.assertEqual(shrunk.pixelColor(20, 20).alpha(), 255)
        self.assertEqual(shrunk.pixelColor(13, 20).alpha(), 255)
        self.assertEqual(shrunk.pixelColor(12, 20).alpha(), 0)

    def test_shrink_mask_keeps_a_selection_narrower_than_the_reach(self) -> None:
        """A selection the shrink would erase entirely is returned unchanged."""
        mask = _mask(QSize(40, 40), QRect(10, 10, 4, 4))
        self.assertEqual(shrink_mask(mask, 5).pixelColor(11, 11).alpha(), 255)

    def test_blurred_estimate_is_half_at_the_edge(self) -> None:
        """A blurred hard edge passes through about half alpha and is soft on both sides."""
        estimate = blurred_mask_estimate(_mask(QSize(40, 40), QRect(0, 0, 20, 40)), 4)
        self.assertAlmostEqual(estimate.pixelColor(19, 20).alpha(), 128, delta=40)
        self.assertGreater(estimate.pixelColor(22, 20).alpha(), 0)
        self.assertEqual(estimate.pixelColor(2, 20).alpha(), 255)
