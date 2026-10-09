"""Tests the eraser tool through synthetic mouse input."""
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor

from src.config.cache import Cache
from src.tools.eraser_tool import EraserTool
from src.undo_stack import UndoStack
from test.image.brush.brush_test_case import brush_test_pattern
from test.tools.tool_test_case import ToolTestCase

ERASER_TOOL_IMAGE_PATH = 'test/resources/test_images/qt_paint_brush/eraser_tool_drag.png'


class EraserToolTest(ToolTestCase):
    """Eraser tool testing"""

    def setUp(self) -> None:
        super().setUp()
        self.eraser_tool = EraserTool(self.image_stack, self.image_viewer)
        self.tool_controller.add_tool(self.eraser_tool)
        self.layer = self.image_stack.create_layer(image_data=brush_test_pattern(self.IMAGE_SIZE))
        self.image_stack.active_layer = self.layer
        self.activate_tool(self.eraser_tool)

    def test_cache_settings_reach_brush(self) -> None:
        """Eraser tool settings in the cache are applied to the brush, and the brush color doesn't follow the draw
           color."""
        cache = Cache()
        cache.set(Cache.ERASER_TOOL_SIZE, 33)
        cache.set(Cache.ERASER_TOOL_OPACITY, 0.35)
        cache.set(Cache.ERASER_TOOL_HARDNESS, 0.4)
        cache.set(Cache.ERASER_TOOL_ANTIALIAS, False)
        cache.set(Cache.ERASER_TOOL_PRESSURE_OPACITY, True)
        brush = self.eraser_tool.brush
        initial_color = brush.brush_color
        cache.set(Cache.LAST_BRUSH_COLOR, QColor(255, 0, 0, 40).name(QColor.NameFormat.HexArgb))
        self.assertTrue(brush.eraser)
        self.assertEqual(brush.brush_size, 33)
        self.assertAlmostEqual(brush.opacity, 0.35)
        self.assertAlmostEqual(brush.hardness, 0.4)
        self.assertFalse(brush.antialiasing)
        self.assertTrue(brush.pressure_opacity)
        self.assertEqual(brush.brush_color, initial_color)
        self.assertEqual(brush.brush_color.alpha(), 255)

    def test_drag_erases_layer_as_one_undo_step(self) -> None:
        """A mouse drag erases from the active layer, and undoing it restores the layer."""
        cache = Cache()
        cache.set(Cache.ERASER_TOOL_SIZE, 40)
        cache.set(Cache.ERASER_TOOL_OPACITY, 0.7)
        cache.set(Cache.ERASER_TOOL_HARDNESS, 0.5)
        initial_image = self.layer.image
        UndoStack().clear()
        self.mouse_drag([QPoint(60 + i * 12, 100 + i * 9) for i in range(30)])
        self.assertNotEqual(self.layer.image, initial_image)
        self.assert_image_matches_golden(self.layer.image, ERASER_TOOL_IMAGE_PATH)
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assert_images_equal(self.layer.image, initial_image)
