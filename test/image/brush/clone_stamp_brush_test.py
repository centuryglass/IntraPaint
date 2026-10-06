"""Tests CloneStampBrush output in both source modes against golden images, and checks properties that must hold for
   any clone stroke."""
import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QImage

from src.image.brush.clone_stamp_brush import CloneStampBrush
from src.image.layers.image_layer import ImageLayer
from src.undo_stack import UndoStack
from src.util.visual.image_utils import image_data_as_numpy_8bit, NpUInt8Array
from test.image.brush.brush_test_case import BrushTestCase, StrokePoint, brush_test_pattern, \
    opacity_gradient_image, line_points, rect_mask
from test.image.brush.qt_paint_brush_test import zigzag_points

GOLDEN_DIR = 'test/resources/test_images/clone_stamp'

# Source offset for offset-mode strokes, keeping the zigzag's source region inside the layer:
SOURCE_OFFSET = QPoint(15, 25)
# Fixed source point at the corner of brush_test_pattern's transparent and half-transparent bands:
SOURCE_POS = QPoint(124, 100)


def offset_source(initial_image: QImage, offset: QPoint) -> NpUInt8Array:
    """Returns the pixels an offset-mode clone copies into each layer position: the initial image shifted by -offset,
       transparent where the source position is outside the layer."""
    np_initial = image_data_as_numpy_8bit(initial_image)
    height, width = np_initial.shape[:2]
    shifted = np.zeros_like(np_initial)
    dst_x0, dst_y0 = max(0, -offset.x()), max(0, -offset.y())
    dst_x1, dst_y1 = min(width, width - offset.x()), min(height, height - offset.y())
    if dst_x0 < dst_x1 and dst_y0 < dst_y1:
        shifted[dst_y0:dst_y1, dst_x0:dst_x1] = np_initial[dst_y0 + offset.y():dst_y1 + offset.y(),
                                                           dst_x0 + offset.x():dst_x1 + offset.x()]
    return shifted


def changed_pixels(image: QImage, initial_image: QImage) -> np.ndarray:
    """Returns a boolean array marking each pixel that differs between two images."""
    return np.any(image_data_as_numpy_8bit(image) != image_data_as_numpy_8bit(initial_image), axis=2)


class CloneStampBrushTest(BrushTestCase):
    """Drives CloneStampBrush directly on an ImageLayer, configured as CloneStampTool configures it."""

    brush: CloneStampBrush

    def setUp(self) -> None:
        super().setUp()
        self.layer = ImageLayer(brush_test_pattern(), 'clone stamp test layer')
        self.brush = CloneStampBrush(self.layer)
        self.brush.brush_size = 16
        self.brush.opacity = 1.0
        self.brush.hardness = 1.0
        self.brush.antialiasing = False
        self.brush.pressure_size = True
        self.brush.pressure_opacity = False
        self.brush.pressure_hardness = False
        self.brush.source_offset = SOURCE_OFFSET

    def assert_stroke_matches_golden(self, image: QImage, golden_name: str) -> None:
        """Checks that a stroke left only valid premultiplied pixels, then compares it with its golden image."""
        self.assert_valid_premultiplied(image)
        self.assert_image_matches_golden(image, f'{GOLDEN_DIR}/{golden_name}.png')

    def use_soft_brush(self) -> None:
        """Sets up a soft, translucent, antialiased brush."""
        self.brush.brush_size = 30
        self.brush.opacity = 0.7
        self.brush.hardness = 0.3
        self.brush.antialiasing = True

    def stroke_soft(self, points: list[StrokePoint]) -> QImage:
        """Draws a stroke with use_soft_brush settings and returns the layer image."""
        self.use_soft_brush()
        return self.stroke(points)

    def test_source_offset_and_source_pos_replace_each_other(self) -> None:
        """Each source property reads back what was set, and setting one clears the other."""
        self.brush.source_offset = QPoint(3, -4)
        self.assertEqual(self.brush.source_offset, QPoint(3, -4))
        self.assertIsNone(self.brush.source_pos)
        self.brush.source_pos = QPoint(10, 20)
        self.assertEqual(self.brush.source_pos, QPoint(10, 20))
        self.assertIsNone(self.brush.source_offset)
        self.brush.source_offset = QPoint(-5, 6)
        self.assertEqual(self.brush.source_offset, QPoint(-5, 6))
        self.assertIsNone(self.brush.source_pos)

    # Source offset mode:

    def test_offset_hard_stroke(self) -> None:
        """A hard, opaque offset-mode stroke copies pre-stroke content from the source offset, even where it crosses
           pixels it already changed."""
        initial_image = brush_test_pattern()
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'offset_hard')
        changed = changed_pixels(image, initial_image)
        self.assertTrue(np.any(changed))
        expected = offset_source(initial_image, SOURCE_OFFSET)
        np.testing.assert_array_equal(image_data_as_numpy_8bit(image)[changed], expected[changed])

    def test_offset_soft_stroke(self) -> None:
        """A soft, translucent, antialiased offset-mode stroke, crossing itself."""
        image = self.stroke_soft(zigzag_points())
        self.assert_stroke_matches_golden(image, 'offset_soft')

    def test_offset_source_partly_outside_layer(self) -> None:
        """Where the source offset points outside the layer, a hard stroke clears pixels to transparent."""
        offset = QPoint(-40, 0)
        self.brush.source_offset = offset
        initial_image = brush_test_pattern()
        image = self.stroke(line_points(QPoint(15, 40), QPoint(100, 70), 8))
        self.assert_stroke_matches_golden(image, 'offset_source_partly_outside')
        changed = changed_pixels(image, initial_image)
        np_image = image_data_as_numpy_8bit(image)
        np.testing.assert_array_equal(np_image[changed], offset_source(initial_image, offset)[changed])
        self.assertTrue(np.any(np_image[:, :40][changed[:, :40]][:, 3] == 0))
        self.assertTrue(np.any(np_image[:, 40:][changed[:, 40:]][:, 3] > 0))

    def test_offset_source_wholly_outside_layer(self) -> None:
        """With the whole source region outside the layer, a hard stroke clears every pixel it covers."""
        self.brush.source_offset = QPoint(0, -300)
        initial_image = brush_test_pattern()
        image = self.stroke(zigzag_points())
        changed = changed_pixels(image, initial_image)
        self.assertTrue(np.any(changed))
        self.assertFalse(np.any(image_data_as_numpy_8bit(image)[changed]))
        self.assertEqual(image_data_as_numpy_8bit(image)[60, 170, 3], 0)

    def test_zero_offset_changes_nothing(self) -> None:
        """An offset of zero clones nothing."""
        self.brush.source_offset = QPoint()
        image = self.stroke(zigzag_points())
        self.assert_images_equal(image, brush_test_pattern())

    def test_offset_stroke_reaches_final_point(self) -> None:
        """An offset-mode stroke clones the whole brush area around its final point."""
        initial_image = brush_test_pattern()
        image = self.stroke(line_points(QPoint(40, 60), QPoint(100, 60), 20))
        expected = offset_source(initial_image, SOURCE_OFFSET)
        np_image = image_data_as_numpy_8bit(image)
        np.testing.assert_array_equal(np_image[58:62, 100:106], expected[58:62, 100:106])

    # Fixed source point mode:

    def test_fixed_source_hard_stroke(self) -> None:
        """A hard, opaque fixed-source stroke stamps the same source patch along the stroke."""
        self.brush.source_pos = SOURCE_POS
        image = self.stroke(zigzag_points())
        self.assert_stroke_matches_golden(image, 'fixed_hard')

    def test_fixed_source_soft_stroke(self) -> None:
        """A soft, translucent, antialiased fixed-source stroke, crossing itself."""
        self.brush.source_pos = SOURCE_POS
        image = self.stroke_soft(zigzag_points())
        self.assert_stroke_matches_golden(image, 'fixed_soft')

    def test_fixed_source_stamps_patch_at_first_point(self) -> None:
        """The first stamp of a fixed-source stroke copies the source patch, aligned with the first point."""
        self.brush.source_pos = QPoint(30, 30)
        initial_image = brush_test_pattern()
        image = self.stroke([(40, 60)])
        np_image = image_data_as_numpy_8bit(image)
        np_initial = image_data_as_numpy_8bit(initial_image)
        changed = changed_pixels(image, initial_image)
        self.assertTrue(np.any(changed))
        np.testing.assert_array_equal(np_image[52:68, 32:48][changed[52:68, 32:48]],
                                      np_initial[22:38, 22:38][changed[52:68, 32:48]])
        self.assertFalse(np.any(changed[:52]) or np.any(changed[68:]) or np.any(changed[:, :32])
                         or np.any(changed[:, 48:]))

    @pytest.mark.xfail(strict=True, reason='https://github.com/centuryglass/IntraPaint/issues/114: fixed-source '
                                          'interpolation excludes each segment\'s end point, so the final input point '
                                          'of a stroke is never stamped')
    def test_fixed_source_stroke_reaches_final_point(self) -> None:
        """A fixed-source stroke stamps the source patch at its final point."""
        self.brush.source_pos = QPoint(30, 30)
        initial_image = brush_test_pattern()
        image = self.stroke(line_points(QPoint(40, 60), QPoint(100, 60), 20))
        np_image = image_data_as_numpy_8bit(image)
        np_initial = image_data_as_numpy_8bit(initial_image)
        np.testing.assert_array_equal(np_image[58:62, 92:106], np_initial[28:32, 22:36])

    def test_fixed_source_partly_outside_layer(self) -> None:
        """A fixed source point near the top edge stamps a patch that is transparent above the layer."""
        self.brush.source_pos = QPoint(100, 6)
        self.brush.brush_size = 24
        image = self.stroke(line_points(QPoint(30, 40), QPoint(160, 80), 8))
        self.assert_stroke_matches_golden(image, 'fixed_source_partly_outside')
        changed = changed_pixels(image, brush_test_pattern())
        alpha = image_data_as_numpy_8bit(image)[:, :, 3]
        self.assertTrue(np.any(alpha[changed] == 0))
        self.assertTrue(np.any(alpha[changed] == 255))

    def test_fixed_source_wholly_outside_layer(self) -> None:
        """With the whole source patch outside the layer, a hard fixed-source stroke clears every pixel it covers."""
        self.brush.source_pos = QPoint(-100, -100)
        initial_image = brush_test_pattern()
        image = self.stroke(zigzag_points())
        changed = changed_pixels(image, initial_image)
        self.assertTrue(np.any(changed))
        self.assertFalse(np.any(image_data_as_numpy_8bit(image)[changed]))
        self.assertEqual(image_data_as_numpy_8bit(image)[60, 160, 3], 0)

    # Both modes:

    def gradient_strokes(self) -> QImage:
        """Draws soft clone strokes across an opacity gradient in both directions, and returns the layer image."""
        self.use_layer(opacity_gradient_image())
        self.use_soft_brush()
        self.stroke(line_points(QPoint(180, 30), QPoint(20, 30), 7))
        self.brush.opacity = 0.4
        return self.stroke(line_points(QPoint(20, 90), QPoint(170, 60), 7))

    def test_offset_strokes_across_opacity_gradient(self) -> None:
        """Soft offset-mode strokes copy between pixels of different opacity."""
        self.brush.source_offset = QPoint(-30, 20)
        image = self.gradient_strokes()
        self.assert_stroke_matches_golden(image, 'offset_opacity_gradient')

    def test_fixed_source_strokes_across_opacity_gradient(self) -> None:
        """Soft fixed-source strokes stamp a partly transparent patch over pixels of varying opacity."""
        self.brush.source_pos = QPoint(60, 100)
        image = self.gradient_strokes()
        self.assert_stroke_matches_golden(image, 'fixed_opacity_gradient')

    def masked_stroke(self) -> tuple[QImage, QImage, QRect]:
        """Draws a soft stroke with an input mask, and returns the initial image, the result, and the masked area."""
        initial_image = self.layer.image
        selected = QRect(40, 20, 80, 50)
        self.brush.set_input_mask(rect_mask(selected))
        self.brush.brush_size = 24
        self.brush.hardness = 0.4
        self.brush.opacity = 0.9
        image = self.stroke(zigzag_points())
        return initial_image, image, selected

    def test_offset_input_mask_restricts_changes(self) -> None:
        """Offset-mode cloning stays inside the input mask."""
        initial_image, image, selected = self.masked_stroke()
        self.assert_stroke_matches_golden(image, 'offset_input_mask')
        self.assert_changes_inside(image, initial_image, selected)

    def test_fixed_source_input_mask_restricts_changes(self) -> None:
        """Fixed-source cloning stays inside the input mask."""
        self.brush.source_pos = SOURCE_POS
        initial_image, image, selected = self.masked_stroke()
        self.assert_stroke_matches_golden(image, 'fixed_input_mask')
        self.assert_changes_inside(image, initial_image, selected)

    def assert_stroke_is_one_undo_step(self) -> None:
        """Draws a stroke, checking that it is one undo step and that undoing it restores the layer."""
        UndoStack().clear()
        self.use_soft_brush()
        image = self.stroke(zigzag_points())
        self.assertNotEqual(image, brush_test_pattern())
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assert_images_equal(self.layer.image, brush_test_pattern())

    def test_offset_undo_restores_layer(self) -> None:
        """Each offset-mode stroke is one undo step."""
        self.assert_stroke_is_one_undo_step()

    def test_fixed_source_undo_restores_layer(self) -> None:
        """Each fixed-source stroke is one undo step."""
        self.brush.source_pos = SOURCE_POS
        self.assert_stroke_is_one_undo_step()

    def assert_mid_stroke_draws_match_one_draw_at_end(self) -> None:
        """Checks that drawing buffered input after every point gives the same result as one draw at the end."""
        self.use_soft_brush()
        points = zigzag_points()
        buffered_image = self.stroke(points)
        UndoStack().undo()
        self.assert_images_equal(self.layer.image, brush_test_pattern())
        flushed_image = self.stroke(points, flush_after_each_point=True)
        self.assert_images_equal(flushed_image, buffered_image)

    def test_offset_mid_stroke_draws_match_one_draw_at_end(self) -> None:
        """Offset-mode output doesn't depend on when buffered input is drawn."""
        self.assert_mid_stroke_draws_match_one_draw_at_end()

    def test_fixed_source_mid_stroke_draws_match_one_draw_at_end(self) -> None:
        """Fixed-source output doesn't depend on when buffered input is drawn."""
        self.brush.source_pos = SOURCE_POS
        self.assert_mid_stroke_draws_match_one_draw_at_end()
