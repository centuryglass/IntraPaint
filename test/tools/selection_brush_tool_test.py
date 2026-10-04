"""Tests the selection brush's right button: a click toggles a context pin, and a drag draws a 1px selection."""
from PySide6.QtCore import QPoint, Qt

from src.config.application_config import AppConfig
from src.tools.selection_brush_tool import SelectionBrushTool
from src.undo_stack import UndoStack
from test.tools.tool_test_case import ToolTestCase

RIGHT = Qt.MouseButton.RightButton


class SelectionBrushToolTest(ToolTestCase):
    """Drives SelectionBrushTool's right button with synthetic mouse input at 1:1 scale."""

    def setUp(self) -> None:
        super().setUp()
        AppConfig().set(AppConfig.UNDO_MERGE_INTERVAL, 0.0)
        self.image_stack.create_layer()
        self.tool = self.activate_tool(SelectionBrushTool(self.image_stack, self.image_viewer))
        self.selection_layer = self.image_stack.selection_layer
        UndoStack().clear()

    def test_right_click_adds_pin_without_selecting(self) -> None:
        """A right-click without movement adds a pin and selects nothing."""
        self.mouse_drag([QPoint(100, 100)], RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [QPoint(100, 100)])
        self.assertTrue(self.selection_layer.is_empty())
        self.assertEqual(UndoStack().undo_count(), 1)
        self.assertEqual(len(self.image_viewer._context_pin_items), 1)  # pylint: disable=protected-access

    def test_right_click_near_pin_removes_it(self) -> None:
        """A right-click within a few screen pixels of a pin removes that pin."""
        self.selection_layer.set_context_pins([QPoint(100, 100)])
        self.mouse_drag([QPoint(103, 102)], RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [])

    def test_small_jitter_still_toggles_pin(self) -> None:
        """Movement under the drag threshold still counts as a click."""
        self.mouse_drag([QPoint(100, 100), QPoint(101, 101), QPoint(102, 100)], RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [QPoint(100, 100)])
        self.assertTrue(self.selection_layer.is_empty())

    def test_right_drag_selects_1px_line_from_press_point(self) -> None:
        """A right-drag past the threshold draws a 1px line starting at the press point, and adds no pin."""
        self.tool.brush_size = 10
        self.mouse_drag([QPoint(100, 100), QPoint(110, 100), QPoint(130, 100)], RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [])
        image = self.selection_layer.image
        self.assertGreater(image.pixelColor(100, 100).alpha(), 0)
        self.assertGreater(image.pixelColor(120, 100).alpha(), 0)
        self.assertEqual(image.pixelColor(120, 102).alpha(), 0)
        self.assertEqual(self.tool.brush_size, 10)

    def test_left_click_selects(self) -> None:
        """The left button selects as before and adds no pin."""
        self.mouse_drag([QPoint(100, 100)])
        self.assertEqual(self.selection_layer.context_pins, [])
        self.assertFalse(self.selection_layer.is_empty())
