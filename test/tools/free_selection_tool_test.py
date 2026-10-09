"""Tests FreeSelectionTool: clicks build a polygon, closing it selects or deselects its area as one undo step, and
   Escape cancels it."""
from typing import Sequence

import numpy as np
from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from src.hotkey_filter import HotkeyFilter
from src.tools.free_selection_tool import FreeSelectionTool
from src.ui.input_fields.dual_toggle import DualToggle
from src.ui.panel.tool_control_panels.brush_selection_panel import TOOL_MODE_DESELECT
from src.undo_stack import UndoStack
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
        hotkey_filter.remove_keybinding(f'FreeSelectionPanel_{id(self.tool.get_control_panel())}_try_toggle')
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
        """Switches the tool to deselecting through its control panel's select/deselect toggle."""
        panel = self.tool.get_control_panel()
        assert panel is not None
        mode_toggle = panel.findChild(DualToggle)
        assert isinstance(mode_toggle, DualToggle)
        mode_toggle.setValue(TOOL_MODE_DESELECT)

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

    def test_tool_action_hotkey_toggles_deselect(self) -> None:
        """The tool action hotkey (Q) switches to deselect mode, so the next polygon subtracts."""
        existing = rect_mask(self.IMAGE_SIZE, QRect(0, 0, 32, 24))
        self.set_selection_outside_history(existing)
        self._press_key(Qt.Key.Key_Q)
        self._click_points(RECT_POINTS)
        self._press_key(Qt.Key.Key_Return)
        self.assert_selection(existing & ~rect_mask(self.IMAGE_SIZE, RECT_AREA))
