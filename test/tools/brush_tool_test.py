import unittest

from PySide6.QtCore import QPoint, QRectF, Qt

from src.config.application_config import AppConfig
from src.tools.brush_tool import MIN_OUTLINE_DIAMETER
from src.tools.mypaint_brush_tool import MyPaintBrushTool
from src.ui.brush_crosshair import CrosshairVariant, crosshair_cursor
from src.undo_stack import UndoStack
from test.tools.tool_test_case import ToolTestCase

BRUSH_STROKE_IMAGE_PATH = 'test/resources/test_images/brush_test.png'
BRUSH_PATH = 'resources/brushes/classic/bulk.myb'


class BrushToolTest(ToolTestCase):
    """MyPaint brush tool testing"""

    def setUp(self) -> None:
        super().setUp()
        self.brush_tool = MyPaintBrushTool(self.image_stack, self.image_viewer)
        self.tool_controller.add_tool(self.brush_tool)
        self.brush = self.brush_tool._brush
        self.surface = self.brush._mp_surface
        self.tiles = self.surface._tiles
        self.pending_tiles = self.surface._pending_changed_tiles

    def test_activation_no_layers(self) -> None:
        self.assertEqual(self.image_stack.layer_stack.count, 0)
        self.assertFalse(self.brush_tool.is_active)
        self.activate_tool(self.brush_tool)
        self.assertIsNotNone(self.brush)
        self.assertIsNotNone(self.surface)
        self.assertEqual(len(self.tiles), 0)
        self.assertEqual(len(self.pending_tiles), 0)

    def test_activation_one_layer(self) -> None:
        # Create one layer, confirm that layer property assumptions are true:
        layer = self.image_stack.create_layer()
        self.image_stack.active_layer = layer
        self.assertFalse(self.brush_tool.is_active)

        # Activate brush tool, confirm that using the brush tool applies changes as expected:
        initial_image = layer.image

        self.activate_tool(self.brush_tool)
        self.assertFalse(layer.locked)
        self.assertFalse(layer.alpha_locked)
        self.assertFalse(layer.bounds.isEmpty())

        self.assertEqual(self.image_stack.active_layer, layer)
        self.assertEqual(self.brush_tool._layer, layer)
        self.assertEqual(self.brush._layer, layer)
        self.assertEqual(self.surface._layer, layer)
        self.assertEqual(self.surface.brush.color.alpha(), 255)
        self.assertGreater(self.brush_tool.brush_size, 1)
        self.brush_tool.brush_size = 50
        self.surface.brush.load_file(BRUSH_PATH)

        UndoStack().clear()
        self.assertEqual(0, UndoStack().undo_count())

        self.mouse_press(QPoint(50, 50))
        for xy in range(50, 150, 5):
            self.mouse_move(QPoint(xy, xy))
            if xy == 100:
                self.assertGreater(len(self.pending_tiles), 0)
                for tile in self.pending_tiles:
                    self.assertTrue(not tile.bounds.isEmpty())
                    self.assertIn(tile, self.tiles.values())
        self.mouse_release(QPoint(150, 150))
        self.assertEqual(len(self.pending_tiles), 0)
        self.assertGreater(len(self.tiles), 0)
        self.assertEqual(1, UndoStack().undo_count())

        final_image = layer.image
        self.assertNotEqual(initial_image, final_image)
        self.assert_image_matches_golden(final_image, BRUSH_STROKE_IMAGE_PATH)

    def test_activation_two_layer(self) -> None:
        # Create one layer, confirm that layer property assumptions are true:
        layer1 = self.image_stack.create_layer()
        layer2 = self.image_stack.create_layer()
        group = self.image_stack.create_layer_group('group')

        # Activate brush tool, confirm that it connects whenever an image layer is active, but not when a group is
        self.activate_tool(self.brush_tool)

        self.image_stack.active_layer = self.image_stack.layer_stack
        self.assertIsNone(self.brush_tool._layer)

        self.image_stack.active_layer = layer1
        self.assertEqual(layer1, self.brush_tool._layer)
        self.image_stack.active_layer = group
        self.assertIsNone(self.brush_tool._layer)
        self.image_stack.active_layer = layer2
        self.assertEqual(layer2, self.brush_tool._layer)

    def test_right_drag_does_not_draw(self) -> None:
        """The right mouse button doesn't draw, and leaves the brush size unchanged."""
        layer = self.image_stack.create_layer()
        self.image_stack.active_layer = layer
        self.activate_tool(self.brush_tool)
        self.brush_tool.brush_size = 20
        initial_image = layer.image
        UndoStack().clear()
        self.mouse_drag([QPoint(50, 50), QPoint(100, 100), QPoint(150, 150)], Qt.MouseButton.RightButton)
        self.assertEqual(layer.image, initial_image)
        self.assertEqual(UndoStack().undo_count(), 0)
        self.assertEqual(self.brush_tool.brush_size, 20)

    def _hover_with_layer(self, point: QPoint, brush_size: int = 40):
        """Activates the tool on a new layer, sets the brush size, and hovers over an image pixel."""
        layer = self.image_stack.create_layer()
        self.image_stack.active_layer = layer
        self.activate_tool(self.brush_tool)
        self.brush_tool.brush_size = brush_size
        self.mouse_move(point, Qt.MouseButton.NoButton)
        return layer

    def assert_outline_under(self, image_point: QPoint) -> None:
        """Asserts that the brush outline shows, centred within an image pixel and sized to the brush."""
        outline = self.brush_tool.brush_outline
        self.assertTrue(outline.isVisible())
        self.assertTrue(QRectF(image_point.toPointF(), image_point.toPointF() + QPoint(1, 1)).contains(outline.pos()),
                        f'outline at {outline.pos().toTuple()}, cursor over pixel {image_point.toTuple()}')
        self.assertEqual(outline.diameter, self.brush_tool.brush_size)

    def test_cursor_is_crosshair(self) -> None:
        """The active brush tool uses its crosshair variant's cursor."""
        self._hover_with_layer(QPoint(100, 100))
        self.assertIs(self.brush_tool.cursor,
                      crosshair_cursor(self.brush_tool.crosshair_variant, self.image_viewer.devicePixelRatioF()))

    def test_crosshair_variants_setting_falls_back_to_plain(self) -> None:
        """Turning off per-tool crosshair variants uses the plain crosshair for every brush tool."""
        self._hover_with_layer(QPoint(100, 100))
        self.assertIs(self.brush_tool.cursor,
                      crosshair_cursor(self.brush_tool.crosshair_variant, self.image_viewer.devicePixelRatioF()))
        AppConfig().set(AppConfig.BRUSH_CROSSHAIR_VARIANTS, False)
        self.assertIs(self.brush_tool.cursor,
                      crosshair_cursor(CrosshairVariant.PLAIN, self.image_viewer.devicePixelRatioF()))
        AppConfig().set(AppConfig.BRUSH_CROSSHAIR_VARIANTS, True)
        self.assertIs(self.brush_tool.cursor,
                      crosshair_cursor(self.brush_tool.crosshair_variant, self.image_viewer.devicePixelRatioF()))

    def test_outline_follows_cursor_at_brush_size(self) -> None:
        """The outline appears under the hovered pixel at the brush's scene size, and follows the cursor."""
        self.assertFalse(self.brush_tool.brush_outline.isVisible())
        self._hover_with_layer(QPoint(100, 100))
        self.assert_outline_under(QPoint(100, 100))
        self.mouse_move(QPoint(300, 200), Qt.MouseButton.NoButton)
        self.assert_outline_under(QPoint(300, 200))
        self.brush_tool.brush_size = 90
        self.assert_outline_under(QPoint(300, 200))

    def test_outline_keeps_brush_size_across_zoom(self) -> None:
        """At every zoom level the outline's scene diameter is the brush size, centred under the cursor."""
        self._hover_with_layer(QPoint(256, 256))
        for scale in (0.5, 2.0, 4.0):
            with self.subTest(scale=scale):
                self.image_viewer.scene_scale = scale
                self.mouse_move(QPoint(256, 256), Qt.MouseButton.NoButton)
                self.assert_outline_under(QPoint(256, 256))
                outline = self.brush_tool.brush_outline
                self.assertEqual(outline.pos(), self.image_viewer.widget_point_to_scene(self.image_viewer.cursor_pos))

    def test_outline_hides_when_no_wider_than_crosshair(self) -> None:
        """The outline hides once the brush is no wider on screen than the crosshair, and returns above that."""
        self._hover_with_layer(QPoint(100, 100), brush_size=MIN_OUTLINE_DIAMETER)
        self.assertFalse(self.brush_tool.brush_outline.isVisible())
        self.brush_tool.brush_size = MIN_OUTLINE_DIAMETER + 1
        self.assertTrue(self.brush_tool.brush_outline.isVisible())
        self.image_viewer.scene_scale = 0.5
        self.assertFalse(self.brush_tool.brush_outline.isVisible())

    def test_outline_hides_while_input_is_disabled(self) -> None:
        """Locking the layer shows the disabled cursor and hides the outline; unlocking restores both."""
        layer = self._hover_with_layer(QPoint(100, 100))
        layer.locked = True
        self.assertTrue(self.brush_tool.cursor_disabled)
        self.assertFalse(self.brush_tool.brush_outline.isVisible())
        layer.locked = False
        self.assertFalse(self.brush_tool.cursor_disabled)
        self.assert_outline_under(QPoint(100, 100))

    def test_outline_hides_on_leave_and_deactivate(self) -> None:
        """The outline hides when the cursor leaves the viewer, and when the tool stops being active."""
        self._hover_with_layer(QPoint(100, 100))
        self.image_viewer.set_cursor_pos(None)
        self.assertFalse(self.brush_tool.brush_outline.isVisible())
        self.mouse_move(QPoint(100, 100), Qt.MouseButton.NoButton)
        self.assertTrue(self.brush_tool.brush_outline.isVisible())
        self.brush_tool.is_active = False
        self.assertFalse(self.brush_tool.brush_outline.isVisible())
        self.mouse_move(QPoint(120, 100), Qt.MouseButton.NoButton)
        self.assertFalse(self.brush_tool.brush_outline.isVisible())


if __name__ == '__main__':
    unittest.main()
