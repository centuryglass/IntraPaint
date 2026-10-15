"""Tests ShapeSelectionTool: rectangle and ellipse drags select into the selection layer, a right-drag edits context pins,
   and each drag is one undo step."""
from unittest import mock

import numpy as np
from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.hotkey_filter import HotkeyFilter
from src.tools.shape_selection_tool import ShapeSelectionTool
from src.ui.input_fields.dual_toggle import DualToggle
from src.undo_stack import UndoStack
from src.util.visual.selection_mode import SelectionMode
from src.util.visual.shape_mode import SHAPE_MODE_ELLIPSE_LABEL
from test.tools.context_pin_gesture_tests import ContextPinGestureTests
from test.tools.selection_tool_test_case import SelectionToolTestCase, rect_mask, mask_bounds

RIGHT = Qt.MouseButton.RightButton
SHIFT = Qt.KeyboardModifier.ShiftModifier
CTRL = Qt.KeyboardModifier.ControlModifier


def _ellipse_mask(shape: tuple[int, int], rect: QRect) -> np.ndarray:
    """Returns pixels whose centers fall inside the ellipse inscribed in rect, as (inside, boundary) masks.

    Boundary pixels sit within about a pixel of the curve, where Qt's polygon approximation may go either way.
    """
    y, x = np.mgrid[0:shape[0], 0:shape[1]]
    center_x = rect.x() + rect.width() / 2
    center_y = rect.y() + rect.height() / 2
    radius_x = rect.width() / 2
    radius_y = rect.height() / 2
    # Distance from the curve in pixels, approximately:
    normalized = np.sqrt(((x + 0.5 - center_x) / radius_x) ** 2 + ((y + 0.5 - center_y) / radius_y) ** 2)
    pixel_distance = (normalized - 1.0) * min(radius_x, radius_y)
    return pixel_distance < 0, np.abs(pixel_distance) <= 1.0


class ShapeSelectionToolTest(ContextPinGestureTests, SelectionToolTestCase):
    """Drives ShapeSelectionTool with synthetic mouse input at 1:1 scale."""

    def setUp(self) -> None:
        super().setUp()
        self.tool = self.activate_tool(ShapeSelectionTool(self.image_stack, self.image_viewer))
        self.empty = np.zeros((self.IMAGE_SIZE.height(), self.IMAGE_SIZE.width()), dtype=bool)

    def tearDown(self) -> None:
        # The panel's binding would otherwise outlive the test and claim later tests' keys (#165):
        panel_id = id(self.tool.get_control_panel())
        HotkeyFilter.instance().remove_keybinding(f'ShapeSelectionPanel_{panel_id}_try_toggle')
        super().tearDown()

    def _set_ellipse_mode(self) -> None:
        """Switches to ellipse selection through the control panel's rectangle/ellipse toggle."""
        panel = self.tool.get_control_panel()
        assert panel is not None
        mode_toggle = panel.findChild(DualToggle)
        assert isinstance(mode_toggle, DualToggle)
        mode_toggle.setValue(SHAPE_MODE_ELLIPSE_LABEL)

    def test_rectangle_drag_selects(self) -> None:
        """A left-drag selects the rectangle between the press and release pixels' top-left corners, as one undo
           step."""
        self.mouse_drag([QPoint(10, 8), QPoint(20, 14), QPoint(30, 20)])
        self.assert_one_undo_step(self.empty, rect_mask(self.IMAGE_SIZE, QRect(10, 8, 20, 12)))

    def test_rectangle_drag_up_and_left_selects(self) -> None:
        """A drag toward the top left selects the same rectangle as the drag in the other direction."""
        self.mouse_drag([QPoint(30, 20), QPoint(20, 14), QPoint(10, 8)])
        self.assert_selection(rect_mask(self.IMAGE_SIZE, QRect(10, 8, 20, 12)))

    def test_rectangle_drag_past_image_edge_is_clipped(self) -> None:
        """A drag that ends outside the image selects the part of the rectangle inside it, as one undo step."""
        self.mouse_drag([QPoint(40, 30), QPoint(60, 40), QPoint(90, 70)])
        self.assert_one_undo_step(self.empty, rect_mask(self.IMAGE_SIZE, QRect(40, 30, 24, 18)))

    def test_rectangle_drag_outside_image_does_nothing(self) -> None:
        """A drag entirely outside the image selects nothing and records no undo step."""
        self.mouse_drag([QPoint(70, 10), QPoint(80, 20), QPoint(90, 30)])
        self.assert_selection(self.empty)
        self.assertEqual(UndoStack().undo_count(), 0)

    def assert_square_from(self, corner: QPoint) -> None:
        """Asserts the selection is one square anchored at a corner, added as one undo step."""
        bounds = mask_bounds(self.selection_mask())
        assert bounds is not None
        self.assertEqual(bounds.topLeft(), corner)
        self.assertEqual(bounds.width(), bounds.height())
        self.assert_one_undo_step(self.empty, rect_mask(self.IMAGE_SIZE, bounds))

    def test_fixed_aspect_modifier_makes_square(self) -> None:
        """Pressing the fixed aspect modifier (Shift) during the drag selects a square anchored at the press point."""
        self.mouse_press(QPoint(10, 8))
        with mock.patch.object(QApplication, 'keyboardModifiers', return_value=SHIFT):
            self.mouse_move(QPoint(25, 12), modifiers=SHIFT)
            self.mouse_move(QPoint(40, 16), modifiers=SHIFT)
            self.mouse_release(QPoint(40, 16), modifiers=SHIFT)
        self.assert_square_from(QPoint(10, 8))

    def test_fixed_aspect_modifier_held_at_press_needs_fresh_press(self) -> None:
        """Shift held from the press doesn't fix the aspect ratio, since the press reads it as add. Releasing it and
           pressing it again during the drag does."""
        with mock.patch.object(QApplication, 'keyboardModifiers', return_value=SHIFT):
            self.mouse_drag([QPoint(10, 8), QPoint(25, 12), QPoint(40, 16)], modifiers=SHIFT)
        self.assert_selection(rect_mask(self.IMAGE_SIZE, QRect(10, 8, 30, 8)))
        UndoStack().clear()
        self.set_selection_outside_history(self.empty)
        with mock.patch.object(QApplication, 'keyboardModifiers', return_value=SHIFT):
            self.mouse_press(QPoint(10, 8), modifiers=SHIFT)
        self.mouse_move(QPoint(25, 12))
        with mock.patch.object(QApplication, 'keyboardModifiers', return_value=SHIFT):
            self.mouse_move(QPoint(40, 16), modifiers=SHIFT)
            self.mouse_release(QPoint(40, 16), modifiers=SHIFT)
        self.assert_square_from(QPoint(10, 8))

    def test_fixed_aspect_checkbox(self) -> None:
        """With the fixed aspect option checked, a drag with no modifiers selects a square."""
        Cache().set(Cache.SHAPE_SELECTION_FIXED_ASPECT, True)
        self.mouse_drag([QPoint(10, 8), QPoint(25, 12), QPoint(40, 16)])
        self.assert_square_from(QPoint(10, 8))

    def test_pan_modifier_ignores_drag(self) -> None:
        """With the pan view modifier (Ctrl) held, a drag changes nothing."""
        with mock.patch.object(QApplication, 'keyboardModifiers', return_value=CTRL):
            self.mouse_drag([QPoint(10, 8), QPoint(30, 20)], modifiers=CTRL)
        self.assert_selection(self.empty)
        self.assertEqual(UndoStack().undo_count(), 0)

    def test_ellipse_drag_selects(self) -> None:
        """In ellipse mode, a drag selects the ellipse inscribed in the dragged rectangle, as one undo step."""
        self._set_ellipse_mode()
        rect = QRect(8, 6, 40, 30)
        self.mouse_drag([rect.topLeft(), QPoint(30, 20), rect.topLeft() + QPoint(rect.width(), rect.height())])
        mask = self.selection_mask()
        inside, boundary = _ellipse_mask(mask.shape, rect)
        self.assert_masks_equal(mask & ~boundary, inside & ~boundary)
        self.assertEqual(mask_bounds(mask), rect)
        self.assert_one_undo_step(self.empty, mask)

    def test_ellipse_drag_past_image_edge_is_clipped(self) -> None:
        """An ellipse that extends past the image selects only its part inside the image."""
        self._set_ellipse_mode()
        rect = QRect(40, 20, 40, 40)
        self.mouse_drag([rect.topLeft(), QPoint(80, 60)])
        mask = self.selection_mask()
        inside, boundary = _ellipse_mask(mask.shape, rect)
        self.assert_masks_equal(mask & ~boundary, inside & ~boundary)
        self.assertEqual(mask_bounds(mask), QRect(40, 20, 24, 28))
        self.assert_one_undo_step(self.empty, mask)

    def test_left_drag_adds_to_selection(self) -> None:
        """With the default add mode, a left-drag adds to the existing selection, without replacing it."""
        existing = rect_mask(self.IMAGE_SIZE, QRect(0, 0, 16, 16))
        self.set_selection_outside_history(existing)
        self.mouse_drag([QPoint(8, 8), QPoint(30, 20)])
        self.assert_one_undo_step(existing, existing | rect_mask(self.IMAGE_SIZE, QRect(8, 8, 22, 12)))

    def test_right_drag_does_not_change_selection(self) -> None:
        """A right-drag edits context pins and leaves the selection unchanged."""
        existing = rect_mask(self.IMAGE_SIZE, QRect(0, 0, 40, 30))
        self.set_selection_outside_history(existing)
        self.mouse_drag([QPoint(10, 8), QPoint(50, 20)], RIGHT)
        self.assert_selection(existing)

    def test_each_drag_is_one_undo_step(self) -> None:
        """Two drags record two undo steps, and undoing the second leaves the first."""
        self.mouse_drag([QPoint(2, 2), QPoint(12, 12)])
        first = rect_mask(self.IMAGE_SIZE, QRect(2, 2, 10, 10))
        self.mouse_drag([QPoint(30, 20), QPoint(40, 40)])
        self.assert_selection(first | rect_mask(self.IMAGE_SIZE, QRect(30, 20, 10, 20)))
        self.assertEqual(UndoStack().undo_count(), 2)
        UndoStack().undo()
        self.assert_selection(first)

    def test_tool_action_hotkey_toggles_ellipse(self) -> None:
        """The tool action hotkey (Q) switches between rectangle and ellipse, not between select and deselect.

        #140 notes this differs from the free selection tool, where the same key toggles deselect.
        """
        QApplication.sendEvent(self.image_viewer, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Q,
                                                            Qt.KeyboardModifier.NoModifier))
        rect = QRect(8, 6, 40, 30)
        self.mouse_drag([rect.topLeft(), rect.topLeft() + QPoint(rect.width(), rect.height())])
        mask = self.selection_mask()
        self.assertEqual(mask_bounds(mask), rect)
        self.assertFalse(mask[rect.y(), rect.x()], 'Rectangle corner selected in ellipse mode')


ALT = Qt.KeyboardModifier.AltModifier


class ShapeSelectionModeTest(SelectionToolTestCase):
    """Drives ShapeSelectionTool's selection modes and the add and subtract modifiers."""

    EXISTING = QRect(0, 0, 40, 30)
    DRAG = [QPoint(20, 15), QPoint(60, 40)]  # Selects QRect(20, 15, 40, 25), overlapping EXISTING in (20, 15, 20, 15)

    def setUp(self) -> None:
        super().setUp()
        self.tool = self.activate_tool(ShapeSelectionTool(self.image_stack, self.image_viewer))
        self.empty = np.zeros((self.IMAGE_SIZE.height(), self.IMAGE_SIZE.width()), dtype=bool)
        self.existing = rect_mask(self.IMAGE_SIZE, self.EXISTING)
        self.dragged = rect_mask(self.IMAGE_SIZE, QRect(20, 15, 40, 25))
        self.set_selection_outside_history(self.existing)

    def tearDown(self) -> None:
        HotkeyFilter.instance().remove_keybinding(f'ShapeSelectionPanel_{id(self.tool.get_control_panel())}_try_toggle')
        super().tearDown()

    def _drag_with(self, modifiers: Qt.KeyboardModifier) -> None:
        with mock.patch.object(QApplication, 'keyboardModifiers', return_value=modifiers):
            self.mouse_drag(self.DRAG, modifiers=modifiers)

    def test_add_mode(self) -> None:
        """Add mode unions the dragged rectangle with the selection."""
        self.set_selection_mode(SelectionMode.ADD)
        self.mouse_drag(self.DRAG)
        self.assert_one_undo_step(self.existing, self.existing | self.dragged)

    def test_subtract_mode(self) -> None:
        """Subtract mode clears the dragged rectangle from the selection."""
        self.set_selection_mode(SelectionMode.SUBTRACT)
        self.mouse_drag(self.DRAG)
        self.assert_one_undo_step(self.existing, self.existing & ~self.dragged)

    def test_replace_mode(self) -> None:
        """Replace mode leaves only the dragged rectangle selected, as one undo step."""
        self.set_selection_mode(SelectionMode.REPLACE)
        self.mouse_drag(self.DRAG)
        self.assert_one_undo_step(self.existing, self.dragged)

    def test_intersect_mode(self) -> None:
        """Intersect mode keeps only the overlap between the selection and the dragged rectangle."""
        self.set_selection_mode(SelectionMode.INTERSECT)
        self.mouse_drag(self.DRAG)
        self.assert_one_undo_step(self.existing, self.existing & self.dragged)

    def test_replace_mode_outside_image_clears_selection(self) -> None:
        """A replace drag that misses the image still discards the old selection."""
        self.set_selection_mode(SelectionMode.REPLACE)
        self.mouse_drag([QPoint(70, 10), QPoint(90, 30)])
        self.assert_one_undo_step(self.existing, self.empty)

    def test_shift_adds_for_one_gesture(self) -> None:
        """Shift held through a drag adds despite a stored subtract mode, without fixing the aspect ratio, and the next
           gesture uses the stored mode."""
        self.set_selection_mode(SelectionMode.SUBTRACT)
        self._drag_with(SHIFT)
        self.assert_selection(self.existing | self.dragged)
        self.mouse_drag([QPoint(0, 0), QPoint(64, 48)])
        self.assert_selection(self.empty)

    def test_alt_subtracts_in_add_mode(self) -> None:
        """Alt held at the press subtracts despite the default add mode."""
        self._drag_with(ALT)
        self.assert_one_undo_step(self.existing, self.existing & ~self.dragged)

    def test_alt_overrides_replace_mode(self) -> None:
        """The subtract modifier beats a stored replace mode."""
        self.set_selection_mode(SelectionMode.REPLACE)
        self._drag_with(ALT)
        self.assert_selection(self.existing & ~self.dragged)

    def test_shift_and_alt_intersect(self) -> None:
        """Shift and Alt together intersect with the selection."""
        self._drag_with(SHIFT | ALT)
        self.assert_one_undo_step(self.existing, self.existing & self.dragged)

    def test_ctrl_shift_replaces(self) -> None:
        """Ctrl+Shift replaces the selection despite the default add mode, and doesn't pan the view."""
        self._drag_with(CTRL | SHIFT)
        self.assert_one_undo_step(self.existing, self.dragged)
