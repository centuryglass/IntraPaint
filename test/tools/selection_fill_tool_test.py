"""Tests SelectionFillTool: a click selects the area matching the clicked color, by flood fill or by color, from the
   active layer, the merged image or the selection itself, as one undo step."""
from unittest import mock

import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QImage, QTransform
from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.tools.selection_fill_tool import SelectionFillTool
from src.ui.input_fields.check_box import CheckBox
from src.ui.panel.tool_control_panels.fill_selection_panel import FILL_BY_SELECTION
from src.undo_stack import UndoStack
from src.util.visual.image_utils import image_data_as_numpy_8bit
from test.tools.selection_tool_test_case import SelectionToolTestCase, rect_mask

RIGHT = Qt.MouseButton.RightButton

# The pattern: black on the left, split by a near-black stripe, white on the right with a black square inside it.
BLACK = (0, 0, 0)
NEAR_BLACK = (10, 10, 10)  # About 2.7 from black in the fill's perceptual distance.
WHITE = (255, 255, 255)
STRIPE = QRect(16, 0, 4, 48)
WHITE_AREA = QRect(32, 0, 32, 48)
ISLAND = QRect(44, 16, 8, 8)
LEFT_OF_STRIPE = QRect(0, 0, 16, 48)
RIGHT_OF_STRIPE = QRect(20, 0, 12, 48)
# Below the stripe's threshold, above the distance between black and white:
NEAR_THRESHOLD = 5.0


def _pattern_image(width: int, height: int) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    pixels = image_data_as_numpy_8bit(image)
    pixels[:, :, 3] = 255

    def _fill(rect: QRect, rgb: tuple[int, int, int]) -> None:
        pixels[rect.y():rect.y() + rect.height(), rect.x():rect.x() + rect.width(), :3] = rgb[::-1]  # BGR order
    _fill(QRect(0, 0, width, height), BLACK)
    _fill(STRIPE, NEAR_BLACK)
    _fill(WHITE_AREA, WHITE)
    _fill(ISLAND, BLACK)
    return image


class SelectionFillToolTest(SelectionToolTestCase):
    """Drives SelectionFillTool with synthetic clicks at 1:1 scale, on a layer holding the pattern image."""

    def setUp(self) -> None:
        super().setUp()
        self.layer.set_image(_pattern_image(self.IMAGE_SIZE.width(), self.IMAGE_SIZE.height()))
        Cache().set(Cache.FILL_THRESHOLD, 0.0)
        Cache().set(Cache.SAMPLE_MERGED, False)
        Cache().set(Cache.COLOR_SELECT_MODE, False)
        self.tool = self.activate_tool(SelectionFillTool(self.image_stack))
        self.empty = np.zeros((self.IMAGE_SIZE.height(), self.IMAGE_SIZE.width()), dtype=bool)
        UndoStack().clear()

    def _mask(self, *rects: QRect) -> np.ndarray:
        mask = self.empty.copy()
        for rect in rects:
            mask |= rect_mask(self.IMAGE_SIZE, rect)
        return mask

    def test_flood_fill_stops_at_other_colors(self) -> None:
        """At threshold 0, a click selects the connected area of the exact clicked color, as one undo step."""
        self.mouse_drag([QPoint(4, 4)])
        self.assert_one_undo_step(self.empty, self._mask(LEFT_OF_STRIPE))

    def test_flood_fill_threshold_includes_similar_colors(self) -> None:
        """A threshold above the stripe's color distance fills through it, but not into the white area or the
           unconnected black square."""
        Cache().set(Cache.FILL_THRESHOLD, NEAR_THRESHOLD)
        self.mouse_drag([QPoint(4, 4)])
        self.assert_one_undo_step(self.empty, self._mask(LEFT_OF_STRIPE, STRIPE, RIGHT_OF_STRIPE))

    def test_color_select_mode_ignores_connectivity(self) -> None:
        """In color select mode, a click selects every pixel of the clicked color, connected or not."""
        Cache().set(Cache.COLOR_SELECT_MODE, True)
        self.mouse_drag([QPoint(4, 4)])
        self.assert_one_undo_step(self.empty, self._mask(LEFT_OF_STRIPE, RIGHT_OF_STRIPE, ISLAND))

    def test_color_select_mode_samples_offset_layer_at_click(self) -> None:
        """On a layer moved right, color select mode matches the color of the layer pixel under the click."""
        self.layer.set_transform(QTransform.fromTranslate(8, 0))
        UndoStack().clear()
        Cache().set(Cache.COLOR_SELECT_MODE, True)
        self.mouse_drag([QPoint(STRIPE.x() + 8 + 1, 4)])
        self.assert_one_undo_step(self.empty, self._mask(STRIPE.translated(8, 0)))

    def test_flood_fill_on_offset_layer(self) -> None:
        """On a layer moved right, the flood fill starts at the layer pixel under the click and selects in image
           coordinates."""
        self.layer.set_transform(QTransform.fromTranslate(8, 0))
        UndoStack().clear()
        self.mouse_drag([QPoint(12, 4)])
        self.assert_one_undo_step(self.empty, self._mask(LEFT_OF_STRIPE.translated(8, 0)))

    def test_sample_merged_uses_layers_above(self) -> None:
        """With sample merged on, a white bar on a layer above the active layer stops the fill; with it off, the
           fill sees only the active layer."""
        bar = QImage(self.IMAGE_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
        bar.fill(Qt.GlobalColor.transparent)
        bar_pixels = image_data_as_numpy_8bit(bar)
        bar_pixels[20:28, :, :] = 255
        self.image_stack.create_layer(image_data=bar)
        self.image_stack.active_layer = self.layer
        UndoStack().clear()

        self.mouse_drag([QPoint(4, 4)])
        self.assert_selection(self._mask(LEFT_OF_STRIPE))
        UndoStack().undo()
        Cache().set(Cache.SAMPLE_MERGED, True)
        self.mouse_drag([QPoint(4, 4)])
        self.assert_selection(self._mask(QRect(0, 0, 16, 20)))

    def test_fill_selection_holes(self) -> None:
        """With "Fill selection holes" checked, a click in an unselected hole selects the hole, ignoring the image."""
        ring = self._mask(QRect(4, 4, 40, 30)) & ~self._mask(QRect(10, 10, 20, 16))
        self.set_selection_outside_history(ring)
        panel = self.tool.get_control_panel()
        assert panel is not None
        checkboxes = [box for box in panel.findChildren(CheckBox) if box.text() == FILL_BY_SELECTION]
        self.assertEqual(len(checkboxes), 1)
        checkboxes[0].setChecked(True)
        self.mouse_drag([QPoint(20, 20)])
        self.assert_one_undo_step(ring, self._mask(QRect(4, 4, 40, 30)))

    def test_left_click_adds_to_selection(self) -> None:
        """A left-click adds the filled area to the existing selection, without replacing it.

        #140 adds replace and intersect modes; this pins the current add-only behavior.
        """
        existing = self._mask(QRect(40, 30, 24, 18))
        self.set_selection_outside_history(existing)
        self.mouse_drag([QPoint(4, 4)])
        self.assert_one_undo_step(existing, existing | self._mask(LEFT_OF_STRIPE))

    def test_right_click_subtracts_from_selection(self) -> None:
        """A right-click clears the filled area from the existing selection, as one undo step."""
        existing = self._mask(QRect(0, 0, 40, 30))
        self.set_selection_outside_history(existing)
        self.mouse_drag([QPoint(4, 4)], RIGHT)
        self.assert_one_undo_step(existing, existing & ~self._mask(LEFT_OF_STRIPE))

    def test_any_modifier_ignores_click(self) -> None:
        """With any keyboard modifier held, a click changes nothing.

        #140 plans Shift and Alt as one-gesture add and subtract modifiers; this pins the current behavior.
        """
        for modifier in (Qt.KeyboardModifier.ShiftModifier, Qt.KeyboardModifier.AltModifier):
            with mock.patch.object(QApplication, 'keyboardModifiers', return_value=modifier):
                self.mouse_drag([QPoint(4, 4)], modifiers=modifier)
            self.assert_selection(self.empty)
            self.assertEqual(UndoStack().undo_count(), 0)

    def test_each_click_is_one_undo_step(self) -> None:
        """Two clicks record two undo steps, and undoing the second leaves the first."""
        self.mouse_drag([QPoint(4, 4)])
        self.mouse_drag([QPoint(40, 4)])
        self.assert_selection(self._mask(LEFT_OF_STRIPE, WHITE_AREA) & ~self._mask(ISLAND))
        self.assertEqual(UndoStack().undo_count(), 2)
        UndoStack().undo()
        self.assert_selection(self._mask(LEFT_OF_STRIPE))
