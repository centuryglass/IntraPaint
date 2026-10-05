"""Tests the draw tool through synthetic mouse input."""
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor

from src.config.cache import Cache
from src.tools.draw_tool import DrawTool
from src.ui.input_fields.fill_style_combo_box import BRUSH_PATTERN_DENSE_4, BRUSH_PATTERN_SOLID
from src.undo_stack import UndoStack
from test.image.brush.brush_test_case import brush_test_pattern
from test.tools.tool_test_case import ToolTestCase

DRAW_TOOL_IMAGE_PATH = 'test/resources/test_images/qt_paint_brush/draw_tool_drag.png'


class DrawToolTest(ToolTestCase):
    """Draw tool testing"""

    def setUp(self) -> None:
        super().setUp()
        self.draw_tool = DrawTool(self.image_stack, self.image_viewer)
        self.tool_controller.add_tool(self.draw_tool)
        self.layer = self.image_stack.create_layer(image_data=brush_test_pattern(self.IMAGE_SIZE))
        self.image_stack.active_layer = self.layer
        self.activate_tool(self.draw_tool)

    def test_cache_settings_reach_brush(self) -> None:
        """Draw tool settings in the cache are applied to the brush."""
        cache = Cache()
        cache.set(Cache.DRAW_TOOL_BRUSH_SIZE, 33)
        cache.set(Cache.DRAW_TOOL_OPACITY, 0.35)
        cache.set(Cache.DRAW_TOOL_HARDNESS, 0.4)
        cache.set(Cache.DRAW_TOOL_ANTIALIAS, False)
        cache.set(Cache.DRAW_TOOL_PRESSURE_OPACITY, True)
        cache.set(Cache.DRAW_TOOL_BRUSH_PATTERN, BRUSH_PATTERN_DENSE_4)
        cache.set(Cache.LAST_BRUSH_COLOR, QColor(Qt.GlobalColor.red).name(QColor.NameFormat.HexArgb))
        brush = self.draw_tool.brush
        self.assertEqual(brush.brush_size, 33)
        self.assertAlmostEqual(brush.opacity, 0.35)
        self.assertAlmostEqual(brush.hardness, 0.4)
        self.assertFalse(brush.antialiasing)
        self.assertTrue(brush.pressure_opacity)
        self.assertEqual(brush._pattern_brush.style(), Qt.BrushStyle.Dense4Pattern)  # pylint: disable=protected-access
        self.assertEqual(brush.brush_color, QColor(Qt.GlobalColor.red))
        cache.set(Cache.DRAW_TOOL_BRUSH_PATTERN, BRUSH_PATTERN_SOLID)
        self.assertIsNone(brush._pattern_brush)  # pylint: disable=protected-access

    def test_drag_draws_on_layer_as_one_undo_step(self) -> None:
        """A mouse drag draws on the active layer, and undoing it restores the layer."""
        cache = Cache()
        cache.set(Cache.DRAW_TOOL_BRUSH_SIZE, 40)
        cache.set(Cache.DRAW_TOOL_OPACITY, 0.7)
        cache.set(Cache.DRAW_TOOL_HARDNESS, 0.5)
        cache.set(Cache.LAST_BRUSH_COLOR, '#ff1e5ac8')
        initial_image = self.layer.image
        UndoStack().clear()
        self.mouse_drag([QPoint(60 + i * 12, 100 + i * 9) for i in range(30)])
        self.assertNotEqual(self.layer.image, initial_image)
        self.assert_image_matches_golden(self.layer.image, DRAW_TOOL_IMAGE_PATH)
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assert_images_equal(self.layer.image, initial_image)
