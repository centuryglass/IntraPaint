"""Tests the quick stroke card that a right-click opens in the MyPaint brush, draw, eraser and smudge tools."""
from typing import Callable, Optional
from unittest import mock

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.image.layers.image_stack import ImageStack
from src.tools.brush_tool import QUICK_CARD_CLICK_SLOP, BrushTool
from src.tools.clone_stamp_tool import CloneStampTool
from src.tools.draw_tool import DrawTool
from src.tools.eraser_tool import EraserTool
from src.tools.mypaint_brush_tool import MyPaintBrushTool
from src.tools.selection_brush_tool import SelectionBrushTool
from src.tools.smudge_tool import SmudgeTool
from src.ui.image_viewer import ImageViewer
from src.ui.panel.mypaint_brush_panel import FAV_CONFIG_KEY
from src.ui.widget.quick_stroke_card import EDGE_MARGIN
from src.undo_stack import UndoStack
from test.base_test_case import press_key
from test.image.brush.brush_test_case import brush_test_pattern
from test.tools.tool_test_case import ToolTestCase

RIGHT = Qt.MouseButton.RightButton
LEFT = Qt.MouseButton.LeftButton
CENTER = QPoint(256, 256)


class _QuickStrokeCardTestBase(ToolTestCase):
    """Drives one tool's card. Subclasses set TOOL_CLASS, SIZE_KEY and OPACITY_KEY, and COLOR_ROW for tools that show
    one."""

    TOOL_CLASS: Optional[Callable[[ImageStack, ImageViewer], BrushTool]] = None
    SIZE_KEY = ''
    OPACITY_KEY: Optional[str] = None
    COLOR_ROW = False

    def setUp(self) -> None:
        super().setUp()
        tool_class = self.TOOL_CLASS
        assert tool_class is not None
        self.layer = self.image_stack.create_layer(image_data=brush_test_pattern(self.IMAGE_SIZE))
        self.image_stack.active_layer = self.layer
        self.tool = self.activate_tool(tool_class(self.image_stack, self.image_viewer))
        UndoStack().clear()

    def open_card(self, point: QPoint = CENTER):
        """Right-clicks at an image point and returns the opened card."""
        self.mouse_drag([point], RIGHT)
        card = self.tool.quick_card
        self.assertIsNotNone(card)
        assert card is not None
        self.assertTrue(card.isVisible())
        return card

    def test_right_click_opens_card_and_paints_nothing(self) -> None:
        """A right press and release without moving opens the card and changes no pixels."""
        initial_image = self.layer.image
        self.open_card()
        self.assertEqual(self.layer.image, initial_image)
        self.assertEqual(UndoStack().undo_count(), 0)

    def test_right_click_with_small_movement_opens_card(self) -> None:
        """A right press and release within the click slop still opens the card."""
        self.mouse_drag([CENTER, QPoint(CENTER.x() + QUICK_CARD_CLICK_SLOP - 1, CENTER.y())], RIGHT)
        self.assertIsNotNone(self.tool.quick_card)
        assert self.tool.quick_card is not None
        self.assertTrue(self.tool.quick_card.isVisible())

    def test_right_drag_does_not_open_card(self) -> None:
        """A right drag past the click slop doesn't open the card."""
        distance = QUICK_CARD_CLICK_SLOP + 1
        self.mouse_drag([CENTER, QPoint(CENTER.x() + distance, CENTER.y())], RIGHT)
        self.assertIsNone(self.tool.quick_card)

    def test_right_press_during_stroke_is_ignored(self) -> None:
        """A right press while the left button is down doesn't open the card, and the stroke continues."""
        self.mouse_press(CENTER, LEFT)
        self.send_mouse_event(QEvent.Type.MouseButtonPress, CENTER, RIGHT, LEFT | RIGHT)
        self.send_mouse_event(QEvent.Type.MouseButtonRelease, CENTER, RIGHT, LEFT)
        self.assertTrue(self.tool._drawing)  # pylint: disable=protected-access
        self.mouse_release(CENTER, LEFT)
        self.assertIsNone(self.tool.quick_card)
        self.assertFalse(self.tool._drawing)  # pylint: disable=protected-access

    def test_modifier_right_click_does_not_open_card(self) -> None:
        """A right-click with a modifier held isn't the card's gesture."""
        self.mouse_drag([CENTER], RIGHT, Qt.KeyboardModifier.ControlModifier)
        self.assertIsNone(self.tool.quick_card)

    def test_card_opens_over_size_field(self) -> None:
        """Away from the edges, the pointer is over the middle of the Size field."""
        card = self.open_card()
        center = card.size_field.mapTo(self.image_viewer, card.size_field.rect().center())
        pointer = self.image_point_to_widget(CENTER)
        self.assertLessEqual((center - pointer).manhattanLength(), 2)

    def test_card_stays_inside_viewer(self) -> None:
        """Near each corner, the card is clamped inside the viewer's margin."""
        bounds = self.image_viewer.rect()
        for point in (QPoint(0, 0), QPoint(511, 0), QPoint(0, 511), QPoint(511, 511)):
            with self.subTest(point=point.toTuple()):
                self.image_viewer.scene_scale = 1.0
                card = self.open_card(point)
                geometry = card.geometry()
                self.assertGreaterEqual(geometry.left(), EDGE_MARGIN)
                self.assertGreaterEqual(geometry.top(), EDGE_MARGIN)
                self.assertLessEqual(geometry.right(), bounds.right() - EDGE_MARGIN)
                self.assertLessEqual(geometry.bottom(), bounds.bottom() - EDGE_MARGIN)
                card.close_card()

    def test_fields_follow_and_write_cache(self) -> None:
        """Changing a field changes its Cache key, and a change to the key updates the field."""
        card = self.open_card()
        card.size_field.set_value(41)
        self.assertEqual(Cache().get(self.SIZE_KEY), 41)
        Cache().set(self.SIZE_KEY, 17)
        self.assertEqual(card.size_field.value(), 17)
        if self.OPACITY_KEY is not None:
            opacity_field = card.fields[1]
            opacity_field.set_value(0.5)
            self.assertAlmostEqual(Cache().get(self.OPACITY_KEY), 0.5)
            Cache().set(self.OPACITY_KEY, 0.25)
            self.assertAlmostEqual(opacity_field.value(), 0.25)

    def test_card_reveals_pressure_links_when_a_tablet_is_seen(self) -> None:
        """An open card, and one opened later, show the pressure links once a tablet is seen."""
        if self.OPACITY_KEY is None:
            self.skipTest('The tool has no pressure links')
        Cache().set(Cache.EXPECT_TABLET_INPUT, False)
        card = self.open_card()
        self.assertFalse(card.size_field.pressure_link_available())
        Cache().set(Cache.EXPECT_TABLET_INPUT, True)
        self.assertTrue(card.size_field.pressure_link_available())

    def test_escape_closes_card(self) -> None:
        """Escape closes the focused card."""
        card = self.open_card()
        press_key(card, Qt.Key.Key_Escape)
        self.assertFalse(card.isVisible())

    def test_press_outside_closes_card_without_painting(self) -> None:
        """A left press on the canvas outside the card closes it and paints nothing, and a right press doesn't
           reopen it."""
        card = self.open_card()
        far_point = QPoint(0, 0) if card.geometry().center().x() > 100 else QPoint(500, 500)
        initial_image = self.layer.image
        self.mouse_drag([far_point], LEFT)
        self.assertFalse(card.isVisible())
        self.assertEqual(self.layer.image, initial_image)
        self.assertEqual(UndoStack().undo_count(), 0)
        card = self.open_card()
        self.mouse_drag([far_point], RIGHT)
        self.assertFalse(card.isVisible())

    def test_tool_change_closes_card(self) -> None:
        """Deactivating the tool closes the card."""
        card = self.open_card()
        self.tool.is_active = False
        self.assertFalse(card.isVisible())

    def test_pointer_leaving_closes_card(self) -> None:
        """Moving the pointer far outside the card with no button held closes it."""
        card = self.open_card()
        global_rect_center = card.mapToGlobal(card.rect().center())
        far = global_rect_center + QPoint(2000, 2000)
        event = QMouseEvent(QEvent.Type.MouseMove, QPointF(self.image_viewer.viewport().mapFromGlobal(far)),
                            QPointF(far), Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                            Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(self.image_viewer.viewport(), event)
        self.assertFalse(card.isVisible())

    def test_view_change_closes_card(self) -> None:
        """Zooming the view closes the card."""
        card = self.open_card()
        self.image_viewer.scene_scale = 2.0
        self.assertFalse(card.isVisible())

    def test_card_background_press_paints_nothing(self) -> None:
        """Pressing the card's background doesn't reach the canvas."""
        card = self.open_card()
        initial_image = self.layer.image
        local = QPoint(2, 2)
        for event_type, button, buttons in ((QEvent.Type.MouseButtonPress, LEFT, LEFT),
                                            (QEvent.Type.MouseButtonRelease, LEFT, Qt.MouseButton.NoButton)):
            event = QMouseEvent(event_type, QPointF(local), QPointF(card.mapToGlobal(local)), button, buttons,
                                Qt.KeyboardModifier.NoModifier)
            QApplication.sendEvent(card, event)
        self.assertEqual(self.layer.image, initial_image)
        self.assertEqual(UndoStack().undo_count(), 0)
        self.assertTrue(card.isVisible())

    def test_canvas_has_no_context_menu(self) -> None:
        """The canvas prevents context menus, so none opens over the card."""
        self.assertEqual(self.image_viewer.contextMenuPolicy(), Qt.ContextMenuPolicy.PreventContextMenu)
        self.assertEqual(self.image_viewer.viewport().contextMenuPolicy(), Qt.ContextMenuPolicy.PreventContextMenu)

    def test_locked_layer_blocks_card(self) -> None:
        """The card doesn't open while the active layer is locked."""
        self.layer.locked = True
        self.mouse_drag([CENTER], RIGHT)
        self.assertIsNone(self.tool.quick_card)

    def test_color_row(self) -> None:
        """Tools that paint a color show a color row, and clicking a recent color sets the foreground color."""
        card = self.open_card()
        self.assertEqual(card.swatches is not None, self.COLOR_ROW)
        if not self.COLOR_ROW:
            return
        Cache().set(Cache.RECENT_COLORS, ['#ffff0000', '#ff00ff00'])
        swatches = card.swatches
        assert swatches is not None
        self.assertEqual(len(swatches.colors()), 2)
        swatches.color_clicked.emit(QColor('#ff00ff00'))
        self.assertEqual(Cache().get_color(Cache.LAST_BRUSH_COLOR, QColor()), QColor('#ff00ff00'))
        self.assertTrue(card.isVisible())

    def test_color_dialog_closes_card(self) -> None:
        """Opening the color dialog from the card's pair closes the card first, with the dialog mocked."""
        card = self.open_card()
        pair = card.color_pair
        if not self.COLOR_ROW:
            self.assertIsNone(pair)
            return
        assert pair is not None
        with mock.patch('src.ui.widget.color_pair_widget.ColorDialog.show_color_dialog', return_value=None):
            pair.select_foreground()
        self.assertFalse(card.isVisible())


class MyPaintQuickStrokeCardTest(_QuickStrokeCardTestBase):
    """The MyPaint brush tool's card: Size, favorites, color."""
    TOOL_CLASS = MyPaintBrushTool
    SIZE_KEY = Cache.PAINT_TOOL_BRUSH_SIZE
    COLOR_ROW = True

    def test_favorites_row(self) -> None:
        """The row is hidden without favorites, and shows them with the active one checked. Clicking one selects
           the brush and closes the card."""
        AppConfig().set(FAV_CONFIG_KEY, [])
        card = self.open_card()
        row = card.favorites_row
        assert row is not None
        self.assertTrue(row.isHidden())
        card.close_card()
        panel = self.tool.get_control_panel()
        library = panel.brush_panel.library  # type: ignore[union-attr]
        candidates = [path for group in library.categories for path in library.brush_paths(group)][:3]
        self.assertGreaterEqual(len(candidates), 2)
        names = [f'{path.split("/")[-2]}/{path.split("/")[-1][:-4]}' for path in candidates]
        AppConfig().set(FAV_CONFIG_KEY, names)
        card = self.open_card()
        self.assertEqual(len(card.favorite_buttons), len(candidates))
        self.assertFalse(card.favorites_row.isHidden())  # type: ignore[union-attr]
        card.favorite_buttons[1].click()
        self.assertFalse(card.isVisible())
        self.assertTrue(Cache().get(Cache.MYPAINT_BRUSH).endswith(candidates[1].split('/')[-1]))


class DrawQuickStrokeCardTest(_QuickStrokeCardTestBase):
    """The draw tool's card: Size, Opacity, Hardness, color."""
    TOOL_CLASS = DrawTool
    SIZE_KEY = Cache.DRAW_TOOL_BRUSH_SIZE
    OPACITY_KEY = Cache.DRAW_TOOL_OPACITY
    COLOR_ROW = True


class EraserQuickStrokeCardTest(_QuickStrokeCardTestBase):
    """The eraser's card: Size, Opacity, Hardness."""
    TOOL_CLASS = EraserTool
    SIZE_KEY = Cache.ERASER_TOOL_SIZE
    OPACITY_KEY = Cache.ERASER_TOOL_OPACITY


class SmudgeQuickStrokeCardTest(_QuickStrokeCardTestBase):
    """The smudge tool's card: Size, Strength, Hardness."""
    TOOL_CLASS = SmudgeTool
    SIZE_KEY = Cache.SMUDGE_TOOL_BRUSH_SIZE
    OPACITY_KEY = Cache.SMUDGE_TOOL_OPACITY


class OtherToolsKeepRightButtonTest(ToolTestCase):
    """The clone stamp and selection brush tools keep their right button, and never create a card."""

    def test_clone_stamp_and_selection_brush_have_no_card(self) -> None:
        """A right-click in these tools creates no card."""
        layer = self.image_stack.create_layer(image_data=brush_test_pattern(self.IMAGE_SIZE))
        self.image_stack.active_layer = layer
        for tool_class in (CloneStampTool, SelectionBrushTool):
            with self.subTest(tool=tool_class.__name__):
                tool = self.activate_tool(tool_class(self.image_stack, self.image_viewer))
                self.assertIsNone(tool.quick_stroke_keys())
                self.mouse_drag([CENTER], RIGHT)
                self.assertIsNone(tool.quick_card)


del _QuickStrokeCardTestBase
