"""Tests the generation area tool's left-drag moves and resize handles through mouse input on the canvas."""
from PySide6.QtCore import QPoint, QRect, QSize, Qt

from src.config.cache import Cache
from src.tools.generation_area_tool import GenerationAreaTool
from src.undo_stack import UndoStack
from test.tools.tool_test_case import ToolTestCase

START_AREA = QRect(100, 100, 200, 100)
SHIFT = Qt.KeyboardModifier.ShiftModifier


class GenerationAreaToolTestBase(ToolTestCase):
    """Sets up a generation area tool with START_AREA selected and a clear undo history."""

    SHOW_HANDLES = True

    def setUp(self) -> None:
        super().setUp()
        self.image_stack.min_generation_area_size = QSize(8, 8)
        self.image_stack.max_generation_area_size = self.IMAGE_SIZE
        self.image_stack.generation_area = START_AREA
        self.tool = GenerationAreaTool(self.image_stack, self.image_viewer, show_handles=self.SHOW_HANDLES)
        self.tool_controller.add_tool(self.tool)
        self.activate_tool(self.tool)
        UndoStack().clear()


class GenerationAreaToolMoveTest(GenerationAreaToolTestBase):
    """Tests moving the area with left-drags."""

    def test_drag_inside_keeps_grab_offset(self) -> None:
        """Pressing inside the area doesn't move it, and dragging moves it by the pointer's movement."""
        self.mouse_press(QPoint(150, 120))
        self.assertEqual(self.image_stack.generation_area, START_AREA)
        self.mouse_move(QPoint(170, 150))
        self.mouse_release(QPoint(170, 150))
        self.assertEqual(self.image_stack.generation_area, QRect(120, 130, 200, 100))

    def test_press_outside_centers_then_drags(self) -> None:
        """Pressing outside the area centers it on the pointer, and dragging continues from there."""
        self.mouse_press(QPoint(400, 400))
        self.assertEqual(self.image_stack.generation_area, QRect(300, 350, 200, 100))
        self.mouse_move(QPoint(390, 380))
        self.mouse_release(QPoint(390, 380))
        self.assertEqual(self.image_stack.generation_area, QRect(290, 330, 200, 100))

    def test_move_stays_in_image(self) -> None:
        """Dragging past the image edge stops the area at the edge."""
        self.mouse_drag([QPoint(150, 120), QPoint(5, 5)])
        self.assertEqual(self.image_stack.generation_area, QRect(0, 0, 200, 100))

    def test_modifier_press_is_ignored(self) -> None:
        """A left-press with an unrelated modifier held leaves the area alone, for the view's own modifier gestures."""
        self.mouse_drag([QPoint(400, 400), QPoint(410, 410)], modifiers=Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.image_stack.generation_area, START_AREA)

    def test_each_drag_is_one_undo_step(self) -> None:
        """Every change in one drag undoes together, and separate drags undo separately."""
        self.mouse_drag([QPoint(150, 120), QPoint(160, 120), QPoint(170, 120)])
        first_drag_area = self.image_stack.generation_area
        self.mouse_drag([QPoint(200, 150), QPoint(200, 160), QPoint(200, 170)])
        self.assertEqual(self.image_stack.generation_area, QRect(120, 120, 200, 100))
        self.assertEqual(UndoStack().undo_count(), 2)
        UndoStack().undo()
        self.assertEqual(self.image_stack.generation_area, first_drag_area)
        UndoStack().undo()
        self.assertEqual(self.image_stack.generation_area, START_AREA)


class GenerationAreaToolHandleTest(GenerationAreaToolTestBase):
    """Tests resizing the area with its handles."""

    def test_handles_shown_only_while_active(self) -> None:
        """The handles show while the tool is active and hide when another tool takes over."""
        handles = list(self.tool._handles.values())
        self.assertEqual(len(handles), 8)
        self.assertTrue(all(handle.isVisible() for handle in handles))
        self.tool_controller.active_tool = None
        self.assertFalse(any(handle.isVisible() for handle in handles))

    def test_corner_keeps_aspect_ratio(self) -> None:
        """A corner handle keeps the area's aspect ratio when no modifier is held."""
        self.mouse_drag([QPoint(300, 200), QPoint(400, 300)])
        self.assertEqual(self.image_stack.generation_area, QRect(100, 100, 320, 160))

    def test_corner_with_modifier_resizes_freely(self) -> None:
        """Holding the fixed aspect modifier lets a corner handle change the aspect ratio."""
        self.mouse_drag([QPoint(300, 200), QPoint(400, 300)], modifiers=SHIFT)
        self.assertEqual(self.image_stack.generation_area, QRect(100, 100, 300, 200))

    def test_edge_handle_moves_one_side(self) -> None:
        """An edge handle moves only its own side."""
        self.mouse_drag([QPoint(100, 150), QPoint(50, 180)])
        self.assertEqual(self.image_stack.generation_area, QRect(50, 100, 250, 100))

    def test_handle_press_does_not_move_area(self) -> None:
        """Pressing a handle grabs it without moving or resizing the area."""
        self.mouse_press(QPoint(300, 200))
        self.assertEqual(self.image_stack.generation_area, START_AREA)
        self.mouse_release(QPoint(300, 200))
        self.assertEqual(self.image_stack.generation_area, START_AREA)
        self.assertEqual(UndoStack().undo_count(), 0)

    def test_resize_is_one_undo_step_and_records_frame(self) -> None:
        """A handle drag undoes in one step and adds the finished size to the recent frames."""
        self.mouse_drag([QPoint(300, 200), QPoint(350, 250), QPoint(400, 300)], modifiers=SHIFT)
        self.assertEqual(UndoStack().undo_count(), 1)
        self.assertIn('300x200', Cache().get(Cache.RECENT_GENERATION_AREA_SIZES))
        UndoStack().undo()
        self.assertEqual(self.image_stack.generation_area, START_AREA)

    def test_hover_cursor(self) -> None:
        """Hovering over a handle shows a resize cursor, and the default cursor returns away from it."""
        self.mouse_move(QPoint(300, 200), Qt.MouseButton.NoButton)
        self.assertEqual(self.tool.cursor.shape(), Qt.CursorShape.SizeFDiagCursor)
        self.mouse_move(QPoint(200, 100), Qt.MouseButton.NoButton)
        self.assertEqual(self.tool.cursor.shape(), Qt.CursorShape.SizeVerCursor)
        self.mouse_move(QPoint(200, 150), Qt.MouseButton.NoButton)
        self.assertEqual(self.tool.cursor.shape(), Qt.CursorShape.CrossCursor)

    def test_input_hint_describes_handles(self) -> None:
        """The hint covers handle resizing and the inverted aspect modifier."""
        hint = self.tool.get_input_hint()
        self.assertIn('drag a handle to resize', hint)
        self.assertIn('free aspect ratio on corner handles', hint)

    def test_handles_follow_area(self) -> None:
        """The handles move with the area."""
        self.image_stack.generation_area = QRect(10, 20, 100, 50)
        handle_pos = self.tool._handles['bottom_right'].pos()
        self.assertEqual((handle_pos.x(), handle_pos.y()), (110.0, 70.0))


class GenerationAreaToolNoHandlesTest(GenerationAreaToolTestBase):
    """Tests the navigation panel's instance, which has no handles."""

    SHOW_HANDLES = False

    def test_corner_press_moves_area(self) -> None:
        """Without handles, pressing at the area's corner centers the area there instead of resizing it."""
        self.mouse_drag([QPoint(300, 200), QPoint(310, 210)])
        self.assertEqual(self.image_stack.generation_area, QRect(210, 160, 200, 100))

    def test_input_hint_omits_handles(self) -> None:
        """The hint doesn't mention handles the instance doesn't have."""
        self.assertNotIn('handle', self.tool.get_input_hint())
