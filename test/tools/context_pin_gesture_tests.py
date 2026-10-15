"""Right-button context pin tests shared by every selection tool except the selection brush, which pins its own."""
from PySide6.QtCore import QPoint, Qt

from src.undo_stack import UndoStack

RIGHT = Qt.MouseButton.RightButton


class ContextPinGestureTests:
    """Mixin for `SelectionToolTestCase` subclasses: the right button adds, moves and removes context pins.

    The test case sets `selection_layer` and drives the tool under test with `mouse_drag`, `mouse_press`,
    `mouse_move` and `mouse_release`. The pins sit well apart and inside the 64x48 image.
    """

    # pylint: disable=no-member

    def test_right_click_adds_pin_without_selecting(self) -> None:
        """A right-click away from every pin adds a pin there, selects nothing, and records one undo step."""
        self.mouse_drag([QPoint(20, 20)], RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [QPoint(20, 20)])
        self.assertTrue(self.selection_layer.is_empty())
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assertEqual(self.selection_layer.context_pins, [])

    def test_right_drag_moves_existing_pin(self) -> None:
        """A right-drag from a pin moves it, leaves other pins alone, and records one undo step."""
        self.selection_layer.set_context_pins([QPoint(20, 20), QPoint(50, 40)], False)
        self.mouse_drag([QPoint(20, 20), QPoint(30, 25), QPoint(40, 10)], RIGHT)
        self.assertCountEqual(self.selection_layer.context_pins, [QPoint(50, 40), QPoint(40, 10)])
        self.assertTrue(self.selection_layer.is_empty())
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assertCountEqual(self.selection_layer.context_pins, [QPoint(20, 20), QPoint(50, 40)])

    def test_right_click_on_pin_removes_it(self) -> None:
        """A right-click on an existing pin removes it, as one undo step."""
        self.selection_layer.set_context_pins([QPoint(20, 20)], False)
        self.mouse_drag([QPoint(20, 20)], RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [])
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assertEqual(self.selection_layer.context_pins, [QPoint(20, 20)])

    def test_release_off_image_deletes_pin(self) -> None:
        """Dropping a dragged pin outside the image deletes it, as one undo step."""
        self.selection_layer.set_context_pins([QPoint(20, 20)], False)
        self.mouse_drag([QPoint(20, 20), QPoint(5, 20), QPoint(-20, 20)], RIGHT)
        self.assertEqual(self.selection_layer.context_pins, [])
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assertEqual(self.selection_layer.context_pins, [QPoint(20, 20)])

    def test_left_button_adds_no_pin(self) -> None:
        """The left button never touches context pins."""
        self.selection_layer.set_context_pins([QPoint(20, 20)], False)
        self.mouse_drag([QPoint(20, 20), QPoint(30, 30)])
        self.assertEqual(self.selection_layer.context_pins, [QPoint(20, 20)])
