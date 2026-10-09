"""ShapeTool testing."""
from src.config.cache import Cache
from src.tools.shape_tool import ShapeTool
from test.tools.tool_test_case import ToolTestCase


class ShapeToolTest(ToolTestCase):
    """ShapeTool testing."""

    def setUp(self) -> None:
        super().setUp()
        self.shape_tool = ShapeTool(self.image_stack, self.image_viewer)
        self.tool_controller.add_tool(self.shape_tool)

    def test_inactive_tool_ignores_brush_color(self) -> None:
        """Brush color changes don't change the shape colors while the shape tool is inactive."""
        self.assertFalse(self.shape_tool.is_active)
        fill_color = Cache().get(Cache.SHAPE_TOOL_FILL_COLOR)
        line_color = Cache().get(Cache.SHAPE_TOOL_LINE_COLOR)
        Cache().set(Cache.LAST_BRUSH_COLOR, '#ff123456')
        self.assertEqual(Cache().get(Cache.SHAPE_TOOL_FILL_COLOR), fill_color)
        self.assertEqual(Cache().get(Cache.SHAPE_TOOL_LINE_COLOR), line_color)

    def test_active_tool_follows_brush_color(self) -> None:
        """Brush color changes propagate to the shape fill color while the shape tool is active."""
        self.activate_tool(self.shape_tool)
        Cache().set(Cache.LAST_BRUSH_COLOR, '#ff123456')
        self.assertEqual(Cache().get(Cache.SHAPE_TOOL_FILL_COLOR), '#ff123456')
