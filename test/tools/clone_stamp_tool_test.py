"""Tests for the clone stamp tool's source marker."""
from PySide6.QtCore import QPoint, QPointF, Qt

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.tools.brush_tool import MIN_OUTLINE_DIAMETER
from src.tools.clone_stamp_tool import SOURCE_MODE_FIXED_OFFSET, SOURCE_MODE_STATIC, CloneStampTool
from src.ui.brush_crosshair import CrosshairVariant
from test.tools.tool_test_case import ToolTestCase


class CloneStampToolTest(ToolTestCase):
    """Checks that the source marker follows the source point, the brush size and the crosshair setting."""

    def setUp(self) -> None:
        super().setUp()
        Cache().set(Cache.CLONE_STAMP_TOOL_SOURCE_MODE, SOURCE_MODE_FIXED_OFFSET)
        self.tool = CloneStampTool(self.image_stack, self.image_viewer)
        self.tool_controller.add_tool(self.tool)
        self.image_stack.active_layer = self.image_stack.create_layer()

    def _hover(self, point: QPoint, brush_size: int = 40) -> None:
        self.activate_tool(self.tool)
        self.tool.brush_size = brush_size
        self.mouse_move(point, Qt.MouseButton.NoButton)

    def test_marker_hidden_unless_tool_active(self) -> None:
        """The marker shows while the tool is active and the pointer is over the viewer, and hides on deactivation."""
        self.assertFalse(self.tool._source_crosshair.isVisible())
        self._hover(QPoint(100, 100))
        self.assertTrue(self.tool._source_crosshair.isVisible())
        self.assertTrue(self.tool._source_outline.isVisible())
        self.tool.is_active = False
        self.assertFalse(self.tool._source_crosshair.isVisible())
        self.assertFalse(self.tool._source_outline.isVisible())

    def test_marker_follows_pointer_plus_offset(self) -> None:
        """In an offset mode the marker sits at the pointer position plus the offset, at the brush's size."""
        self._hover(QPoint(100, 100))
        self.tool.update_source_xy(QPoint(30, -20))
        self.mouse_move(QPoint(200, 150), Qt.MouseButton.NoButton)
        pointer = self.image_viewer.widget_point_to_scene(self.image_viewer.cursor_pos)
        self.assertEqual(self.tool._source_outline.pos(), pointer + QPointF(30, -20))
        self.assertEqual(self.tool._source_crosshair.pos(), pointer + QPointF(30, -20))
        self.assertEqual(self.tool._source_outline.diameter, 40)

    def test_marker_stays_at_fixed_position(self) -> None:
        """In Fixed position mode the marker stays on the source pixel as the pointer moves."""
        self._hover(QPoint(100, 100))
        Cache().set(Cache.CLONE_STAMP_TOOL_SOURCE_MODE, SOURCE_MODE_STATIC)
        self.tool.get_control_panel()
        Cache().set(Cache.CLONE_STAMP_TOOL_SOURCE_MODE, SOURCE_MODE_FIXED_OFFSET)
        Cache().set(Cache.CLONE_STAMP_TOOL_SOURCE_MODE, SOURCE_MODE_STATIC)
        self.tool.update_source_xy(QPoint(50, 60))
        for point in (QPoint(100, 100), QPoint(300, 200)):
            self.mouse_move(point, Qt.MouseButton.NoButton)
            self.assertEqual(self.tool._source_crosshair.pos(), QPointF(50.5, 60.5))

    def test_outline_hides_when_no_wider_than_crosshair(self) -> None:
        """Small brushes show the crosshair alone."""
        self._hover(QPoint(100, 100), brush_size=MIN_OUTLINE_DIAMETER)
        self.assertFalse(self.tool._source_outline.isVisible())
        self.assertTrue(self.tool._source_crosshair.isVisible())
        self.tool.brush_size = MIN_OUTLINE_DIAMETER + 1
        self.assertTrue(self.tool._source_outline.isVisible())

    def test_crosshair_variants_setting(self) -> None:
        """The marker's crosshair becomes the plain design when per-tool variants are off."""
        self._hover(QPoint(100, 100))
        self.assertEqual(self.tool._source_crosshair.variant, CrosshairVariant.CLONE_SOURCE)
        AppConfig().set(AppConfig.BRUSH_CROSSHAIR_VARIANTS, False)
        self.assertEqual(self.tool._source_crosshair.variant, CrosshairVariant.PLAIN)
        AppConfig().set(AppConfig.BRUSH_CROSSHAIR_VARIANTS, True)
        self.assertEqual(self.tool._source_crosshair.variant, CrosshairVariant.CLONE_SOURCE)
