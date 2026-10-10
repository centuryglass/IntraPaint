"""Tests the selection brush: its left button and brush paint the selection layer, and its right button adds, moves
   and removes context pins."""
import math

import numpy as np
from PySide6.QtCore import QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QImage, QPainter, QPen

from src.config.cache import Cache
from src.image.brush.qt_paint_brush import QtPaintBrush
from src.image.layers.selection_layer import SelectionLayer
from src.tools.selection_brush_tool import SelectionBrushTool
from src.ui.input_fields.dual_toggle import DualToggle
from src.ui.panel.tool_control_panels.brush_selection_panel import TOOL_MODE_DESELECT
from src.undo_stack import UndoStack
from src.util.visual.image_utils import image_data_as_numpy_8bit
from test.tools.tool_test_case import ToolTestCase

RIGHT = Qt.MouseButton.RightButton


class SelectionBrushToolTest(ToolTestCase):
    """Drives SelectionBrushTool's right button with synthetic mouse input at 1:1 scale."""

    def setUp(self) -> None:
        super().setUp()
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


SELECTION_BRUSH_GOLDEN_DIR = 'test/resources/test_images/selection_brush'
SELECTED_ARGB = 0xffff0000  # Every selected pixel, with the test config's SELECTION_COLOR.
STROKE_BRUSH_SIZE = 16
SOFT_HARDNESS = 0.3
SOFT_OPACITY = 0.4

# A curving stroke through the middle of the stroke test image:
CURVE_POINTS = [QPoint(20 + i * 6, 64 + round(36 * math.sin(i / 3))) for i in range(21)]
# A stroke from inside the image out past its top right corner, back in, and out through the bottom edge:
EDGE_CROSSING_POINTS = [QPoint(40, 40), QPoint(120, 10), QPoint(170, -20), QPoint(150, 30), QPoint(100, 80),
                        QPoint(80, 140)]


def _golden(name: str) -> str:
    return f'{SELECTION_BRUSH_GOLDEN_DIR}/{name}.png'


def _outline_image(selection_layer: SelectionLayer) -> QImage:
    """Draws the selection layer's outline polygons with an aliased one-pixel pen, on an image one pixel larger than
       the layer, since outline points sit on pixel edges."""
    image = QImage(selection_layer.size + QSize(1, 1), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setPen(QPen(Qt.GlobalColor.black, 0))
    for polygon in selection_layer.outline:
        painter.drawPolygon(polygon)
    painter.end()
    return image


def _outline_points(selection_layer: SelectionLayer) -> list[list[tuple[float, float]]]:
    return [[point.toTuple() for point in polygon.toList()] for polygon in selection_layer.outline]


class SelectionBrushStrokeTest(ToolTestCase):
    """Drives SelectionBrushTool's left button and brush, pinning what painted and erased selections look like."""

    IMAGE_SIZE = QSize(160, 128)

    def setUp(self) -> None:
        super().setUp()
        Cache().set(Cache.SELECTION_BRUSH_SIZE, STROKE_BRUSH_SIZE)
        self.image_stack.create_layer()
        self.tool = self.activate_tool(SelectionBrushTool(self.image_stack, self.image_viewer))
        self.selection_layer = self.image_stack.selection_layer
        brush = self.tool.brush
        assert isinstance(brush, QtPaintBrush)
        self.brush = brush
        UndoStack().clear()

    def _set_deselect_mode(self) -> None:
        """Switches the tool to erasing selection through its control panel's select/deselect toggle."""
        panel = self.tool.get_control_panel()
        assert panel is not None
        mode_toggle = panel.findChild(DualToggle)
        assert isinstance(mode_toggle, DualToggle)
        mode_toggle.setValue(TOOL_MODE_DESELECT)
        self.assertTrue(self.brush.eraser)

    def _select_all(self) -> QImage:
        """Selects the whole image outside the undo history, and returns the selection layer image."""
        self.selection_layer.select_all()
        UndoStack().clear()
        return self.selection_layer.image

    def _brush_stroke(self, points: list[tuple[int, int, float]]) -> QImage:
        """Draws one stroke with the tool's brush through (x, y, pressure) points, returning the selection image."""
        self.brush.start_stroke()
        for x, y, pressure in points:
            self.brush.stroke_to(x, y, pressure, None, None)
        self.brush.end_stroke()
        return self.selection_layer.image

    def assert_selection_state(self, golden_name: str) -> None:
        """Asserts the selection layer image and outline match their goldens, every pixel is either unselected or
           fully selected, and the outline's bounds match the selection bounds."""
        image = self.selection_layer.image
        self.assert_image_matches_golden(image, _golden(golden_name))
        self.assert_image_matches_golden(_outline_image(self.selection_layer), _golden(f'{golden_name}_outline'))
        pixels = image_data_as_numpy_8bit(image.convertToFormat(QImage.Format.Format_ARGB32)).view(np.uint32)
        partial = (pixels != 0) & (pixels != SELECTED_ARGB)
        self.assertFalse(np.any(partial), f'{np.count_nonzero(partial)} pixels are partially selected')
        selection_bounds = self.selection_layer.get_selection_bounds()
        outline = self.selection_layer.outline
        if selection_bounds is None:
            self.assertEqual(outline, [])
            self.assertTrue(self.selection_layer.is_empty())
            return
        self.assertFalse(self.selection_layer.is_empty())
        self.assertEqual(selection_bounds, self.selection_layer.get_content_bounds())
        outline_bounds = QRectF()
        for polygon in outline:
            outline_bounds = outline_bounds.united(polygon.boundingRect())
        self.assertEqual(outline_bounds, QRectF(selection_bounds))

    def assert_one_undo_step(self, initial_image: QImage) -> None:
        """Asserts the last stroke was one undo step that restores initial_image, and that redo restores the stroke
           and its outline."""
        stroke_image = self.selection_layer.image
        outline = _outline_points(self.selection_layer)
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assert_images_equal(self.selection_layer.image, initial_image)
        UndoStack().redo()
        self.assert_images_equal(self.selection_layer.image, stroke_image)
        self.assertCountEqual(_outline_points(self.selection_layer), outline)

    def test_hard_stroke_selects(self) -> None:
        """A drag with the default hard brush selects along the stroke, as one undo step that clears the outline."""
        initial_image = self.selection_layer.image
        self.mouse_drag(CURVE_POINTS)
        self.assert_selection_state('hard_select')
        self.assert_one_undo_step(initial_image)
        UndoStack().undo()
        self.assertTrue(self.selection_layer.is_empty())
        self.assertEqual(self.selection_layer.outline, [])
        self.assertIsNone(self.selection_layer.get_selection_bounds())

    def _soften_brush(self) -> None:
        """Sets every brush option that would leave partial alpha in a stroke on an image layer."""
        self.brush.hardness = SOFT_HARDNESS
        self.brush.opacity = SOFT_OPACITY
        self.brush.antialiasing = True

    def test_soft_brush_options_select_like_hard_brush(self) -> None:
        """Hardness, opacity and antialiasing don't affect a select stroke, since the selection layer is one-bit."""
        self._soften_brush()
        self.mouse_drag(CURVE_POINTS)
        self.assert_selection_state('hard_select')
        self.assertEqual(UndoStack().undo_count(), 1)

    def test_hard_stroke_deselects(self) -> None:
        """In deselect mode, a drag with the hard brush clears selection along the stroke, as one undo step."""
        initial_image = self._select_all()
        self._set_deselect_mode()
        self.mouse_drag(CURVE_POINTS)
        self.assert_selection_state('hard_deselect')
        self.assert_one_undo_step(initial_image)

    def test_soft_brush_options_deselect_like_hard_brush(self) -> None:
        """Hardness, opacity and antialiasing don't affect a deselect stroke, since the selection layer is one-bit."""
        self._select_all()
        self._set_deselect_mode()
        self._soften_brush()
        self.mouse_drag(CURVE_POINTS)
        self.assert_selection_state('hard_deselect')
        self.assertEqual(UndoStack().undo_count(), 1)

    def test_stroke_leaving_image_selects(self) -> None:
        """A stroke that leaves and re-enters the image selects only inside it, as one undo step."""
        initial_image = self.selection_layer.image
        self.mouse_drag(EDGE_CROSSING_POINTS)
        self.assert_selection_state('edge_crossing_select')
        self.assert_one_undo_step(initial_image)

    def test_stroke_leaving_image_deselects(self) -> None:
        """A deselect stroke that leaves and re-enters the image clears selection only inside it."""
        initial_image = self._select_all()
        self._set_deselect_mode()
        self.mouse_drag(EDGE_CROSSING_POINTS)
        self.assert_selection_state('edge_crossing_deselect')
        self.assert_one_undo_step(initial_image)

    def test_each_stroke_is_one_undo_step(self) -> None:
        """Two strokes record two undo steps, and undoing the second leaves the first and its outline."""
        self.mouse_drag([QPoint(20, 30), QPoint(60, 40), QPoint(100, 30)])
        first_image = self.selection_layer.image
        first_outline = _outline_points(self.selection_layer)
        self.mouse_drag([QPoint(30, 100), QPoint(80, 90), QPoint(140, 110)])
        self.assertEqual(UndoStack().undo_count(), 2)
        UndoStack().undo()
        self.assert_images_equal(self.selection_layer.image, first_image)
        self.assertCountEqual(_outline_points(self.selection_layer), first_outline)

    def test_pressure_sets_size_without_pressure_size(self) -> None:
        """On the selection layer, pressure scales brush size even with the brush's pressure_size option off."""
        self.brush.pressure_size = False
        self.brush.brush_size = 24
        self._brush_stroke([(20 + i * 6, 64, 0.2 + i * 0.04) for i in range(21)])
        self.assert_selection_state('pressure_select')
        self.assertEqual(UndoStack().undo_count(), 1)

    def test_pressure_ignored_for_opacity_and_hardness(self) -> None:
        """On the selection layer, pressure changes size only, even with pressure_opacity and pressure_hardness on.

        Below full opacity or hardness an erased pixel keeps some alpha and stays selected, so deselecting shows
        whether pressure reached either value.
        """
        full_selection = self._select_all()
        self._set_deselect_mode()
        self.brush.pressure_size = False
        self.brush.pressure_opacity = True
        self.brush.pressure_hardness = True
        line = [(20 + i * 10, 64) for i in range(13)]
        self.brush.brush_size = 32
        pressure_image = self._brush_stroke([(x, y, 0.5) for x, y in line])
        UndoStack().undo()
        self.brush.pressure_size = True
        self.brush.pressure_opacity = False
        self.brush.pressure_hardness = False
        self.brush.brush_size = 16
        expected_image = self._brush_stroke([(x, y, 1.0) for x, y in line])
        self.assertNotEqual(expected_image, full_selection)
        self.assert_images_equal(pressure_image, expected_image)
