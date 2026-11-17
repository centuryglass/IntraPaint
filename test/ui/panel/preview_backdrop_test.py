"""Tests the shared sample backdrop under the Smudge, Filter and Clone stamp previews."""
import os

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage

from src.ui.panel.tool_control_panels.preview_backdrop import backdrop_image, backdrop_motif_rect, tile_size
from test.base_test_case import IntraPaintTestCase, TEST_RESOURCE_DIR

GOLDEN_DIR = os.path.join(TEST_RESOURCE_DIR, 'brush_previews')
BACKDROP_SIZE = QSize(200, 80)


class PreviewBackdropTest(IntraPaintTestCase):
    """Tests the backdrop's size, repetition and look."""

    def test_image_has_the_requested_size_and_is_opaque(self) -> None:
        """The backdrop fills the whole requested size with opaque pixels."""
        for size in (BACKDROP_SIZE, QSize(37, 21), QSize(500, 30)):
            with self.subTest(size=size):
                image = backdrop_image(size)
                self.assertEqual(image.size(), size)
                for x in range(0, size.width(), 7):
                    for y in range(0, size.height(), 5):
                        self.assertEqual(image.pixelColor(x, y).alpha(), 255)

    def test_tile_keeps_a_fixed_aspect(self) -> None:
        """The tile is twice as wide as the preview is tall, however wide the preview is."""
        self.assertEqual(tile_size(QSize(500, 40)), QSize(80, 40))
        self.assertEqual(tile_size(QSize(60, 40)), QSize(80, 40))

    def test_tile_repeats_across_the_width(self) -> None:
        """Each tile is a copy of the first."""
        image = backdrop_image(QSize(480, 80))
        tile_width = tile_size(image.size()).width()
        first = image.copy(0, 0, tile_width, 80)
        self.assert_images_equal(image.copy(tile_width, 0, tile_width, 80), first)
        self.assert_images_equal(image.copy(2 * tile_width, 0, tile_width, 80), first)

    def test_returned_images_are_independent_of_the_cache(self) -> None:
        """Drawing on a returned image does not change later ones."""
        image = backdrop_image(BACKDROP_SIZE)
        image.fill(QColor('red'))
        self.assertNotEqual(backdrop_image(BACKDROP_SIZE).pixelColor(0, 0), QColor('red'))

    def test_motif_rect_lies_within_the_tile(self) -> None:
        """The motif's bounds are inside the first tile and clear of its edges."""
        tile = tile_size(BACKDROP_SIZE)
        motif = backdrop_motif_rect(BACKDROP_SIZE)
        self.assertGreater(motif.left(), 0)
        self.assertGreater(motif.top(), 0)
        self.assertLess(motif.right(), tile.width())
        self.assertLess(motif.bottom(), tile.height())

    def test_golden_image(self) -> None:
        """The backdrop matches the golden image."""
        self.assert_image_matches_golden(backdrop_image(BACKDROP_SIZE),
                                         os.path.join(GOLDEN_DIR, 'backdrop.png'))
