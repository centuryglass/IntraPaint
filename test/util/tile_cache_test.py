"""Tests TileCache: tile keys and areas, invalidation by area, and rendering missing tiles."""
import sys

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QColor, QImage, QPainter, QRegion
from PySide6.QtWidgets import QApplication

from src.image.mypaint.libmypaint import TILE_DIM
from src.util.visual.image_utils import create_transparent_image
from src.util.visual.tile_cache import TILE_SIZE, TileCache
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

SIZE = 10


class CoordinateRenderer:
    """Renders each pixel from its image coordinates and a generation number, and records every area it renders."""

    def __init__(self) -> None:
        self.generation = 0
        self.rendered: list[QRect] = []

    def color(self, x: int, y: int) -> QColor:
        """Returns the color this renderer gives image pixel (x, y)."""
        return QColor(x % 256, y % 256, self.generation % 256, 255)

    def __call__(self, image: QImage, area: QRect) -> None:
        self.rendered.append(QRect(area))
        for y in range(area.height()):
            for x in range(area.width()):
                image.setPixelColor(x, y, self.color(area.x() + x, area.y() + y))

    def expected(self, area: QRect) -> QImage:
        """Returns the image this renderer gives area, rendered in one call without recording it."""
        image = create_transparent_image(area.size())
        for y in range(area.height()):
            for x in range(area.width()):
                image.setPixelColor(x, y, self.color(area.x() + x, area.y() + y))
        return image


class TileCacheTest(IntraPaintTestCase):
    """Tests TileCache with a small tile size and a renderer that records what it renders."""

    def setUp(self) -> None:
        super().setUp()
        self.cache = TileCache(SIZE)
        self.renderer = CoordinateRenderer()

    def draw(self, area: QRect) -> QImage:
        """Returns area drawn from the cache into a new image."""
        image = create_transparent_image(area.size())
        self.cache.draw(image, area, area.topLeft(), self.renderer)
        return image

    def test_tile_size_is_mypaint_aligned(self) -> None:
        """The default tile size is a multiple of libmypaint's tile size."""
        self.assertEqual(TILE_SIZE % TILE_DIM, 0)
        self.assertEqual(TileCache().tile_size, TILE_SIZE)

    def test_invalid_tile_size(self) -> None:
        """A tile size below one raises ValueError."""
        with self.assertRaises(ValueError):
            TileCache(0)

    def test_tile_keys_cover_area(self) -> None:
        """tile_keys lists every tile an area touches, including tiles at negative coordinates."""
        self.assertEqual(self.cache.tile_keys(QRect(0, 0, SIZE, SIZE)), [(0, 0)])
        self.assertEqual(self.cache.tile_keys(QRect(9, 0, 2, 1)), [(0, 0), (1, 0)])
        self.assertEqual(self.cache.tile_keys(QRect(-1, -1, 2, 2)), [(-1, -1), (0, -1), (-1, 0), (0, 0)])
        self.assertEqual(self.cache.tile_keys(QRect()), [])

    def test_tile_rect_and_alignment(self) -> None:
        """tile_rect gives a tile's area in image coordinates, and tile_aligned the union of the tiles an area touches."""
        self.assertEqual(self.cache.tile_rect((-1, 2)), QRect(-SIZE, 2 * SIZE, SIZE, SIZE))
        self.assertEqual(self.cache.tile_aligned(QRect(-3, 5, 15, 1)), QRect(-SIZE, 0, 3 * SIZE, SIZE))
        self.assertTrue(self.cache.tile_aligned(QRect()).isEmpty())

    def test_draw_matches_single_render(self) -> None:
        """Drawing an area from tiles gives the same pixels as rendering that area in one call."""
        area = QRect(-7, 3, 31, 22)
        self.assert_images_equal(self.draw(area), self.renderer.expected(area))

    def test_cached_tiles_are_not_rendered_again(self) -> None:
        """A second read of the same area renders nothing."""
        self.draw(QRect(0, 0, 25, 25))
        render_count = len(self.renderer.rendered)
        self.draw(QRect(2, 2, 20, 20))
        self.assertEqual(len(self.renderer.rendered), render_count)

    def test_invalidate_drops_only_intersecting_tiles(self) -> None:
        """Invalidating an area re-renders the tiles it touches, and leaves the others cached with their old content."""
        area = QRect(0, 0, 3 * SIZE, 3 * SIZE)
        self.draw(area)
        self.assertEqual(self.cache.cached_count, 9)
        self.renderer.generation = 1
        self.renderer.rendered.clear()
        changed = QRect(SIZE + 2, SIZE + 2, 3, 3)
        self.cache.invalidate(changed)
        self.assertFalse(self.cache.is_cached((1, 1)))
        self.assertEqual(self.cache.cached_count, 8)
        drawn = self.draw(area)
        self.assertEqual(self.renderer.rendered, [self.cache.tile_rect((1, 1))])
        self.assertEqual(drawn.pixelColor(SIZE + 5, SIZE + 5), self.renderer.color(SIZE + 5, SIZE + 5))
        self.assertEqual(drawn.pixelColor(0, 0).blue(), 0)

    def test_clear_and_discard_outside(self) -> None:
        """discard_outside keeps only tiles touching its area, and clear drops every tile."""
        self.draw(QRect(0, 0, 3 * SIZE, SIZE))
        self.cache.discard_outside(QRect(SIZE, 0, 1, 1))
        self.assertEqual([self.cache.is_cached((x, 0)) for x in range(3)], [False, True, False])
        self.cache.clear()
        self.assertEqual(self.cache.cached_count, 0)

    def test_dense_missing_tiles_render_together(self) -> None:
        """Missing tiles that fill most of their bounding grid rectangle are rendered in one call."""
        self.draw(QRect(0, 0, 3 * SIZE, 2 * SIZE))
        self.assertEqual(self.renderer.rendered, [QRect(0, 0, 3 * SIZE, 2 * SIZE)])

    def test_sparse_missing_tiles_render_separately(self) -> None:
        """Missing tiles far apart are each rendered on their own, without rendering the tiles between them."""
        self.draw(QRect(0, 0, 3 * SIZE, 3 * SIZE))
        self.cache.invalidate(QRect(0, 0, 1, 1))
        self.cache.invalidate(QRect(3 * SIZE - 1, 3 * SIZE - 1, 1, 1))
        self.renderer.rendered.clear()
        self.draw(QRect(0, 0, 3 * SIZE, 3 * SIZE))
        self.assertEqual(self.renderer.rendered, [self.cache.tile_rect((0, 0)), self.cache.tile_rect((2, 2))])

    def test_draw_region_leaves_pixels_outside_region(self) -> None:
        """draw_region replaces only the pixels inside its region, at the given origin."""
        target = create_transparent_image(QRect(0, 0, 2 * SIZE, SIZE).size())
        target.fill(QColor(1, 2, 3, 255))
        origin = QPoint(5, 5)
        region = QRegion(QRect(5, 5, 4, 4)) + QRegion(QRect(15, 10, 2, 2))
        self.cache.draw_region(target, region, origin, self.renderer)
        self.assertEqual(target.pixelColor(0, 0), self.renderer.color(5, 5))
        self.assertEqual(target.pixelColor(10, 5), self.renderer.color(15, 10))
        self.assertEqual(target.pixelColor(5, 0), QColor(1, 2, 3, 255))

    def test_returned_tiles_are_copies(self) -> None:
        """Painting on an image from tiles() leaves the cached tile unchanged."""
        for _, tile in self.cache.tiles(QRect(0, 0, 1, 1), self.renderer):
            painter = QPainter(tile)
            painter.fillRect(tile.rect(), QColor(0, 0, 0, 0))
            painter.end()
        self.assert_images_equal(self.draw(QRect(0, 0, SIZE, SIZE)), self.renderer.expected(QRect(0, 0, SIZE, SIZE)))
