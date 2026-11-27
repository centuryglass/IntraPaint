"""Tests the RulerGuides model, and the ruler and handle strip gestures, menus and panel wiring that create, move and
delete guides."""
import sys

from PySide6.QtCore import QEvent, QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.hotkey_filter import HotkeyFilter
from src.image.layers.image_stack import ImageStack
from src.ui.canvas_extras import CanvasExtraCategory
from src.ui.panel.image_panel import ImagePanel, MENU_ACTION_CLEAR_GUIDES, MENU_ACTION_LOCK_GUIDES
from src.ui.widget.guide_handle_bar import GuideHandleBar, GuideHandleStrip, MENU_ACTION_DELETE_GUIDE
from src.ui.widget.ruler import Ruler
from src.ui.widget.ruler_guides import RulerGuides
from src.undo_stack import UndoStack
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

IMAGE_SIZE = QSize(512, 384)
PANEL_SIZE = QSize(800, 600)
HORIZONTAL = Qt.Orientation.Horizontal
VERTICAL = Qt.Orientation.Vertical
LEFT = Qt.MouseButton.LeftButton


class RulerGuidesModelTest(IntraPaintTestCase):
    """Tests the guide model."""

    def setUp(self) -> None:
        super().setUp()
        self.guides = RulerGuides()
        self.changes = 0

        def _count() -> None:
            self.changes += 1
        self.guides.guides_changed.connect(_count)

    def test_add_move_remove(self) -> None:
        """Each change to the guide set emits once, and no-op changes emit nothing."""
        self.guides.add(HORIZONTAL, 10)
        self.guides.add(VERTICAL, 20)
        self.assertEqual(self.guides.positions(HORIZONTAL), [10])
        self.assertEqual(self.guides.positions(VERTICAL), [20])
        self.assertEqual(self.guides.count, 2)
        self.guides.move(HORIZONTAL, 10, 30)
        self.assertEqual(self.guides.positions(HORIZONTAL), [30])
        self.guides.move(HORIZONTAL, 99, 5)
        self.guides.move(HORIZONTAL, 30, 30)
        self.guides.remove(HORIZONTAL, 99)
        self.assertEqual(self.changes, 3)
        self.guides.remove(HORIZONTAL, 30)
        self.assertEqual(self.guides.positions(HORIZONTAL), [])
        self.assertEqual(self.changes, 4)

    def test_clear(self) -> None:
        """Clearing removes every guide, and clearing an empty set emits nothing."""
        self.guides.clear()
        self.assertEqual(self.changes, 0)
        self.guides.add(HORIZONTAL, 1)
        self.guides.add(VERTICAL, 2)
        self.guides.clear()
        self.assertEqual(self.guides.count, 0)
        self.assertEqual(self.changes, 3)

    def test_prune(self) -> None:
        """Pruning drops guides outside [0, size] on their own axis only, emitting once."""
        for position in (0, 40, 41):
            self.guides.add(HORIZONTAL, position)
        for position in (0, 50, 51):
            self.guides.add(VERTICAL, position)
        self.changes = 0
        self.guides.prune(QSize(50, 40))
        self.assertEqual(self.guides.positions(HORIZONTAL), [0, 40])
        self.assertEqual(self.guides.positions(VERTICAL), [0, 50])
        self.assertEqual(self.changes, 1)
        self.guides.prune(QSize(50, 40))
        self.assertEqual(self.changes, 1)

    def test_lock(self) -> None:
        """Locking emits only when the flag changes."""
        self.guides.locked = True
        self.guides.locked = True
        self.assertTrue(self.guides.locked)
        self.assertEqual(self.changes, 1)


class GuidePanelTestCase(IntraPaintTestCase):
    """Builds an ImagePanel with rulers, and sends synthetic mouse events to its guide handle bars."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(IMAGE_SIZE, QSize(256, 256), QSize(8, 8), QSize(2048, 2048), UndoStack())
        self.panel = ImagePanel(self.image_stack, HotkeyFilter(), include_rulers=True)
        self.panel.resize(PANEL_SIZE)
        self.panel.show()
        self.viewer = self.panel.image_viewer
        self.viewer.scene_scale = 1.0
        horizontal, vertical = self.panel.rulers
        assert horizontal is not None and vertical is not None
        self.horizontal: Ruler = horizontal
        self.vertical: Ruler = vertical
        guides = self.panel.guides
        assert guides is not None
        self.guides: RulerGuides = guides

    def tearDown(self) -> None:
        self.panel.close()
        self.panel.deleteLater()
        super().tearDown()

    @staticmethod
    def _send(ruler: GuideHandleBar, event_type: QEvent.Type, local_pos: QPointF, button: Qt.MouseButton,
              buttons: Qt.MouseButton) -> None:
        event = QMouseEvent(event_type, local_pos, QPointF(ruler.mapToGlobal(local_pos)), button, buttons,
                            Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(ruler, event)

    def _drag(self, ruler: GuideHandleBar, points: list[QPointF]) -> None:
        """Presses at the first ruler-local point, moves through the rest and releases at the last."""
        self._send(ruler, QEvent.Type.MouseButtonPress, points[0], LEFT, LEFT)
        for point in points[1:]:
            self._send(ruler, QEvent.Type.MouseMove, point, Qt.MouseButton.NoButton, LEFT)
        self._send(ruler, QEvent.Type.MouseButtonRelease, points[-1], LEFT, Qt.MouseButton.NoButton)

    def _view_point(self, ruler: GuideHandleBar, image_x: float, image_y: float) -> QPointF:
        """Returns the ruler-local position of an image point."""
        viewport = self.viewer.viewport()
        assert viewport is not None
        view_pos = self.viewer.mapFromScene(QPointF(image_x, image_y))
        return QPointF(ruler.mapFromGlobal(viewport.mapToGlobal(QPointF(view_pos))))

    def _handle_point(self, ruler: Ruler, coordinate: int) -> QPointF:
        """Returns a ruler-local point on the handle of the guide at a coordinate."""
        along = ruler.image_to_position(coordinate)
        across = ruler.thickness - 4
        return QPointF(along, across) if ruler.orientation == HORIZONTAL else QPointF(across, along)


class RulerGuideGestureTest(GuidePanelTestCase):
    """Drives the rulers of an ImagePanel with synthetic mouse events."""

    def test_create_horizontal_guide_from_top_ruler(self) -> None:
        """Dragging from the top ruler into the view creates a horizontal guide at the rounded image y."""
        start = self._handle_point(self.horizontal, 100)
        self._drag(self.horizontal, [start, self._view_point(self.horizontal, 50.0, 120.4)])
        self.assertEqual(self.guides.positions(HORIZONTAL), [120])
        self.assertEqual(self.guides.positions(VERTICAL), [])

    def test_create_vertical_guide_from_left_ruler(self) -> None:
        """Dragging from the left ruler into the view creates a vertical guide at the rounded image x."""
        start = self._handle_point(self.vertical, 100)
        self._drag(self.vertical, [start, self._view_point(self.vertical, 200.6, 50.0)])
        self.assertEqual(self.guides.positions(VERTICAL), [201])

    def test_create_clamps_to_image(self) -> None:
        """A guide dragged past the image edge is clamped onto it."""
        end = self._view_point(self.horizontal, 10.0, IMAGE_SIZE.height() + 20.0)
        self._drag(self.horizontal, [self._handle_point(self.horizontal, 5), end])
        self.assertEqual(self.guides.positions(HORIZONTAL), [IMAGE_SIZE.height()])

    def test_create_follows_cursor_and_shows_line(self) -> None:
        """While dragging, a guide line item follows the cursor, and it is kept when the drag ends."""
        panel_ruler = self.horizontal
        self._send(panel_ruler, QEvent.Type.MouseButtonPress, self._handle_point(panel_ruler, 5), LEFT, LEFT)
        self.assertEqual(self.panel.guide_line_items, [])
        self._send(panel_ruler, QEvent.Type.MouseMove, self._view_point(panel_ruler, 5.0, 60.0),
                   Qt.MouseButton.NoButton, LEFT)
        self.assertEqual([item.position for item in self.panel.guide_line_items], [60])
        self._send(panel_ruler, QEvent.Type.MouseMove, self._view_point(panel_ruler, 5.0, 70.0),
                   Qt.MouseButton.NoButton, LEFT)
        self.assertEqual([item.position for item in self.panel.guide_line_items], [70])
        self._send(panel_ruler, QEvent.Type.MouseButtonRelease, self._view_point(panel_ruler, 5.0, 70.0), LEFT,
                   Qt.MouseButton.NoButton)
        self.assertEqual([item.position for item in self.panel.guide_line_items], [70])
        self.assertEqual(self.guides.positions(HORIZONTAL), [70])

    def test_release_over_ruler_creates_nothing(self) -> None:
        """Dragging into the view and back over the ruler before releasing creates no guide."""
        start = self._handle_point(self.horizontal, 100)
        self._drag(self.horizontal, [start, self._view_point(self.horizontal, 50.0, 120.0),
                                     self._handle_point(self.horizontal, 100)])
        self.assertEqual(self.guides.count, 0)
        self.assertEqual(self.panel.guide_line_items, [])

    def test_release_outside_view_creates_nothing(self) -> None:
        """Releasing outside the view creates no guide."""
        self._drag(self.horizontal, [self._handle_point(self.horizontal, 100), QPointF(-500.0, -500.0)])
        self.assertEqual(self.guides.count, 0)

    def test_move_guide_by_handle(self) -> None:
        """Dragging a handle along its ruler moves the guide to the whole pixel under the cursor."""
        self.guides.add(HORIZONTAL, 100)
        handle = self._handle_point(self.vertical, 100)
        self._drag(self.vertical, [handle, self._handle_point(self.vertical, 150) + QPointF(0.0, 0.3)])
        self.assertEqual(self.guides.positions(HORIZONTAL), [150])
        self.guides.add(VERTICAL, 40)
        self._drag(self.horizontal, [self._handle_point(self.horizontal, 40), self._handle_point(self.horizontal, 90)])
        self.assertEqual(self.guides.positions(VERTICAL), [90])

    def test_move_clamps_to_image(self) -> None:
        """A handle dragged along the ruler past the image edge stops at the edge."""
        self.guides.add(HORIZONTAL, 100)
        self._drag(self.vertical, [self._handle_point(self.vertical, 100), self._handle_point(self.vertical, 5000)])
        self.assertEqual(self.guides.positions(HORIZONTAL), [IMAGE_SIZE.height()])

    def test_drag_handle_off_ruler_deletes(self) -> None:
        """Releasing a handle more than a ruler thickness off its ruler deletes the guide, and the line is hidden
        while pending."""
        self.guides.add(HORIZONTAL, 100)
        handle = self._handle_point(self.vertical, 100)
        far = QPointF(self.vertical.thickness * 2 + 5, handle.y())
        self._send(self.vertical, QEvent.Type.MouseButtonPress, handle, LEFT, LEFT)
        self._send(self.vertical, QEvent.Type.MouseMove, far, Qt.MouseButton.NoButton, LEFT)
        self.assertEqual(self.panel.guide_line_items, [])
        self.assertEqual(self.guides.positions(HORIZONTAL), [100])
        self._send(self.vertical, QEvent.Type.MouseButtonRelease, far, LEFT, Qt.MouseButton.NoButton)
        self.assertEqual(self.guides.positions(HORIZONTAL), [])

    def test_drag_handle_back_before_release_keeps_guide(self) -> None:
        """Coming back within range before release cancels the delete."""
        self.guides.add(HORIZONTAL, 100)
        handle = self._handle_point(self.vertical, 100)
        far = QPointF(self.vertical.thickness * 2 + 5, handle.y())
        self._drag(self.vertical, [handle, far, handle + QPointF(0.0, 20.0)])
        self.assertEqual(self.guides.positions(HORIZONTAL), [120])
        self.assertEqual(len(self.panel.guide_line_items), 1)

    def test_locked_guides_ignore_handle_presses(self) -> None:
        """A locked guide can't be moved or drag-deleted, but a new guide can still be created."""
        self.guides.add(HORIZONTAL, 100)
        self.guides.locked = True
        handle = self._handle_point(self.vertical, 100)
        self._drag(self.vertical, [handle, self._handle_point(self.vertical, 150)])
        self.assertEqual(self.guides.positions(HORIZONTAL), [100])
        self._drag(self.vertical, [handle, QPointF(self.vertical.thickness * 3.0, handle.y())])
        self.assertEqual(self.guides.positions(HORIZONTAL), [100])
        self._drag(self.horizontal, [self._handle_point(self.horizontal, 100),
                                     self._view_point(self.horizontal, 10.0, 200.0)])
        self.assertEqual(self.guides.positions(HORIZONTAL), [100, 200])

    def test_handle_hit_area(self) -> None:
        """Handles are hit across the ruler's whole thickness and a little to each side along it."""
        self.guides.add(HORIZONTAL, 100)
        along = self.vertical.image_to_position(100)
        self.assertEqual(self.vertical.guide_handle_at(QPointF(1.0, along + 5)), 100)
        self.assertEqual(self.vertical.guide_handle_at(QPointF(self.vertical.thickness - 1.0, along)), 100)
        self.assertIsNone(self.vertical.guide_handle_at(QPointF(1.0, along + 40)))
        self.assertIsNone(self.horizontal.guide_handle_at(QPointF(along, 1.0)))

    def test_context_menu_delete_guide(self) -> None:
        """The menu on a handle starts with Delete guide, which removes only that guide, even while locked."""
        self.guides.add(HORIZONTAL, 100)
        self.guides.add(HORIZONTAL, 200)
        self.guides.locked = True
        menu = self.vertical.build_context_menu(self._handle_point(self.vertical, 100).toPoint())
        texts = [action.text() for action in menu.actions() if not action.isSeparator()]
        self.assertEqual(texts[0], MENU_ACTION_DELETE_GUIDE)
        menu.actions()[0].trigger()
        self.assertEqual(self.guides.positions(HORIZONTAL), [200])

    def test_context_menu_without_handle(self) -> None:
        """Away from a handle the menu has the ruler actions but no Delete guide."""
        menu = self.vertical.build_context_menu(QPoint(2, 2))
        texts = [action.text() for action in menu.actions()]
        self.assertNotIn(MENU_ACTION_DELETE_GUIDE, texts)
        self.assertIn(MENU_ACTION_CLEAR_GUIDES, texts)
        self.assertIn(MENU_ACTION_LOCK_GUIDES, texts)

    def test_clear_and_lock_actions(self) -> None:
        """Clear guides removes every guide and Lock guides toggles the lock."""
        self.guides.add(HORIZONTAL, 100)
        self.guides.add(VERTICAL, 100)
        menu = self.horizontal.build_context_menu(QPoint(2, 2))
        actions = {action.text(): action for action in menu.actions()}
        actions[MENU_ACTION_LOCK_GUIDES].setChecked(True)
        self.assertTrue(self.guides.locked)
        actions[MENU_ACTION_CLEAR_GUIDES].trigger()
        self.assertEqual(self.guides.count, 0)
        self.assertEqual(self.panel.guide_line_items, [])
        actions[MENU_ACTION_LOCK_GUIDES].setChecked(False)
        self.assertFalse(self.guides.locked)

    def test_size_change_prunes_guides(self) -> None:
        """Shrinking the image removes guides outside it, and keeps the rest at their coordinates."""
        self.guides.add(HORIZONTAL, 300)
        self.guides.add(HORIZONTAL, 50)
        self.guides.add(VERTICAL, 400)
        self.guides.add(VERTICAL, 60)
        self.image_stack.size = QSize(200, 100)
        self.assertEqual(self.guides.positions(HORIZONTAL), [50])
        self.assertEqual(self.guides.positions(VERTICAL), [60])
        self.assertEqual(len(self.panel.guide_line_items), 2)

    def test_hiding_rulers_keeps_guide_lines(self) -> None:
        """Guide lines stay visible while the rulers are hidden."""
        self.guides.add(HORIZONTAL, 100)
        item = self.panel.guide_line_items[0]
        AppConfig().set(AppConfig.SHOW_RULERS, False)
        self.assertTrue(item.isVisible())
        self.assertTrue(self.viewer.canvas_extras.is_shown(CanvasExtraCategory.GUIDES))
        AppConfig().set(AppConfig.SHOW_RULERS, True)
        self.assertTrue(item.isVisible())
        self.assertEqual(self.guides.positions(HORIZONTAL), [100])

    def test_guide_lines_accept_no_input(self) -> None:
        """Guide line items take no mouse buttons and no hover events."""
        self.guides.add(VERTICAL, 100)
        item = self.panel.guide_line_items[0]
        self.assertEqual(item.acceptedMouseButtons(), Qt.MouseButton.NoButton)
        self.assertFalse(item.acceptHoverEvents())
        self.assertEqual(item.length, IMAGE_SIZE.height())


class GuideHandleStripTest(GuidePanelTestCase):
    """Drives the guide handle strips that replace the rulers while they are hidden."""

    def setUp(self) -> None:
        super().setUp()
        AppConfig().set(AppConfig.SHOW_RULERS, False)
        self.top_strip, self.left_strip = self.panel.guide_handle_strips

    def _strip_handle_point(self, strip: GuideHandleStrip, coordinate: int) -> QPointF:
        """Returns a strip-local point on the drawn handle of the guide at a coordinate."""
        along = strip.image_to_position(coordinate)
        across = strip.thickness * 0.25
        return QPointF(along, across) if strip.orientation == HORIZONTAL else QPointF(across, along)

    def test_strips_follow_ruler_visibility(self) -> None:
        """Strips with handles in view show only while the rulers are hidden."""
        self.guides.add(HORIZONTAL, 100)
        self.guides.add(VERTICAL, 100)
        self.assertTrue(self.top_strip.isVisible())
        self.assertTrue(self.left_strip.isVisible())
        AppConfig().set(AppConfig.SHOW_RULERS, True)
        self.assertFalse(self.top_strip.isVisible())
        self.assertFalse(self.left_strip.isVisible())

    def test_strip_hidden_without_handles(self) -> None:
        """A strip with no handles in view is hidden, so it never covers the view."""
        self.assertFalse(self.top_strip.isVisible())
        self.guides.add(HORIZONTAL, 100)
        self.assertFalse(self.top_strip.isVisible())
        self.assertTrue(self.left_strip.isVisible())

    def test_strips_cover_viewport_edges(self) -> None:
        """Each strip starts at the viewport's corner and spans its edge, so handles sit against the edge."""
        self.guides.add(HORIZONTAL, 100)
        self.guides.add(VERTICAL, 100)
        viewport = self.viewer.viewport()
        assert viewport is not None
        corner = viewport.mapToGlobal(QPoint(0, 0))
        for strip in (self.top_strip, self.left_strip):
            self.assertEqual(strip.mapToGlobal(QPoint(0, 0)), corner)
        self.assertEqual(self.top_strip.width(), viewport.width())
        self.assertEqual(self.left_strip.height(), viewport.height())

    def test_mask_covers_only_handles(self) -> None:
        """Strip input is limited to handle hit areas, leaving the rest of the edge to the view's tools."""
        self.guides.add(VERTICAL, 100)
        mask = self.top_strip.mask()
        self.assertTrue(mask.contains(self._strip_handle_point(self.top_strip, 100).toPoint()))
        self.assertFalse(mask.contains(self._strip_handle_point(self.top_strip, 200).toPoint()))
        self.guides.move(VERTICAL, 100, 200)
        self.assertTrue(self.top_strip.mask().contains(self._strip_handle_point(self.top_strip, 200).toPoint()))

    def test_move_guide_by_strip_handle(self) -> None:
        """Dragging a strip handle along the edge moves its guide, and the line follows mid-drag."""
        self.guides.add(HORIZONTAL, 100)
        handle = self._strip_handle_point(self.left_strip, 100)
        self._send(self.left_strip, QEvent.Type.MouseButtonPress, handle, LEFT, LEFT)
        self._send(self.left_strip, QEvent.Type.MouseMove, self._strip_handle_point(self.left_strip, 150),
                   Qt.MouseButton.NoButton, LEFT)
        self.assertEqual([item.position for item in self.panel.guide_line_items], [150])
        self._send(self.left_strip, QEvent.Type.MouseButtonRelease, self._strip_handle_point(self.left_strip, 150),
                   LEFT, Qt.MouseButton.NoButton)
        self.assertEqual(self.guides.positions(HORIZONTAL), [150])

    def test_drag_strip_handle_into_view_deletes(self) -> None:
        """Dragging a strip handle more than a strip thickness into the view and releasing deletes the guide."""
        self.guides.add(VERTICAL, 100)
        handle = self._strip_handle_point(self.top_strip, 100)
        far = QPointF(handle.x(), self.top_strip.thickness * 2 + 5)
        self._drag(self.top_strip, [handle, far])
        self.assertEqual(self.guides.positions(VERTICAL), [])
        self.assertFalse(self.top_strip.isVisible())

    def test_strip_press_off_handle_creates_nothing(self) -> None:
        """Strips can't create guides."""
        self.guides.add(VERTICAL, 100)
        self._drag(self.top_strip, [self._strip_handle_point(self.top_strip, 300),
                                    self._view_point(self.top_strip, 300.0, 200.0)])
        self.assertEqual(self.guides.positions(HORIZONTAL), [])
        self.assertEqual(self.guides.positions(VERTICAL), [100])

    def test_strip_context_menu(self) -> None:
        """A strip handle's menu has Delete guide, Lock guides and Clear guides."""
        self.guides.add(VERTICAL, 100)
        menu = self.top_strip.build_context_menu(self._strip_handle_point(self.top_strip, 100).toPoint())
        texts = [action.text() for action in menu.actions() if not action.isSeparator()]
        self.assertEqual(texts, [MENU_ACTION_DELETE_GUIDE, MENU_ACTION_LOCK_GUIDES, MENU_ACTION_CLEAR_GUIDES])
