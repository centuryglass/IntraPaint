import unittest

from PySide6.QtCore import QPoint, Qt

from src.tools.mypaint_brush_tool import MyPaintBrushTool
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


if __name__ == '__main__':
    unittest.main()
