"""Tests that ruler guides never take input from the tools: a press-drag on a guide line does what the tool does."""
import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt

from src.tools.mypaint_brush_tool import MyPaintBrushTool
from src.tools.shape_selection_tool import ShapeSelectionTool
from test.tools.selection_tool_test_case import SelectionToolTestCase, rect_mask

HORIZONTAL = Qt.Orientation.Horizontal
VERTICAL = Qt.Orientation.Vertical


class GuideInputTest(SelectionToolTestCase):
    """Drives tools with presses starting exactly on a guide line."""

    INCLUDE_RULERS = True

    def setUp(self) -> None:
        super().setUp()
        guides = self.image_panel.guides
        assert guides is not None
        self.guides = guides
        self.guides.add(HORIZONTAL, 10)
        self.guides.add(VERTICAL, 12)

    def _assert_guides_unmoved(self) -> None:
        self.assertEqual(self.guides.positions(HORIZONTAL), [10])
        self.assertEqual(self.guides.positions(VERTICAL), [12])
        self.assertEqual([item.position for item in self.image_panel.guide_line_items], [10, 12])

    def test_rectangle_selection_drag_on_guide(self) -> None:
        """A rectangle selection drag that starts on a guide line selects the rectangle and leaves guides alone."""
        self.activate_tool(ShapeSelectionTool(self.image_stack, self.image_viewer))
        self.mouse_drag([QPoint(12, 10), QPoint(20, 20), QPoint(30, 25)])
        expected = rect_mask(self.IMAGE_SIZE, QRect(12, 10, 18, 15))
        self.assert_masks_equal(self.selection_mask(), expected)
        self._assert_guides_unmoved()

    def test_brush_stroke_on_guide(self) -> None:
        """A brush stroke along a guide line paints, and leaves guides alone."""
        brush_tool = MyPaintBrushTool(self.image_stack, self.image_viewer)
        self.tool_controller.add_tool(brush_tool)
        self.image_stack.active_layer = self.layer
        self.activate_tool(brush_tool)
        brush_tool.brush_size = 4
        before = self.layer.image
        self.mouse_drag([QPoint(5, 10), QPoint(25, 10), QPoint(40, 10)])
        self.assertNotEqual(self.layer.image, before)
        self.assertFalse(np.array_equal(self.selection_mask(), np.ones_like(self.selection_mask())))
        self._assert_guides_unmoved()
