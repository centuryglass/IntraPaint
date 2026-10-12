"""Tests FreeSelectionTool: clicks build a polygon, closing it selects or deselects its area as one undo step, and
   Escape cancels it."""
from typing import Sequence
from unittest import mock

import numpy as np
from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.hotkey_filter import HotkeyFilter
from src.tools.free_selection_tool import FreeSelectionTool
from src.undo_stack import UndoStack
from src.util.visual.selection_mode import SelectionMode
from test.tools.selection_tool_test_case import SelectionToolTestCase, rect_mask

# Polygon points sit on pixel corners, so this polygon covers the pixels of QRect(10, 8, 30, 22):
RECT_POINTS = [QPoint(10, 8), QPoint(40, 8), QPoint(40, 30), QPoint(10, 30)]
RECT_AREA = QRect(10, 8, 30, 22)


class FreeSelectionToolTest(SelectionToolTestCase):
    """Drives FreeSelectionTool with synthetic clicks and key presses at 1:1 scale."""

    def setUp(self) -> None:
        super().setUp()
        self.tool = self.activate_tool(FreeSelectionTool(self.image_stack, self.image_viewer))
        self.empty = np.zeros((self.IMAGE_SIZE.height(), self.IMAGE_SIZE.width()), dtype=bool)

    def tearDown(self) -> None:
        # Earlier tests' tools would otherwise keep their Enter and Escape bindings and claim later tests' keys
        # (#165):
        hotkey_filter = HotkeyFilter.instance()
        hotkey_filter.remove_keybinding('FreeSelectionTool._close_on_enter')
        hotkey_filter.remove_keybinding(f'FreeSelectionTool_{id(self.tool)}_cancel_on_escape')
        hotkey_filter.remove_keybinding(f'SelectionPanel_{id(self.tool.get_control_panel())}_try_toggle')
        super().tearDown()

    def _path_point_count(self) -> int:
        return self.tool._path_item.count  # pylint: disable=protected-access

    def _click_points(self, points: Sequence[QPoint]) -> None:
        for point in points:
            self.mouse_drag([point])

    def _press_key(self, key: Qt.Key) -> None:
        """Sends a key press through the application, where HotkeyFilter handles the tool's keys."""
        QApplication.sendEvent(self.image_viewer, QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))

    def _set_deselect_mode(self) -> None:
        """Switches the tool to deselecting through the shared selection mode."""
        self.set_selection_mode(SelectionMode.SUBTRACT)

    def test_clicks_build_polygon_without_selecting(self) -> None:
        """Each click adds a polygon point as its own undo step, and selects nothing until the polygon closes."""
        self._click_points(RECT_POINTS)
        self.assertEqual(self._path_point_count(), 4)
        self.assert_selection(self.empty)
        self.assertEqual(UndoStack().undo_count(), 4)
        UndoStack().undo()
        self.assertEqual(self._path_point_count(), 3)

    def test_clicking_first_point_closes_polygon(self) -> None:
        """Clicking the first point again selects the polygon's area, as one undo step that restores the open
           polygon."""
        self._click_points(RECT_POINTS)
        UndoStack().clear()
        self._click_points([RECT_POINTS[0]])
        self.assertEqual(self._path_point_count(), 0)
        self.assert_one_undo_step(self.empty, rect_mask(self.IMAGE_SIZE, RECT_AREA))
        UndoStack().undo()
        self.assertEqual(self._path_point_count(), 4)

    def test_enter_closes_polygon(self) -> None:
        """Enter closes a polygon of three or more points, as one undo step."""
        self._click_points(RECT_POINTS)
        UndoStack().clear()
        self._press_key(Qt.Key.Key_Return)
        self.assertEqual(self._path_point_count(), 0)
        self.assert_one_undo_step(self.empty, rect_mask(self.IMAGE_SIZE, RECT_AREA))

    def test_enter_ignores_two_points(self) -> None:
        """Enter does nothing while the polygon has fewer than three points."""
        self._click_points(RECT_POINTS[:2])
        self._press_key(Qt.Key.Key_Return)
        self.assertEqual(self._path_point_count(), 2)
        self.assert_selection(self.empty)

    def test_triangle_selects_its_area(self) -> None:
        """A non-rectangular polygon selects the pixels whose centers fall inside it."""
        self._click_points([QPoint(10, 8), QPoint(40, 8), QPoint(10, 38), QPoint(10, 8)])
        y, x = np.mgrid[0:self.IMAGE_SIZE.height(), 0:self.IMAGE_SIZE.width()]
        # The hypotenuse runs along x + y == 48, through pixel corners:
        diagonal = (x + 0.5) + (y + 0.5) - 48
        inside = (x >= 10) & (y >= 8) & (diagonal < 0)
        on_hypotenuse = np.abs(diagonal) < 1
        mask = self.selection_mask()
        self.assert_masks_equal(mask & ~on_hypotenuse, inside & ~on_hypotenuse)
        self.assert_selection(mask)

    def test_escape_cancels_polygon(self) -> None:
        """Escape discards the open polygon without selecting, and the next click starts a new polygon."""
        self._click_points(RECT_POINTS[:3])
        self._press_key(Qt.Key.Key_Escape)
        self.assertEqual(self._path_point_count(), 0)
        self.assert_selection(self.empty)
        self._click_points([QPoint(20, 20)])
        self.assertEqual(self._path_point_count(), 1)

    def test_polygon_leaving_image_is_clipped(self) -> None:
        """A polygon with points outside the image selects only its part inside the image, as one undo step."""
        self._click_points([QPoint(40, 30), QPoint(80, 30), QPoint(80, 60), QPoint(40, 60)])
        UndoStack().clear()
        self._press_key(Qt.Key.Key_Return)
        self.assert_one_undo_step(self.empty, rect_mask(self.IMAGE_SIZE, QRect(40, 30, 24, 18)))

    def test_polygon_outside_image_changes_nothing(self) -> None:
        """Closing a polygon entirely outside the image clears it and leaves the selection layer untouched."""
        self._click_points([QPoint(70, 10), QPoint(90, 10), QPoint(90, 30)])
        UndoStack().clear()
        initial_image = self.selection_layer.image
        self._press_key(Qt.Key.Key_Return)
        self.assertEqual(self._path_point_count(), 0)
        self.assert_images_equal(self.selection_layer.image, initial_image)
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assertEqual(self._path_point_count(), 3)

    def test_polygon_adds_to_selection(self) -> None:
        """A closed polygon adds to the existing selection, without replacing it.

        #140 adds replace and intersect modes; this pins the current add-only behavior.
        """
        existing = rect_mask(self.IMAGE_SIZE, QRect(0, 0, 16, 16))
        self.set_selection_outside_history(existing)
        self._click_points(RECT_POINTS)
        UndoStack().clear()
        self._press_key(Qt.Key.Key_Return)
        self.assert_one_undo_step(existing, existing | rect_mask(self.IMAGE_SIZE, RECT_AREA))

    def test_deselect_mode_subtracts_polygon(self) -> None:
        """In deselect mode, a closed polygon clears its area from the existing selection, as one undo step."""
        existing = rect_mask(self.IMAGE_SIZE, QRect(0, 0, 32, 24))
        self.set_selection_outside_history(existing)
        self._set_deselect_mode()
        self._click_points(RECT_POINTS)
        UndoStack().clear()
        self._press_key(Qt.Key.Key_Return)
        self.assert_one_undo_step(existing, existing & ~rect_mask(self.IMAGE_SIZE, RECT_AREA))

    def test_tool_action_hotkey_cycles_modes(self) -> None:
        """The tool action hotkey (Q) steps through Add, Subtract, Replace and Intersect, then back to Add."""
        for expected in (SelectionMode.SUBTRACT, SelectionMode.REPLACE, SelectionMode.INTERSECT, SelectionMode.ADD):
            self._press_key(Qt.Key.Key_Q)
            self.assertEqual(Cache().get(Cache.SELECTION_MODE), expected.value)

    def test_tool_action_hotkey_toggles_deselect(self) -> None:
        """The tool action hotkey (Q) switches from the default add mode to subtract, so the next polygon subtracts."""
        existing = rect_mask(self.IMAGE_SIZE, QRect(0, 0, 32, 24))
        self.set_selection_outside_history(existing)
        self._press_key(Qt.Key.Key_Q)
        self._click_points(RECT_POINTS)
        self._press_key(Qt.Key.Key_Return)
        self.assert_selection(existing & ~rect_mask(self.IMAGE_SIZE, RECT_AREA))

    def _close_with(self, modifiers: Qt.KeyboardModifier) -> None:
        """Builds the rectangle polygon, then closes it by clicking its first point while the modifiers are held.

        Enter can't carry the modifiers, since HotkeyFilter only runs a key binding whose modifiers match exactly.
        """
        self._click_points(RECT_POINTS)
        UndoStack().clear()
        with mock.patch.object(QApplication, 'keyboardModifiers', return_value=modifiers):
            self.mouse_drag([RECT_POINTS[0]], modifiers=modifiers)

    def _existing(self) -> np.ndarray:
        existing = rect_mask(self.IMAGE_SIZE, QRect(0, 0, 32, 24))
        self.set_selection_outside_history(existing)
        return existing

    def test_replace_mode(self) -> None:
        """Replace mode leaves only the polygon selected."""
        existing = self._existing()
        self.set_selection_mode(SelectionMode.REPLACE)
        self._close_with(Qt.KeyboardModifier.NoModifier)
        self.assert_one_undo_step(existing, rect_mask(self.IMAGE_SIZE, RECT_AREA))

    def test_replace_mode_with_polygon_outside_image_clears_selection(self) -> None:
        """A replace polygon entirely outside the image still discards the old selection."""
        existing = self._existing()
        self.set_selection_mode(SelectionMode.REPLACE)
        self._click_points([QPoint(70, 10), QPoint(90, 10), QPoint(90, 30)])
        UndoStack().clear()
        self._press_key(Qt.Key.Key_Return)
        self.assert_one_undo_step(existing, self.empty)

    def test_intersect_mode(self) -> None:
        """Intersect mode keeps only the overlap of the polygon and the selection."""
        existing = self._existing()
        self.set_selection_mode(SelectionMode.INTERSECT)
        self._close_with(Qt.KeyboardModifier.NoModifier)
        self.assert_one_undo_step(existing, existing & rect_mask(self.IMAGE_SIZE, RECT_AREA))

    def test_alt_subtracts(self) -> None:
        """Alt held when the first point is clicked subtracts despite the default add mode."""
        existing = self._existing()
        self._close_with(Qt.KeyboardModifier.AltModifier)
        self.assert_one_undo_step(existing, existing & ~rect_mask(self.IMAGE_SIZE, RECT_AREA))

    def test_shift_adds_in_subtract_mode(self) -> None:
        """Shift held when the first point is clicked adds despite a stored subtract mode."""
        existing = self._existing()
        self.set_selection_mode(SelectionMode.SUBTRACT)
        self._close_with(Qt.KeyboardModifier.ShiftModifier)
        self.assert_one_undo_step(existing, existing | rect_mask(self.IMAGE_SIZE, RECT_AREA))
