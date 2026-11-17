"""ShapeTool testing."""
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor

from src.config.cache import Cache
from src.controller import color_controller
from src.tools.shape_tool import ShapeTool
from src.util.visual.shape_mode import ShapeMode
from test.tools.tool_test_case import ToolTestCase

FOREGROUND = '#ff112233'
BACKGROUND = '#ff445566'
CUSTOM_LINE = '#ff778899'
CUSTOM_FILL = '#ffaabbcc'


class ShapeToolTest(ToolTestCase):
    """ShapeTool testing."""

    def setUp(self) -> None:
        super().setUp()
        self.shape_tool = ShapeTool(self.image_stack, self.image_viewer)
        self.tool_controller.add_tool(self.shape_tool)
        Cache().set(Cache.SHAPE_TOOL_MODE, ShapeMode.RECTANGLE.name)
        Cache().set(Cache.SHAPE_TOOL_LINE_WIDTH, 4)
        Cache().set(Cache.SHAPE_TOOL_ANTIALIAS, False)
        Cache().set(Cache.LAST_BRUSH_COLOR, FOREGROUND)
        Cache().set(Cache.BACKGROUND_COLOR, BACKGROUND)
        Cache().set(Cache.SHAPE_TOOL_LINE_COLOR, CUSTOM_LINE)
        Cache().set(Cache.SHAPE_TOOL_FILL_COLOR, CUSTOM_FILL)

    def _draw_shape(self) -> tuple[QColor, QColor]:
        """Draws a rectangle on a new layer, then returns the colors of an outline pixel and an interior pixel."""
        layer = self.image_stack.create_layer()
        self.image_stack.active_layer = layer
        self.activate_tool(self.shape_tool)
        self.mouse_drag([QPoint(100, 100), QPoint(300, 300)])
        image = layer.image
        return QColor(image.pixel(200, 100)), QColor(image.pixel(200, 200))

    def test_default_sources(self) -> None:
        """A fresh configuration outlines with the foreground color and fills with the background color."""
        self.assertEqual(Cache().get(Cache.SHAPE_TOOL_LINE_SOURCE), color_controller.SOURCE_FOREGROUND)
        self.assertEqual(Cache().get(Cache.SHAPE_TOOL_FILL_SOURCE), color_controller.SOURCE_BACKGROUND)
        line, fill = self._draw_shape()
        self.assertEqual(line, QColor(FOREGROUND))
        self.assertEqual(fill, QColor(BACKGROUND))

    def test_custom_sources(self) -> None:
        """The custom line and fill colors are used when their sources are custom."""
        Cache().set(Cache.SHAPE_TOOL_LINE_SOURCE, color_controller.SOURCE_CUSTOM)
        Cache().set(Cache.SHAPE_TOOL_FILL_SOURCE, color_controller.SOURCE_CUSTOM)
        line, fill = self._draw_shape()
        self.assertEqual(line, QColor(CUSTOM_LINE))
        self.assertEqual(fill, QColor(CUSTOM_FILL))

    def test_foreground_fill_source(self) -> None:
        """The fill follows the foreground color when its source is the foreground color."""
        Cache().set(Cache.SHAPE_TOOL_FILL_SOURCE, color_controller.SOURCE_FOREGROUND)
        _, fill = self._draw_shape()
        self.assertEqual(fill, QColor(FOREGROUND))

    def test_color_changes_follow_sources(self) -> None:
        """Changing the foreground or background color updates the shape colors that use them."""
        self.activate_tool(self.shape_tool)
        color_controller.set_foreground(QColor('#ff010203'), commit=False)
        color_controller.set_background(QColor('#ff040506'), commit=False)
        line, fill = self._draw_shape()
        self.assertEqual(line, QColor('#ff010203'))
        self.assertEqual(fill, QColor('#ff040506'))

    def test_brush_color_leaves_shape_colors_alone(self) -> None:
        """Brush color changes never write the shape tool's custom colors, active or not."""
        for active in (False, True):
            if active:
                self.activate_tool(self.shape_tool)
            self.assertEqual(self.shape_tool.is_active, active)
            Cache().set(Cache.LAST_BRUSH_COLOR, '#ff123456')
            self.assertEqual(Cache().get(Cache.SHAPE_TOOL_FILL_COLOR), CUSTOM_FILL)
            self.assertEqual(Cache().get(Cache.SHAPE_TOOL_LINE_COLOR), CUSTOM_LINE)
