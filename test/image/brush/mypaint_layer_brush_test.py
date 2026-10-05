"""Tests MyPaintLayerBrush output against golden images, and checks properties that must hold for any stroke.

The test layer is 3x2 MyPaint tiles, so most strokes cross tile boundaries.
"""
import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QColor, QImage

from src.image.brush.mypaint_layer_brush import MyPaintLayerBrush
from src.image.layers.image_layer import ImageLayer
from src.image.mypaint.libmypaint import TILE_DIM
from src.util.visual.image_utils import create_transparent_image
from test.image.brush.brush_test_case import BrushTestCase, LAYER_SIZE, StrokePoint, brush_test_pattern, \
    opacity_gradient_image, line_points, rect_mask

GOLDEN_DIR = 'test/resources/test_images/mypaint'
BRUSH_DIR = 'resources/brushes'
BULK_BRUSH = f'{BRUSH_DIR}/classic/bulk.myb'
BLEND_BRUSH = f'{BRUSH_DIR}/classic/blend+paint.myb'
ERASER_BRUSH = f'{BRUSH_DIR}/classic/ink_eraser.myb'
TEXTURED_BRUSH = f'{BRUSH_DIR}/classic/charcoal.myb'
BRUSH_COLOR = QColor(30, 90, 200)


def zigzag_points() -> list[StrokePoint]:
    """A stroke that doubles back across itself and crosses every tile boundary."""
    return (line_points(QPoint(15, 20), QPoint(175, 60), 9)
            + line_points(QPoint(175, 60), QPoint(20, 100), 9)[1:]
            + line_points(QPoint(20, 100), QPoint(170, 115), 9)[1:])


def edge_crossing_points() -> list[StrokePoint]:
    """A stroke that leaves the layer past three edges and comes back."""
    return (line_points(QPoint(60, 64), QPoint(-30, 64), 6)
            + line_points(QPoint(-30, 64), QPoint(100, -25), 6)[1:]
            + line_points(QPoint(100, -25), QPoint(220, 140), 6)[1:])


class MyPaintLayerBrushTest(BrushTestCase):
    """Drives MyPaintLayerBrush directly on an ImageLayer."""

    brush: MyPaintLayerBrush

    def setUp(self) -> None:
        super().setUp()
        self.layer = ImageLayer(brush_test_pattern(), 'mypaint test layer')
        self.brush = MyPaintLayerBrush(self.layer)
        self.brush.brush_path = BULK_BRUSH
        self.brush.brush_size = 20
        self.brush.brush_color = BRUSH_COLOR

    def assert_stroke_matches_golden(self, image: QImage, golden_name: str) -> None:
        """Checks that a stroke left only valid premultiplied pixels, then compares it with its golden image."""
        self.assert_valid_premultiplied(image)
        self.assert_image_matches_golden(image, f'{GOLDEN_DIR}/{golden_name}.png')

    def test_layer_size_sets_tile_grid(self) -> None:
        """The surface covers the layer with whole tiles."""
        # pylint: disable=protected-access
        surface = self.brush._mp_surface
        self.assertEqual(surface.tiles_width, LAYER_SIZE.width() // TILE_DIM)
        self.assertEqual(surface.tiles_height, LAYER_SIZE.height() // TILE_DIM)

    def test_bulk_on_blank_layer(self) -> None:
        """A simple opaque brush on a transparent layer."""
        self.use_layer(create_transparent_image(LAYER_SIZE))
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'bulk_blank')

    def test_bulk_on_pattern(self) -> None:
        """A simple opaque brush over existing content, including transparent and half-transparent bands."""
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'bulk_pattern')

    def test_pressure(self) -> None:
        """Rising then falling pressure on a brush whose size and opacity follow pressure."""
        points = line_points(QPoint(15, 64), QPoint(175, 64), 8)
        count = len(points)
        pressure_points: list[StrokePoint] = [(x, y, 1.0 - abs(2 * i / (count - 1) - 1)) for i, (x, y, *_)
                                              in enumerate(points)]
        image = self.stroke(pressure_points)
        self.assert_stroke_matches_golden(image, 'bulk_pressure')

    def test_blending_brush_on_pattern(self) -> None:
        """A brush that picks up and smudges the color under it."""
        self.brush.brush_path = BLEND_BRUSH
        self.brush.brush_size = 30
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'blend_pattern')

    def test_eraser_brush_on_pattern(self) -> None:
        """A brush file that erases."""
        self.brush.brush_path = ERASER_BRUSH
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'ink_eraser_pattern')

    def test_eraser_mode(self) -> None:
        """A painting brush switched to eraser mode erases, and switching back paints again."""
        self.brush.eraser = True
        self.stroke(line_points(QPoint(15, 30), QPoint(175, 30), 8))
        self.brush.eraser = False
        image = self.stroke(line_points(QPoint(15, 90), QPoint(175, 90), 8))
        self.assert_stroke_matches_golden(image, 'bulk_eraser_mode')

    def test_textured_brush_on_pattern(self) -> None:
        """A brush with randomized, grainy dabs."""
        self.brush.brush_path = TEXTURED_BRUSH
        self.brush.brush_size = 24
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'charcoal_pattern')

    def test_bulk_on_opacity_gradient(self) -> None:
        """A simple brush across an opacity gradient."""
        self.use_layer(opacity_gradient_image())
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'bulk_opacity_gradient')

    def test_blending_brush_on_opacity_gradient(self) -> None:
        """A blending brush dragging transparent and opaque pixels into each other."""
        self.use_layer(opacity_gradient_image())
        self.brush.brush_path = BLEND_BRUSH
        self.brush.brush_size = 30
        self.stroke(line_points(QPoint(180, 30), QPoint(10, 30), 7))
        image = self.stroke(line_points(QPoint(10, 90), QPoint(180, 90), 7))
        self.assert_stroke_matches_golden(image, 'blend_opacity_gradient')

    def test_stroke_crossing_layer_edges(self) -> None:
        """Dabs partly or fully outside the layer only change pixels inside it."""
        self.brush.brush_size = 30
        image = self.stroke(edge_crossing_points())
        self.assert_stroke_matches_golden(image, 'bulk_crossing_edges')

    def test_blending_brush_crossing_layer_edges(self) -> None:
        """A blending brush sampling partly outside the layer."""
        self.brush.brush_path = BLEND_BRUSH
        self.brush.brush_size = 30
        image = self.stroke(edge_crossing_points())
        self.assert_stroke_matches_golden(image, 'blend_crossing_edges')

    def test_input_mask_restricts_changes(self) -> None:
        """Only pixels inside the input mask change."""
        selected = QRect(40, 30, 100, 50)
        initial_image = self.layer.image
        self.brush.set_input_mask(rect_mask(selected))
        image = self.stroke(zigzag_points())
        self.assert_changes_inside(image, initial_image, selected)
        self.assert_stroke_matches_golden(image, 'bulk_input_mask')

    def test_blending_brush_with_input_mask(self) -> None:
        """A blending brush inside an input mask only changes pixels inside it."""
        selected = QRect(40, 30, 100, 50)
        initial_image = self.layer.image
        self.brush.brush_path = BLEND_BRUSH
        self.brush.brush_size = 30
        self.brush.set_input_mask(rect_mask(selected))
        image = self.stroke(zigzag_points())
        self.assert_changes_inside(image, initial_image, selected)
        self.assert_stroke_matches_golden(image, 'blend_input_mask')

    @pytest.mark.xfail(strict=True, reason='tiles copy color painted at MyPaint\'s alpha onto the locked alpha')
    def test_alpha_locked_layer(self) -> None:
        """On an alpha-locked layer, color changes but alpha doesn't."""
        initial_image = self.layer.image
        self.layer.alpha_locked = True
        image = self.stroke(zigzag_points())
        self.assert_images_equal(image.convertToFormat(QImage.Format.Format_Alpha8),
                                 initial_image.convertToFormat(QImage.Format.Format_Alpha8))
        self.assert_stroke_matches_golden(image, 'bulk_alpha_locked')

    def assert_mid_stroke_writes_match_one_write(self, brush_path: str) -> None:
        """Asserts that writing changed tiles back to the layer after every input point gives the same result as
           writing once at the end of the stroke."""
        self.brush.brush_path = brush_path
        expected_image = self.stroke(zigzag_points())

        self.brush = MyPaintLayerBrush(None)
        self.brush.brush_path = brush_path
        self.brush.brush_size = 20
        self.brush.brush_color = BRUSH_COLOR
        self.use_layer(brush_test_pattern())
        self.brush.start_stroke()
        for x, y, *_ in zigzag_points():
            self.brush.stroke_to(x, y, None, None, None)
            self.brush._mp_surface.apply_pending_tile_updates()  # pylint: disable=protected-access
        self.brush.end_stroke()
        self.assert_images_equal(self.layer.image, expected_image)

    def test_mid_stroke_tile_writes_match_one_write_at_end(self) -> None:
        """Writing changed tiles partway through a stroke doesn't change a simple brush's result."""
        self.assert_mid_stroke_writes_match_one_write(BULK_BRUSH)

    def test_blending_mid_stroke_tile_writes_match_one_write_at_end(self) -> None:
        """Writing changed tiles partway through a stroke doesn't change what a blending brush picks up."""
        self.assert_mid_stroke_writes_match_one_write(BLEND_BRUSH)

    def test_layer_edit_between_strokes_is_used(self) -> None:
        """A blending brush picks up changes made to the layer outside the brush since its last stroke."""
        self.brush.brush_path = BLEND_BRUSH
        self.brush.brush_size = 30
        self.stroke(line_points(QPoint(20, 64), QPoint(80, 64), 8))
        with self.layer.borrow_image() as layer_image:
            layer_image.fill(QColor(255, 0, 0))
        image = self.stroke(line_points(QPoint(20, 64), QPoint(170, 64), 8))
        self.assert_stroke_matches_golden(image, 'blend_after_layer_edit')

    def test_click_without_movement_changes_nothing(self) -> None:
        """A single point with no movement paints nothing with a brush that has no dabs per second."""
        image = self.stroke([(96, 64)])
        self.assert_stroke_matches_golden(image, 'bulk_click')
