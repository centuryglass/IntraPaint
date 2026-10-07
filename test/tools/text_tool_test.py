"""Tests the text tool through mouse input on the canvas and edits in its control panel."""
import pytest
from PySide6.QtCore import QPoint, QPointF, QRect, QSize, QSizeF, Qt
from PySide6.QtGui import QTransform

from src.config.application_config import AppConfig
from src.image.layers.text_layer import TextLayer
from src.image.text_rect import TextRect
from src.tools.layer_transform_tool import LayerTransformTool
from src.tools.text_tool import TextTool, MIN_DRAG_SIZE
from src.ui.graphics_items.placement_outline import PlacementOutline
from src.ui.panel.tool_control_panels.text_tool_panel import TextToolPanel
from src.undo_stack import UndoStack
from test.tools.tool_test_case import ToolTestCase

DRAG_START = QPoint(50, 60)
DRAG_END = QPoint(150, 140)
DRAG_BOUNDS = QRect(DRAG_START, DRAG_END)


class TextToolTest(ToolTestCase):
    """Tests text layer creation, selection, editing and movement with the text tool, and their undo history."""

    def setUp(self) -> None:
        super().setUp()
        # Without time-based merging, each change is its own undo entry:
        AppConfig().set(AppConfig.UNDO_MERGE_INTERVAL, 0.0)
        self.tool = TextTool(self.image_stack, self.image_viewer)
        self.tool_controller.add_tool(self.tool)
        self.activate_tool(self.tool)
        self.panel: TextToolPanel = self.tool._control_panel
        self.outline: PlacementOutline = self.tool._placement_outline
        UndoStack().clear()

    def _drag_new_layer(self) -> TextLayer:
        self.mouse_drag([DRAG_START, (DRAG_START + DRAG_END) / 2, DRAG_END])
        layer = self.image_stack.active_layer
        assert isinstance(layer, TextLayer)
        return layer

    def _add_text_layer(self, bounds: QRect, text: str = 'Text') -> TextLayer:
        """Adds a text layer with a filled background outside the tool, so clicks anywhere in it hit content."""
        text_rect = TextRect()
        text_rect.text = text
        text_rect.size = bounds.size()
        text_rect.fill_background = True
        layer = self.image_stack.create_text_layer(text_rect)
        layer.set_transform(QTransform.fromTranslate(bounds.x(), bounds.y()))
        return layer

    def assert_panel_matches_layer(self, layer: TextLayer) -> None:
        """Asserts that the panel and placement outline show the layer's text, size and offset."""
        self.assertEqual(self.panel.text_rect.text, layer.text_rect.text)
        self.assertEqual(self.panel._text_box.value(), layer.text_rect.text)
        self.assertEqual(self.panel.text_rect.size, layer.size)
        self.assertEqual(self.panel.offset, layer.offset.toPoint())
        self.assertEqual(self.outline.outline_size, QSizeF(layer.size))
        self.assertEqual(self.outline.offset, layer.offset)

    def test_drag_creates_layer(self) -> None:
        """Dragging over empty canvas creates one text layer covering the dragged area, in one undo step."""
        layer = self._drag_new_layer()
        self.assertEqual(self.image_stack.text_layers, [layer])
        self.assertEqual(layer.transformed_bounds, DRAG_BOUNDS.adjusted(0, 0, -1, -1))
        self.assertIs(self.tool._text_layer, layer)
        self.assertTrue(self.outline.isVisible())
        self.assert_panel_matches_layer(layer)
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assertEqual(self.image_stack.text_layers, [])
        self.assertIsNone(self.tool._text_layer)
        self.assertFalse(self.outline.isVisible())

    def test_click_creates_nothing(self) -> None:
        """A click, or a drag no larger than MIN_DRAG_SIZE, on empty canvas creates no layer."""
        self.mouse_drag([DRAG_START])
        self.mouse_drag([DRAG_START, DRAG_START + QPoint(MIN_DRAG_SIZE, MIN_DRAG_SIZE)])
        self.assertEqual(self.image_stack.text_layers, [])
        self.assertEqual(UndoStack().undo_count(), 0)

    def test_click_selects_layer(self) -> None:
        """Clicking an inactive text layer makes it active and loads it into the panel without editing either layer."""
        first = self._add_text_layer(QRect(20, 20, 80, 40), 'First')
        second = self._add_text_layer(QRect(200, 200, 80, 40), 'Second')
        self.image_stack.active_layer = second
        self.assertIs(self.tool._text_layer, second)
        self.mouse_drag([QPoint(40, 30)])
        self.assertIs(self.image_stack.active_layer, first)
        self.assertIs(self.tool._text_layer, first)
        self.assert_panel_matches_layer(first)
        self.assertEqual(first.text_rect.text, 'First')
        self.assertEqual(second.text_rect.text, 'Second')

    def test_drag_new_layer_beside_active(self) -> None:
        """Dragging outside the active text layer creates a second layer and leaves the first unchanged."""
        first = self._add_text_layer(QRect(300, 300, 80, 40), 'First')
        second = self._drag_new_layer()
        self.assertIsNot(first, second)
        self.assertEqual(len(self.image_stack.text_layers), 2)
        self.assertEqual(first.text_rect.text, 'First')
        self.assertEqual(first.transformed_bounds, QRect(300, 300, 80, 40))
        self.assertIs(self.tool._text_layer, second)

    def test_typing_edits_layer(self) -> None:
        """Text typed into the panel goes to the active layer, one undo step per edit."""
        layer = self._drag_new_layer()
        UndoStack().clear()
        self.panel._text_box.setPlainText('Hello')
        self.panel._text_box.setPlainText('Hello world')
        self.assertEqual(layer.text_rect.text, 'Hello world')
        self.assertEqual(layer.name, '"Hello worl..."')
        self.assertEqual(UndoStack().undo_count(), 2)
        UndoStack().undo()
        self.assertEqual(layer.text_rect.text, 'Hello')
        UndoStack().undo()
        self.assertEqual(layer.text_rect.text, '')

    def test_undo_updates_panel(self) -> None:
        """Undoing and redoing a text edit updates the panel and outline to match the layer."""
        layer = self._drag_new_layer()
        self.panel._text_box.setPlainText('Hello')
        text_rect = self.panel.text_rect
        text_rect.size = QSize(60, 30)
        self.panel.text_rect = text_rect
        self.assertEqual(layer.size, QSize(60, 30))
        UndoStack().undo()
        self.assert_panel_matches_layer(layer)
        UndoStack().undo()
        self.assert_panel_matches_layer(layer)
        self.assertEqual(layer.text_rect.text, '')
        UndoStack().redo()
        self.assert_panel_matches_layer(layer)
        self.assertEqual(layer.text_rect.text, 'Hello')

    def test_panel_size_fields(self) -> None:
        """The panel's width and height fields resize the layer, including a height equal to the width."""
        layer = self._drag_new_layer()
        width = layer.size.width()
        self.panel._height_input.setValue(width)
        self.assertEqual(layer.size, QSize(width, width))
        self.panel._width_input.setValue(width + 20)
        self.assertEqual(layer.size, QSize(width + 20, width))
        self.assert_panel_matches_layer(layer)

    def test_panel_offset_moves_layer(self) -> None:
        """The panel's X and Y fields move the layer and its outline, one undo step per field."""
        layer = self._drag_new_layer()
        UndoStack().clear()
        self.panel._x_input.setValue(10)
        self.panel._y_input.setValue(20)
        self.assertEqual(layer.offset, QPointF(10, 20))
        self.assert_panel_matches_layer(layer)
        self.assertEqual(UndoStack().undo_count(), 2)
        UndoStack().undo()
        self.assertEqual(layer.offset, QPointF(10, DRAG_START.y()))
        self.assert_panel_matches_layer(layer)

    def test_drag_moves_active_layer(self) -> None:
        """Dragging inside the active layer moves it by the drag distance without creating a layer."""
        layer = self._drag_new_layer()
        start = DRAG_START + QPoint(20, 20)
        self.mouse_drag([start, start + QPoint(5, 5), start + QPoint(20, 30)])
        self.assertEqual(self.image_stack.text_layers, [layer])
        self.assertEqual(layer.offset, QPointF(DRAG_START + QPoint(20, 30)))
        self.assertEqual(layer.size, DRAG_BOUNDS.size() - QSize(1, 1))
        self.assert_panel_matches_layer(layer)

    @pytest.mark.xfail(strict=True, reason='https://github.com/centuryglass/IntraPaint/issues/11: undo merges a '
                                           'drag by elapsed time, not by gesture')
    def test_drag_move_is_one_undo_step(self) -> None:
        """One drag that moves the active layer adds one undo entry, however much time passes between its moves."""
        self._drag_new_layer()
        UndoStack().clear()
        start = DRAG_START + QPoint(20, 20)
        self.mouse_drag([start, start + QPoint(5, 5), start + QPoint(20, 30)])
        self.assertEqual(UndoStack().undo_count(), 1)

    def test_layer_transform_updates_panel(self) -> None:
        """Moving the layer outside the tool, and undoing the move, updates the panel's offset."""
        layer = self._drag_new_layer()
        layer.transform = QTransform.fromTranslate(5, 6)
        self.assert_panel_matches_layer(layer)
        UndoStack().undo()
        self.assertEqual(self.panel.offset, DRAG_START)

    def test_locked_layer_disables_controls(self) -> None:
        """Locking the active text layer disables the panel and outline, and unlocking enables them."""
        layer = self._drag_new_layer()
        layer.set_locked(True)
        self.assertFalse(self.panel.isEnabled())
        self.assertFalse(self.outline.isEnabled())
        layer.set_locked(False)
        self.assertTrue(self.panel.isEnabled())
        self.assertTrue(self.outline.isEnabled())

    def test_deactivate_disconnects_layer(self) -> None:
        """Switching tools disconnects the layer, and switching back reconnects the still-active layer."""
        layer = self._drag_new_layer()
        transform_tool = LayerTransformTool(self.image_stack, self.image_viewer)
        self.tool_controller.add_tool(transform_tool)
        self.activate_tool(transform_tool)
        self.assertIsNone(self.tool._text_layer)
        self.activate_tool(self.tool)
        self.assertIs(self.tool._text_layer, layer)
        self.assert_panel_matches_layer(layer)

    @pytest.mark.xfail(strict=True, reason='https://github.com/centuryglass/IntraPaint/issues/22: the text tool '
                                           'shows the translation, the transform tool the bounding box corner')
    def test_rotated_position_matches_transform_tool(self) -> None:
        """For a rotated text layer, the text tool's X and Y match the transform tool's."""
        layer = self._drag_new_layer()
        layer.rotate(90)
        text_tool_offset = self.panel.offset
        transform_tool = LayerTransformTool(self.image_stack, self.image_viewer)
        self.tool_controller.add_tool(transform_tool)
        self.activate_tool(transform_tool)
        transform_panel = transform_tool._control_panel
        self.assertEqual(QPointF(text_tool_offset),
                         QPointF(transform_panel.x_position, transform_panel.y_position))

    def test_unrotated_position_matches_transform_tool(self) -> None:
        """For a text layer that is only translated, the text tool's X and Y match the transform tool's."""
        self._drag_new_layer()
        text_tool_offset = self.panel.offset
        transform_tool = LayerTransformTool(self.image_stack, self.image_viewer)
        self.tool_controller.add_tool(transform_tool)
        self.activate_tool(transform_tool)
        transform_panel = transform_tool._control_panel
        self.assertEqual(QPointF(text_tool_offset),
                         QPointF(transform_panel.x_position, transform_panel.y_position))
