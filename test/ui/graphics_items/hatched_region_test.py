"""Tests HatchedRegion's pattern tile, its geometry, and how it paints at different scales and offsets."""
import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QTransform
from PySide6.QtWidgets import QApplication, QGraphicsScene

from src.ui.graphics_items.hatched_region import HatchedRegion, hatch_tile, HATCH_PERIOD, HATCH_LINE_WIDTH
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

BACKGROUND = QColor(128, 128, 128)


def _rect_path(rect: QRectF) -> QPainterPath:
    path = QPainterPath()
    path.addRect(rect)
    return path


def _paint(item: HatchedRegion, transform: QTransform, size: int) -> QImage:
    """Renders a scene holding only the item onto a gray image, with the scene mapped through `transform`."""
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(BACKGROUND)
    painter = QPainter(image)
    painter.setTransform(transform)
    item.paint(painter, None)
    painter.end()
    return image


def _row(image: QImage, y: int) -> list[str]:
    return [image.pixelColor(x, y).name() for x in range(image.width())]


class HatchTileTest(IntraPaintTestCase):
    """Tests the pattern tile."""

    def test_tile_has_dark_light_and_clear_pixels(self) -> None:
        """Each row of the tile holds a dark line, a light line beside it, and clear gaps."""
        tile = hatch_tile(1.0).toImage()
        self.assertEqual(tile.width(), HATCH_PERIOD)
        for y in range(tile.height()):
            alphas = [tile.pixelColor(x, y).alpha() for x in range(tile.width())]
            self.assertEqual(alphas.count(0), HATCH_PERIOD - HATCH_LINE_WIDTH * 2)
            lightness = sorted(tile.pixelColor(x, y).lightness() for x in range(tile.width())
                               if tile.pixelColor(x, y).alpha() > 0)
            self.assertEqual(lightness[0], 0)
            self.assertEqual(lightness[-1], 255)

    def test_tile_scales_with_device_pixel_ratio(self) -> None:
        """At a device pixel ratio of 2, the tile has twice the pixels and the same logical size."""
        tile = hatch_tile(2.0)
        self.assertEqual(tile.width(), HATCH_PERIOD * 2)
        self.assertEqual(tile.deviceIndependentSize().width(), HATCH_PERIOD)


class HatchedRegionTest(IntraPaintTestCase):
    """Tests the item's geometry and painting."""

    def setUp(self) -> None:
        super().setUp()
        self.scene = QGraphicsScene()
        self.item = HatchedRegion()
        self.scene.addItem(self.item)

    def tearDown(self) -> None:
        self.scene.removeItem(self.item)
        self.scene.deleteLater()
        super().tearDown()

    def test_bounds_follow_region(self) -> None:
        """The bounding rectangle is the region's bounds, and empty without a region."""
        self.assertTrue(self.item.boundingRect().isEmpty())
        self.item.region = _rect_path(QRectF(4, 6, 10, 12))
        self.assertEqual(self.item.boundingRect(), QRectF(4, 6, 10, 12))

    def test_paints_only_inside_region(self) -> None:
        """Pixels outside the region keep the background, and pixels inside it include hatching."""
        self.item.region = _rect_path(QRectF(0, 0, 16, 32))
        image = _paint(self.item, QTransform(), 32)
        inside = {image.pixelColor(x, y).name() for x in range(16) for y in range(32)}
        outside = {image.pixelColor(x, y).name() for x in range(16, 32) for y in range(32)}
        self.assertEqual(outside, {BACKGROUND.name()})
        self.assertIn(BACKGROUND.name(), inside)
        self.assertGreater(len(inside), 2)

    def test_period_is_the_same_at_every_scale(self) -> None:
        """Zooming in doesn't stretch the hatching: the stripe period in device pixels stays fixed."""
        self.item.region = _rect_path(QRectF(0, 0, 64, 64))
        for scale in (1.0, 3.0):
            image = _paint(self.item, QTransform.fromScale(scale, scale), 64)
            row = _row(image, 10)
            darkest = min(range(len(row)), key=lambda x, r=row: QColor(r[x]).lightness())
            dark_color = row[darkest]
            dark_columns = [x for x, color in enumerate(row) if color == dark_color]
            gaps = {b - a for a, b in zip(dark_columns, dark_columns[1:])}
            self.assertEqual(gaps, {HATCH_PERIOD}, f'scale {scale}')

    def test_pattern_moves_with_the_scene(self) -> None:
        """Panning by a distance that isn't a multiple of the period shifts the pattern by that distance."""
        self.item.region = _rect_path(QRectF(-64, -64, 192, 192))
        still = _paint(self.item, QTransform(), 32)
        panned = _paint(self.item, QTransform.fromTranslate(3, 0), 32)
        self.assertNotEqual(_row(still, 5), _row(panned, 5))
        self.assertEqual(_row(still, 5)[:-3], _row(panned, 5)[3:])

    def test_ignores_mouse_buttons(self) -> None:
        """The hatching never takes mouse presses from the tools."""
        self.assertEqual(self.item.acceptedMouseButtons(), Qt.MouseButton.NoButton)

    def test_empty_region_paints_nothing(self) -> None:
        """With no region the item leaves the image untouched."""
        image = _paint(self.item, QTransform.fromTranslate(2, 2), 8)
        self.assertEqual({image.pixelColor(x, y).name() for x in range(8) for y in range(8)}, {BACKGROUND.name()})
