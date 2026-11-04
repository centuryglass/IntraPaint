"""Tests the draw tool through synthetic mouse input."""
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor

from src.config.cache import Cache
from src.config.config_entry import RangeKey
from src.tools.brush_tool import brush_size_step
from src.tools.draw_tool import DrawTool
from src.ui.input_fields.fill_style_combo_box import BRUSH_PATTERN_DENSE_4, BRUSH_PATTERN_SOLID
from src.undo_stack import UndoStack
from test.base_test_case import press_key
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

    def test_brush_size_stops_at_range_edges(self) -> None:
        """Size changes past either end of the size range stop at that end."""
        cache = Cache()
        minimum = cache.get(Cache.DRAW_TOOL_BRUSH_SIZE, RangeKey.MIN)
        maximum = cache.get(Cache.DRAW_TOOL_BRUSH_SIZE, RangeKey.MAX)
        self.draw_tool.set_brush_size(maximum + 50)
        self.assertEqual(cache.get(Cache.DRAW_TOOL_BRUSH_SIZE), maximum)
        self.assertEqual(self.draw_tool.brush_size, maximum)
        self.draw_tool.set_brush_size(minimum - 50)
        self.assertEqual(cache.get(Cache.DRAW_TOOL_BRUSH_SIZE), minimum)
        self.assertEqual(self.draw_tool.brush_size, minimum)

    def test_size_keys_step_in_proportion_to_the_size(self) -> None:
        """Brush size keys change small brushes by one pixel and larger brushes by a tenth of their size."""
        cache = Cache()
        cache.set(Cache.DRAW_TOOL_BRUSH_SIZE, 5)
        press_key(self.image_viewer, Qt.Key.Key_BracketRight)
        self.assertEqual(cache.get(Cache.DRAW_TOOL_BRUSH_SIZE), 6)
        cache.set(Cache.DRAW_TOOL_BRUSH_SIZE, 100)
        press_key(self.image_viewer, Qt.Key.Key_BracketRight)
        self.assertEqual(cache.get(Cache.DRAW_TOOL_BRUSH_SIZE), 110)
        press_key(self.image_viewer, Qt.Key.Key_BracketLeft)
        self.assertEqual(cache.get(Cache.DRAW_TOOL_BRUSH_SIZE), 99)

    def test_brush_size_step(self) -> None:
        """A step is one pixel below size 20 and a tenth of the size above it."""
        self.assertEqual([brush_size_step(size) for size in (1, 9, 19, 20, 99, 100, 250)], [1, 1, 1, 2, 9, 10, 25])

    def test_digit_keys_set_opacity(self) -> None:
        """Digit keys set the opacity to 10% through 100%, with 0 for 100%."""
        cache = Cache()
        for key, expected in ((Qt.Key.Key_3, 0.3), (Qt.Key.Key_7, 0.7), (Qt.Key.Key_0, 1.0), (Qt.Key.Key_1, 0.1)):
            with self.subTest(key=key):
                press_key(self.image_viewer, key)
                self.assertAlmostEqual(cache.get(Cache.DRAW_TOOL_OPACITY), expected)
                self.assertAlmostEqual(self.draw_tool.brush.opacity, expected)

    def test_digit_keys_leave_opacity_alone_while_canvas_is_hidden(self) -> None:
        """With the canvas hidden, as while the generated image selector replaces it, digits go to their other uses."""
        cache = Cache()
        cache.set(Cache.DRAW_TOOL_OPACITY, 0.55)
        self.image_viewer.hide()
        press_key(self.image_panel, Qt.Key.Key_5)
        self.assertAlmostEqual(cache.get(Cache.DRAW_TOOL_OPACITY), 0.55)

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
