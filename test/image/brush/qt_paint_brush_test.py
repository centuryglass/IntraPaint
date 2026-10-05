"""Tests QtPaintBrush output against golden images, and checks properties that must hold for any stroke."""
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QBrush, QImage

from src.image.brush.qt_paint_brush import QtPaintBrush
from src.image.layers.image_layer import ImageLayer
from src.undo_stack import UndoStack
from src.util.visual.image_utils import image_data_as_numpy_8bit, create_transparent_image
from test.image.brush.brush_test_case import BrushTestCase, LAYER_SIZE, StrokePoint, brush_test_pattern, \
    opacity_gradient_image, line_points, rect_mask

GOLDEN_DIR = 'test/resources/test_images/qt_paint_brush'
BRUSH_COLOR = QColor(30, 90, 200)


def zigzag_points() -> list[StrokePoint]:
    """A stroke that doubles back across itself several times, so later segments overlap earlier ones."""
    return (line_points(QPoint(20, 30), QPoint(170, 60), 9)
            + line_points(QPoint(170, 60), QPoint(30, 90), 9)[1:]
            + line_points(QPoint(30, 90), QPoint(160, 20), 9)[1:])


class QtPaintBrushTest(BrushTestCase):
    """Drives QtPaintBrush directly on an ImageLayer."""

    brush: QtPaintBrush

    def setUp(self) -> None:
        super().setUp()
        self.layer = ImageLayer(brush_test_pattern(), 'draw test layer')
        self.brush = QtPaintBrush(self.layer)
        self.brush.brush_size = 16
        self.brush.brush_color = BRUSH_COLOR
        self.brush.opacity = 1.0
        self.brush.hardness = 1.0
        self.brush.antialiasing = False
        self.brush.pressure_size = True
        self.brush.pressure_opacity = False
        self.brush.pressure_hardness = False

    def assert_stroke_matches_golden(self, image: QImage, golden_name: str) -> None:
        """Checks that a stroke left only valid premultiplied pixels, then compares it with its golden image."""
        self.assert_valid_premultiplied(image)
        self.assert_image_matches_golden(image, f'{GOLDEN_DIR}/{golden_name}.png')

    def test_brush_constructed_with_layer_draws(self) -> None:
        """A brush given its layer at construction has usable stroke buffers."""
        image = self.stroke([(50, 50), (60, 50)])
        self.assertNotEqual(image, brush_test_pattern())

    def test_hard_aliased_stroke(self) -> None:
        """A hard, opaque brush without antialiasing."""
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'hard_aliased')

    def test_hard_antialiased_translucent_stroke(self) -> None:
        """A hard, antialiased brush at partial opacity, crossing itself."""
        self.brush.brush_size = 20
        self.brush.opacity = 0.6
        self.brush.antialiasing = True
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'hard_antialiased_translucent')

    def test_soft_stroke(self) -> None:
        """A soft, antialiased brush at partial opacity, crossing itself."""
        self.brush.brush_size = 30
        self.brush.opacity = 0.8
        self.brush.hardness = 0.3
        self.brush.antialiasing = True
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'soft')

    def test_soft_aliased_stroke(self) -> None:
        """A soft, opaque brush without antialiasing."""
        self.brush.brush_size = 24
        self.brush.hardness = 0.5
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'soft_aliased')

    def test_translucent_color(self) -> None:
        """A brush color with partial alpha, combined with partial opacity."""
        self.brush.brush_color = QColor(220, 40, 90, 140)
        self.brush.brush_size = 20
        self.brush.opacity = 0.7
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'translucent_color')

    def test_pressure_controls_size_opacity_and_hardness(self) -> None:
        """Rising pressure scales size, opacity and hardness along the stroke."""
        self.brush.brush_size = 40
        self.brush.pressure_opacity = True
        self.brush.pressure_hardness = True
        self.brush.antialiasing = True
        line = line_points(QPoint(15, 90), QPoint(175, 30), 8)
        points: list[StrokePoint] = [(x, y, 0.2 + 0.8 * i / (len(line) - 1)) for i, (x, y, *_) in enumerate(line)]
        image = self.stroke(points)
        self.assert_stroke_matches_golden(image, 'pressure')

    def test_pressure_ignored_when_disabled(self) -> None:
        """With every pressure option off, pressure doesn't change the stroke."""
        self.brush.pressure_size = False
        self.brush.hardness = 0.5
        line = line_points(QPoint(15, 90), QPoint(175, 30), 8)
        expected_image = self.stroke(line)
        UndoStack().undo()
        points: list[StrokePoint] = [(x, y, 0.1 + 0.9 * (i % 2)) for i, (x, y, *_) in enumerate(line)]
        self.assert_images_equal(self.stroke(points), expected_image)

    def test_input_mask_restricts_changes(self) -> None:
        """Changes stay inside the input mask."""
        initial_image = self.layer.image
        selected = QRect(40, 20, 80, 50)
        self.brush.set_input_mask(rect_mask(selected))
        self.brush.brush_size = 24
        self.brush.hardness = 0.4
        self.brush.opacity = 0.9
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'input_mask')
        self.assert_changes_inside(image, initial_image, selected)

    def test_pattern_brush(self) -> None:
        """A fill pattern limits the stroke to the pattern's pixels."""
        self.brush.set_pattern_brush(QBrush(Qt.BrushStyle.DiagCrossPattern))
        self.brush.brush_size = 30
        self.brush.hardness = 0.6
        self.brush.opacity = 0.8
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'pattern')

    def test_stroke_crossing_layer_edges(self) -> None:
        """A stroke that leaves the layer and comes back."""
        self.brush.brush_size = 36
        self.brush.opacity = 0.9
        self.brush.hardness = 0.5
        self.brush.antialiasing = True
        points = (line_points(QPoint(60, 64), QPoint(-20, 64), 5)
                  + line_points(QPoint(-20, 64), QPoint(100, -15), 5)[1:]
                  + line_points(QPoint(100, -15), QPoint(210, 120), 5)[1:])
        image = self.stroke(points)
        self.assert_stroke_matches_golden(image, 'crossing_edges')

    def test_stroke_entirely_outside_layer_changes_nothing(self) -> None:
        """A stroke that never touches the layer leaves it unchanged."""
        image = self.stroke(line_points(QPoint(-100, -50), QPoint(-30, -40), 10))
        self.assert_images_equal(image, brush_test_pattern())

    def test_click_draws_one_point(self) -> None:
        """A single input point draws a dot."""
        self.brush.brush_size = 21
        self.brush.hardness = 0.4
        self.brush.antialiasing = True
        image = self.stroke([(50, 50)])
        self.assert_stroke_matches_golden(image, 'click')

    def test_strokes_across_opacity_gradient(self) -> None:
        """Soft strokes at partial opacity across an opacity gradient."""
        self.use_layer(opacity_gradient_image())
        self.brush.brush_size = 30
        self.brush.opacity = 0.6
        self.brush.hardness = 0.4
        self.brush.antialiasing = True
        self.stroke(line_points(QPoint(180, 30), QPoint(10, 30), 7))
        self.brush.brush_color = QColor(250, 240, 20, 180)
        image = self.stroke(line_points(QPoint(20, 120), QPoint(170, 75), 7))
        self.assert_stroke_matches_golden(image, 'opacity_gradient')

    def test_overlapping_segments_do_not_build_up(self) -> None:
        """Within one stroke, overlapping segments don't raise opacity past the brush opacity."""
        self.use_layer(create_transparent_image(LAYER_SIZE))
        self.brush.brush_size = 20
        self.brush.opacity = 0.5
        self.brush.hardness = 0.5
        self.brush.antialiasing = True
        image = self.stroke(zigzag_points())
        alpha = image_data_as_numpy_8bit(image)[:, :, 3]
        self.assertAlmostEqual(int(alpha.max()), 255 * 0.5, delta=1)

    def test_mid_stroke_draws_match_one_draw_at_end(self) -> None:
        """Drawing buffered input partway through a stroke doesn't change the result."""
        self.brush.brush_size = 26
        self.brush.opacity = 0.7
        self.brush.hardness = 0.4
        self.brush.antialiasing = True
        self.brush.pressure_opacity = True
        points: list[StrokePoint] = [(x, y, 0.3 + 0.7 * ((i % 5) / 4))
                                     for i, (x, y, *_) in enumerate(zigzag_points())]
        buffered_image = self.stroke(points)
        UndoStack().undo()
        self.assert_images_equal(self.layer.image, brush_test_pattern())
        flushed_image = self.stroke(points, flush_after_each_point=True)
        self.assert_images_equal(flushed_image, buffered_image)

    def test_undo_restores_layer(self) -> None:
        """Undoing a stroke restores the layer."""
        UndoStack().clear()
        image = self.stroke(zigzag_points())
        self.assertNotEqual(image, brush_test_pattern())
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assert_images_equal(self.layer.image, brush_test_pattern())

    def test_second_stroke_blends_over_first(self) -> None:
        """Overlap limiting applies within a stroke only: a second stroke over the first builds up opacity."""
        self.use_layer(create_transparent_image(LAYER_SIZE))
        self.brush.opacity = 0.5
        self.stroke(line_points(QPoint(20, 64), QPoint(170, 64), 10))
        first_alpha = int(image_data_as_numpy_8bit(self.layer.image)[64, 90, 3])
        image = self.stroke(line_points(QPoint(90, 10), QPoint(90, 120), 10))
        self.assertGreater(int(image_data_as_numpy_8bit(image)[64, 90, 3]), first_alpha)
