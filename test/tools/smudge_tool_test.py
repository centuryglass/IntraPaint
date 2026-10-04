"""Tests the smudge tool through synthetic mouse input."""
from PySide6.QtCore import QPoint

from src.config.cache import Cache
from src.tools.smudge_tool import SmudgeTool
from src.undo_stack import UndoStack
from test.image.brush.smudge_brush_test import smudge_test_pattern
from test.tools.tool_test_case import ToolTestCase

SMUDGE_TOOL_IMAGE_PATH = 'test/resources/test_images/smudge/smudge_tool_drag.png'


class SmudgeToolTest(ToolTestCase):
    """Smudge tool testing"""

    def setUp(self) -> None:
        super().setUp()
        self.smudge_tool = SmudgeTool(self.image_stack, self.image_viewer)
        self.tool_controller.add_tool(self.smudge_tool)
        self.layer = self.image_stack.create_layer(image_data=smudge_test_pattern(self.IMAGE_SIZE))
        self.image_stack.active_layer = self.layer
        self.activate_tool(self.smudge_tool)

    def test_cache_settings_reach_brush(self) -> None:
        """Smudge settings in the cache are applied to the brush."""
        cache = Cache()
        cache.set(Cache.SMUDGE_TOOL_BRUSH_SIZE, 33)
        cache.set(Cache.SMUDGE_TOOL_OPACITY, 0.35)
        cache.set(Cache.SMUDGE_TOOL_HARDNESS, 0.4)
        cache.set(Cache.SMUDGE_TOOL_ANTIALIAS, False)
        brush = self.smudge_tool.brush
        self.assertEqual(brush.brush_size, 33)
        self.assertAlmostEqual(brush.opacity, 0.35)
        self.assertAlmostEqual(brush.hardness, 0.4)
        self.assertFalse(brush.antialiasing)

    def test_drag_smudges_layer_as_one_undo_step(self) -> None:
        """A mouse drag smudges the active layer, and undoing it restores the layer."""
        Cache().set(Cache.SMUDGE_TOOL_BRUSH_SIZE, 40)
        initial_image = self.layer.image
        UndoStack().clear()
        self.mouse_drag([QPoint(60 + i * 12, 100 + i * 9) for i in range(30)])
        self.assertNotEqual(self.layer.image, initial_image)
        self.assert_image_matches_golden(self.layer.image, SMUDGE_TOOL_IMAGE_PATH)
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assert_images_equal(self.layer.image, initial_image)
