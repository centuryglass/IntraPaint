"""Tests the selection brush's right button, which adds, moves and removes context pins."""
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

    def _marker_head_offset(self) -> int:
        """Returns how many image pixels above a pin, at 1:1 scale, its drawn marker's head is."""
        return round(self.image_viewer.context_pin_marker_size * 0.6)

    def test_right_click_adds_pin_without_selecting(self) -> None:
        """A right-click away from every pin adds a pin there, selects nothing, and records one undo step."""
        self.mouse_drag([QPoint(100, 100)], RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [QPoint(100, 100)])
        self.assertTrue(self.selection_layer.is_empty())
        self.assertEqual(UndoStack().undo_count(), 1)
        self.assertEqual(len(self.image_viewer._context_pin_items), 1)  # pylint: disable=protected-access

    def test_right_click_on_pin_removes_it(self) -> None:
        """A right-click on a pin's needle tip removes the pin, as one undo step."""
        self.selection_layer.set_context_pins([QPoint(100, 100)], False)
        self.mouse_drag([QPoint(101, 99)], RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [])
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assertEqual(self.selection_layer.context_pins, [QPoint(100, 100)])

    def test_right_click_on_marker_head_removes_pin(self) -> None:
        """Right-clicking the drawn marker's head, well above the pinned pixel, removes the pin."""
        self.selection_layer.set_context_pins([QPoint(100, 100)], False)
        self.mouse_drag([QPoint(100, 100 - self._marker_head_offset())], RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [])

    def test_small_jitter_on_pin_still_removes_it(self) -> None:
        """Movement under the drag threshold still counts as a click on an existing pin."""
        self.selection_layer.set_context_pins([QPoint(100, 100)], False)
        self.mouse_drag([QPoint(100, 100), QPoint(101, 101), QPoint(102, 100)], RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [])

    def test_drag_new_pin(self) -> None:
        """A right-drag away from every pin adds a pin that follows the pointer, as one undo step."""
        self.mouse_drag([QPoint(100, 100), QPoint(110, 105), QPoint(130, 120)], RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [QPoint(130, 120)])
        self.assertTrue(self.selection_layer.is_empty())
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assertEqual(self.selection_layer.context_pins, [])

    def test_drag_existing_pin(self) -> None:
        """A right-drag from a pin moves it, as one undo step, and leaves other pins alone."""
        self.selection_layer.set_context_pins([QPoint(100, 100), QPoint(300, 300)], False)
        self.mouse_drag([QPoint(100, 100), QPoint(120, 110), QPoint(150, 120)], RIGHT)
        self.assertCountEqual(self.selection_layer.context_pins, [QPoint(300, 300), QPoint(150, 120)])
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assertEqual(self.selection_layer.context_pins, [QPoint(100, 100), QPoint(300, 300)])

    def test_drag_by_marker_head_keeps_grab_offset(self) -> None:
        """A pin grabbed by its marker's head moves with the pointer, without jumping to it."""
        head_offset = self._marker_head_offset()
        self.selection_layer.set_context_pins([QPoint(100, 100)], False)
        self.mouse_drag([QPoint(100, 100 - head_offset), QPoint(115, 100 - head_offset),
                         QPoint(130, 110 - head_offset)], RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [QPoint(130, 110)])

    def test_pin_hides_off_image_and_returns(self) -> None:
        """While dragged outside the image, the pin is removed, and it comes back when the pointer returns."""
        self.selection_layer.set_context_pins([QPoint(20, 100)], False)
        self.mouse_press(QPoint(20, 100), RIGHT)
        self.mouse_move(QPoint(-20, 100), RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [])
        self.mouse_move(QPoint(40, 100), RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [QPoint(40, 100)])
        self.mouse_release(QPoint(40, 100), RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [QPoint(40, 100)])

    def test_release_off_image_deletes_pin(self) -> None:
        """Releasing a dragged pin outside the image deletes it, as one undo step."""
        self.selection_layer.set_context_pins([QPoint(20, 100)], False)
        self.mouse_drag([QPoint(20, 100), QPoint(5, 100), QPoint(-20, 100)], RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [])
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assertEqual(self.selection_layer.context_pins, [QPoint(20, 100)])

    def test_missed_release_finishes_drag(self) -> None:
        """A move without the right button, after a release the tool never saw, drops the pin where it was."""
        self.mouse_press(QPoint(100, 100), RIGHT)
        self.mouse_move(QPoint(130, 100), RIGHT)
        self.mouse_move(QPoint(160, 100), Qt.MouseButton.NoButton)
        self.assertEqual(self.selection_layer.context_pins, [QPoint(130, 100)])
        self.assertEqual(UndoStack().undo_count(), 1)

    def test_left_click_selects(self) -> None:
        """The left button selects as before and adds no pin."""
        self.mouse_drag([QPoint(100, 100)])
        self.assertEqual(self.selection_layer.context_pins, [])
        self.assertFalse(self.selection_layer.is_empty())
