"""Tests panning the image view with the pan key and the middle button, and the 100% zoom action. Events are
synthesized, and nothing waits on the event loop."""
from unittest import mock

import numpy as np
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from src.tools.shape_selection_tool import ShapeSelectionTool
from src.undo_stack import UndoStack
from test.base_test_case import press_key
from test.tools.selection_tool_test_case import SelectionToolTestCase

DRAG = [QPoint(10, 8), QPoint(30, 20)]


class PanKeyTest(SelectionToolTestCase):
    """Drives the image viewer's pan gestures with a selection tool active, so a drag that reaches the tool shows up
       as a selection."""

    def setUp(self) -> None:
        super().setUp()
        self.tool = self.activate_tool(ShapeSelectionTool(self.image_stack, self.image_viewer))
        self.empty = np.zeros((self.IMAGE_SIZE.height(), self.IMAGE_SIZE.width()), dtype=bool)

    def test_drag_without_the_pan_key_reaches_the_tool(self) -> None:
        """A plain left drag selects and leaves the view where it was."""
        before = self.image_viewer.offset
        self.mouse_drag(DRAG)
        self.assertEqual(before, self.image_viewer.offset)
        self.assertTrue(self.selection_mask().any())

    def test_drag_with_the_pan_key_pans_without_reaching_the_tool(self) -> None:
        """A left drag with the pan key held moves the view, and no selection or undo step results."""
        before = self.image_viewer.offset
        self.image_viewer.set_pan_key_held(True)
        self.mouse_drag(DRAG)
        self.assertNotEqual(before, self.image_viewer.offset)
        self.assert_selection(self.empty)
        self.assertEqual(UndoStack().undo_count(), 0)

    def test_pan_direction_follows_the_mouse(self) -> None:
        """Dragging right and down moves the content with the mouse, so the view offset decreases."""
        before = self.image_viewer.offset
        self.image_viewer.set_pan_key_held(True)
        self.mouse_drag([QPoint(10, 8), QPoint(20, 14)])
        after = self.image_viewer.offset
        self.assertLess(after.x(), before.x())
        self.assertLess(after.y(), before.y())

    def test_releasing_the_pan_key_restores_tool_input(self) -> None:
        """Once the key is up again, drags reach the tool."""
        self.image_viewer.set_pan_key_held(True)
        self.image_viewer.set_pan_key_held(False)
        self.mouse_drag(DRAG)
        self.assertTrue(self.selection_mask().any())

    def test_ctrl_drag_no_longer_pans(self) -> None:
        """Ctrl was the old pan modifier: a Ctrl drag now leaves the view alone and reaches the tool."""
        before = self.image_viewer.offset
        with mock.patch.object(QApplication, 'keyboardModifiers', return_value=Qt.KeyboardModifier.ControlModifier):
            self.mouse_drag(DRAG, modifiers=Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(before, self.image_viewer.offset)
        self.assertTrue(self.selection_mask().any())

    def test_middle_drag_pans(self) -> None:
        """Middle-button drags still pan the view."""
        before = self.image_viewer.offset
        self.mouse_drag(DRAG, button=Qt.MouseButton.MiddleButton)
        self.assertNotEqual(before, self.image_viewer.offset)

    def test_hand_cursor_while_the_pan_key_is_held(self) -> None:
        """The cursor is an open hand while the key is held, a closed hand during the drag, and the tool's cursor
           afterward."""
        viewer = self.image_viewer
        viewer.set_cursor(Qt.CursorShape.CrossCursor)
        viewer.set_pan_key_held(True)
        self.assertEqual(Qt.CursorShape.OpenHandCursor, viewer.cursor().shape())
        self.mouse_press(DRAG[0])
        self.assertEqual(Qt.CursorShape.ClosedHandCursor, viewer.cursor().shape())
        self.mouse_release(DRAG[0])
        self.assertEqual(Qt.CursorShape.OpenHandCursor, viewer.cursor().shape())
        viewer.set_pan_key_held(False)
        self.assertEqual(Qt.CursorShape.CrossCursor, viewer.cursor().shape())

    def test_cursor_set_during_the_hold_applies_afterward(self) -> None:
        """A tool that changes the cursor while the key is held doesn't hide the hand."""
        viewer = self.image_viewer
        viewer.set_pan_key_held(True)
        viewer.set_cursor(Qt.CursorShape.CrossCursor)
        self.assertEqual(Qt.CursorShape.OpenHandCursor, viewer.cursor().shape())
        viewer.set_pan_key_held(False)
        self.assertEqual(Qt.CursorShape.CrossCursor, viewer.cursor().shape())

    def test_space_key_events_hold_the_pan_key(self) -> None:
        """Pressing and releasing Space holds the pan key, even in a view without keybindings like this one."""
        press_key(self.image_viewer, Qt.Key.Key_Space)
        self.assertTrue(self.image_viewer.pan_key_held)
        handle = self.image_viewer.window().windowHandle()
        QApplication.sendEvent(handle, QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Space,
                                                 Qt.KeyboardModifier.NoModifier))
        self.assertFalse(self.image_viewer.pan_key_held)

    def test_zoom_to_actual_size(self) -> None:
        """Zoom to 100% sets the scale to exactly 1."""
        self.image_viewer.scene_scale = 2.5
        self.image_viewer.zoom_to_actual_size()
        self.assertEqual(1.0, self.image_viewer.scene_scale)
