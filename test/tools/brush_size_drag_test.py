"""Tests the brush size drag gesture in every brush tool: modifier + right-drag sets the size, Escape restores it, and
   the drag never paints or edits context pins."""
from typing import Callable, Optional
from unittest import mock

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.config.config_entry import RangeKey
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.tools.brush_tool import BrushTool
from src.tools.clone_stamp_tool import CloneStampTool
from src.tools.draw_tool import DrawTool
from src.tools.eraser_tool import EraserTool
from src.tools.filter_tool import FilterTool
from src.tools.mypaint_brush_tool import MyPaintBrushTool
from src.tools.selection_brush_tool import SelectionBrushTool
from src.tools.smudge_tool import SmudgeTool
from src.ui.image_viewer import ImageViewer
from src.undo_stack import UndoStack
from test.base_test_case import press_key
from test.image.brush.brush_test_case import brush_test_pattern
from test.tools.tool_test_case import ToolTestCase

RIGHT = Qt.MouseButton.RightButton
LEFT = Qt.MouseButton.LeftButton
ALT = Qt.KeyboardModifier.AltModifier
CENTER = QPoint(256, 256)


class _BrushSizeDragTestBase(ToolTestCase):
    """Drives one brush tool's size drag. Subclasses set TOOL_CLASS and SIZE_KEY."""

    TOOL_CLASS: Optional[Callable[[ImageStack, ImageViewer], BrushTool]] = None
    SIZE_KEY = ''

    def setUp(self) -> None:
        super().setUp()
        tool_class = self.TOOL_CLASS
        assert tool_class is not None
        self.layer = self.image_stack.create_layer(image_data=brush_test_pattern(self.IMAGE_SIZE))
        self.image_stack.active_layer = self.layer
        self.tool = self.activate_tool(tool_class(self.image_stack, self.image_viewer))
        self.tool.set_brush_size(20)
        UndoStack().clear()

    def _size_drag(self, end: QPoint, release: bool = True) -> None:
        """Presses at CENTER with the right button and the size drag modifier, and moves to `end`."""
        self.mouse_press(CENTER, RIGHT, ALT)
        self.mouse_move(QPoint(CENTER.x() + 3, CENTER.y()), RIGHT, ALT)
        self.mouse_move(end, RIGHT, ALT)
        if release:
            self.mouse_release(end, RIGHT, ALT)

    def _press_escape(self) -> None:
        """Presses Escape with the modifier still held. HotkeyFilter reads held modifiers from the application."""
        with mock.patch.object(QApplication, 'keyboardModifiers', return_value=ALT):
            press_key(self.image_viewer, Qt.Key.Key_Escape, ALT)

    def _assert_size(self, expected: int) -> None:
        self.assertEqual(Cache().get(self.SIZE_KEY), expected)
        self.assertEqual(self.tool.brush_size, expected)

    def test_drag_sets_size_from_distance(self) -> None:
        """The size is twice the pointer's image-space distance from the press point, at every zoom level."""
        for scale in (1.0, 2.0, 3.0):
            with self.subTest(scale=scale):
                self.image_viewer.scene_scale = scale
                self.image_viewer.center_on_point(QPointF(CENTER))
                self._size_drag(QPoint(CENTER.x() + 30, CENTER.y()))
                self.assertAlmostEqual(Cache().get(self.SIZE_KEY), 60, delta=2)
                self.assertEqual(self.tool.brush_size, Cache().get(self.SIZE_KEY))

    def test_outline_stays_at_press_point(self) -> None:
        """During the drag the outline is centred on the press point and sized to the dragged size."""
        self._size_drag(QPoint(CENTER.x() + 40, CENTER.y()), release=False)
        outline = self.tool.brush_outline
        self.assertTrue(outline.isVisible())
        self.assertAlmostEqual(outline.pos().x(), CENTER.x() + 0.5, delta=1)
        self.assertAlmostEqual(outline.pos().y(), CENTER.y() + 0.5, delta=1)
        self.assertAlmostEqual(outline.diameter, 80, delta=2)
        self.mouse_release(QPoint(CENTER.x() + 40, CENTER.y()), RIGHT, ALT)

    def test_drag_changes_no_pixels_and_adds_no_undo_step(self) -> None:
        """The drag paints nothing, even with a left press during it, and records no undo step."""
        initial_image = self.layer.image
        initial_selection = self.image_stack.selection_layer.image
        self.mouse_press(CENTER, RIGHT, ALT)
        self.send_mouse_event(QEvent.Type.MouseButtonPress, QPoint(CENTER.x() + 10, CENTER.y()), LEFT, LEFT | RIGHT,
                              ALT)
        self.mouse_move(QPoint(CENTER.x() + 50, CENTER.y() + 20), LEFT | RIGHT, ALT)
        self.mouse_release(QPoint(CENTER.x() + 50, CENTER.y() + 20), RIGHT, ALT)
        self.assertEqual(self.layer.image, initial_image)
        self.assertEqual(self.image_stack.selection_layer.image, initial_selection)
        self.assertEqual(UndoStack().undo_count(), 0)

    def test_escape_restores_size(self) -> None:
        """Escape mid-drag restores the size from before the drag, and the rest of the drag changes nothing."""
        self._size_drag(QPoint(CENTER.x() + 50, CENTER.y()), release=False)
        self.assertNotEqual(self.tool.brush_size, 20)
        self._press_escape()
        self._assert_size(20)
        self.mouse_move(QPoint(CENTER.x() + 80, CENTER.y()), RIGHT, ALT)
        self.mouse_release(QPoint(CENTER.x() + 80, CENTER.y()), RIGHT, ALT)
        self._assert_size(20)

    def test_deactivation_restores_size(self) -> None:
        """Deactivating the tool mid-drag restores the size from before the drag."""
        self._size_drag(QPoint(CENTER.x() + 50, CENTER.y()), release=False)
        self.tool.is_active = False
        self._assert_size(20)
        self.tool.is_active = True
        self.mouse_release(QPoint(CENTER.x() + 50, CENTER.y()), RIGHT, ALT)
        self._assert_size(20)

    def test_size_is_clamped_to_maximum(self) -> None:
        """A drag past the tool's maximum size sets the maximum."""
        maximum = Cache().get(self.SIZE_KEY, RangeKey.MAX)
        self.assertLess(maximum, 400)
        self._size_drag(QPoint(CENTER.x() - 200, CENTER.y()))
        self._assert_size(maximum)

    def test_right_drag_without_modifier_is_not_a_size_drag(self) -> None:
        """A right-drag without the modifier leaves the size alone."""
        self.mouse_drag([CENTER, QPoint(CENTER.x() + 60, CENTER.y())], RIGHT)
        self._assert_size(20)

    def test_unbound_modifier_disables_drag(self) -> None:
        """With the modifier unbound, modifier + right-drag leaves the size alone."""
        KeyConfig().set(KeyConfig.BRUSH_SIZE_DRAG_MODIFIER, '')
        self._size_drag(QPoint(CENTER.x() + 60, CENTER.y()))
        self._assert_size(20)


class MyPaintBrushSizeDragTest(_BrushSizeDragTestBase):
    """Size drag in the MyPaint brush tool."""
    TOOL_CLASS = MyPaintBrushTool
    SIZE_KEY = Cache.PAINT_TOOL_BRUSH_SIZE


class DrawToolSizeDragTest(_BrushSizeDragTestBase):
    """Size drag in the draw tool."""
    TOOL_CLASS = DrawTool
    SIZE_KEY = Cache.DRAW_TOOL_BRUSH_SIZE


class EraserToolSizeDragTest(_BrushSizeDragTestBase):
    """Size drag in the eraser tool."""
    TOOL_CLASS = EraserTool
    SIZE_KEY = Cache.ERASER_TOOL_SIZE


class SmudgeToolSizeDragTest(_BrushSizeDragTestBase):
    """Size drag in the smudge tool."""
    TOOL_CLASS = SmudgeTool
    SIZE_KEY = Cache.SMUDGE_TOOL_BRUSH_SIZE


class CloneStampToolSizeDragTest(_BrushSizeDragTestBase):
    """Size drag in the clone stamp tool, whose plain right-click sets the clone source."""
    TOOL_CLASS = CloneStampTool
    SIZE_KEY = Cache.CLONE_STAMP_TOOL_BRUSH_SIZE

    def test_drag_leaves_clone_source(self) -> None:
        """The drag neither sets the clone source nor starts picking one."""
        # pylint: disable=protected-access
        source = QPoint(self.tool._source_pos)
        pending = self.tool._pending_source_point
        self._size_drag(QPoint(CENTER.x() + 30, CENTER.y()))
        self.assertEqual(self.tool._source_pos, source)
        self.assertEqual(self.tool._pending_source_point, pending)


class FilterToolSizeDragTest(_BrushSizeDragTestBase):
    """Size drag in the filter tool."""
    TOOL_CLASS = FilterTool
    SIZE_KEY = Cache.FILTER_TOOL_BRUSH_SIZE


class SelectionBrushSizeDragTest(_BrushSizeDragTestBase):
    """Size drag in the selection brush, whose plain right button edits context pins."""
    TOOL_CLASS = SelectionBrushTool
    SIZE_KEY = Cache.SELECTION_BRUSH_SIZE

    def test_drag_adds_and_moves_no_pin(self) -> None:
        """The drag neither adds a context pin nor moves one under the press point."""
        selection_layer = self.image_stack.selection_layer
        self._size_drag(QPoint(CENTER.x() + 30, CENTER.y()))
        self.assertEqual(selection_layer.context_pins, [])
        selection_layer.set_context_pins([CENTER], False)
        self._size_drag(QPoint(CENTER.x() + 30, CENTER.y() + 30))
        self.assertEqual(selection_layer.context_pins, [CENTER])


del _BrushSizeDragTestBase
