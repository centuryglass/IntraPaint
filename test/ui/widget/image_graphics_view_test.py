"""Pins how ImageGraphicsView fits, zooms and pans, so a change to its scale and offset bookkeeping shows up as a
failing test. The tests drive the base view directly, with no image stack or subclass."""
import sys
from unittest.mock import patch

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication

from src.config.key_config import KeyConfig
from src.ui.widget.image_graphics_view import ImageGraphicsView, MAX_IMAGE_ZOOM, MIN_IMAGE_ZOOM, ZOOM_FACTOR
from src.util.key_code_utils import get_key_with_modifiers, key_alternatives
from test.base_test_case import IntraPaintTestCase, press_key

app = QApplication.instance() or QApplication(sys.argv)

VIEW_SIZE = QSize(400, 300)
CONTENT_SIZE = QSize(512, 384)
# Distance in scene pixels that a zoom may move the scene point it holds under the cursor. Issue #836 tracks the drift.
ANCHOR_TOLERANCE = 2.0
# Distance in widget pixels between the view center and the center of the bounds zoom_to_bounds shows (issue #836).
ZOOM_TO_BOUNDS_CENTER_TOLERANCE = 6.0


class ImageGraphicsViewTestCase(IntraPaintTestCase):
    """Creates a shown view of VIEW_SIZE with CONTENT_SIZE content and no keybindings."""

    use_keybindings = False

    def setUp(self) -> None:
        super().setUp()
        self.view = ImageGraphicsView(use_keybindings=self.use_keybindings)
        self.view.resize(VIEW_SIZE)
        # The base view divides by the content width on every resize, so content_size comes before show().
        self.view.content_size = CONTENT_SIZE
        self.view.show()

    def scene_point_at(self, widget_point: QPoint) -> QPointF:
        """Returns the scene point shown at a widget point."""
        return self.view.widget_point_to_scene(widget_point)

    def assert_points_close(self, expected: QPointF, actual: QPointF, tolerance: float) -> None:
        """Asserts that two points are within `tolerance` on each axis."""
        self.assertAlmostEqual(expected.x(), actual.x(), delta=tolerance, msg=f'{expected} != {actual}')
        self.assertAlmostEqual(expected.y(), actual.y(), delta=tolerance, msg=f'{expected} != {actual}')


class FitTest(ImageGraphicsViewTestCase):
    """Tests the default view, which fits the content inside the widget with a border."""

    def test_default_view_fits_content_inside_border(self) -> None:
        """The content fills the limiting dimension, less border_size on each side, and is centered."""
        border = self.view.border_size
        bounds = self.view.widget_content_bounds
        self.assertTrue(self.view.is_at_default_view)
        self.assertAlmostEqual(bounds.height(), VIEW_SIZE.height() - 2 * border, delta=2)
        self.assertAlmostEqual(self.view.scene_scale, bounds.width() / CONTENT_SIZE.width(), delta=0.01)
        self.assert_points_close(QPointF(self.view.rect().center()), QPointF(bounds.center()), 1.0)

    def test_resize_keeps_scale_difference_from_fit(self) -> None:
        """A resize changes the fitted scale and keeps scene_scale's difference from it, not its ratio to it."""
        fitted = self.view.scene_scale
        self.view.scene_scale = fitted + 1.0
        self.view.resize(VIEW_SIZE * 2)
        new_fitted = self.view.widget_content_bounds.width() / CONTENT_SIZE.width() - 1.0
        self.assertGreater(new_fitted, fitted)
        self.assertAlmostEqual(self.view.scene_scale, new_fitted + 1.0, delta=0.02)

    def test_resize_emits_view_changed(self) -> None:
        """A resize changes the scene-to-widget mapping, so it emits view_changed."""
        changes: list[bool] = []
        self.view.view_changed.connect(lambda: changes.append(True))
        self.view.resize(VIEW_SIZE + QSize(50, 50))
        self.assertGreater(len(changes), 0)

    def test_reset_scale_restores_default_view(self) -> None:
        """reset_scale undoes zoom and pan, and emits scale_changed with the fitted scale."""
        fitted = self.view.scene_scale
        self.view.scene_scale = 3.0
        self.view.offset = QPointF(25.0, -10.0)
        scales: list[float] = []
        self.view.scale_changed.connect(scales.append)
        self.view.reset_scale()
        self.assertTrue(self.view.is_at_default_view)
        self.assertAlmostEqual(self.view.scene_scale, fitted)
        self.assertAlmostEqual(scales[-1], fitted)

    def test_reset_scale_at_default_scale_does_not_emit(self) -> None:
        """reset_scale emits scale_changed only when the scale was adjusted."""
        scales: list[float] = []
        self.view.scale_changed.connect(scales.append)
        self.view.reset_scale()
        self.assertEqual(scales, [])


class ZoomAnchorTest(ImageGraphicsViewTestCase):
    """Tests which scene point the scene_scale setter holds in place."""

    def _assert_zoom_holds(self, cursor: QPoint | None, held_widget_point: QPoint, scale_multiplier: float) -> None:
        if cursor is not None:
            self.view.set_cursor_pos(cursor)
        before = self.scene_point_at(held_widget_point)
        self.view.scene_scale = self.view.scene_scale * scale_multiplier
        self.assert_points_close(before, self.scene_point_at(held_widget_point), ANCHOR_TOLERANCE)

    def test_zoom_in_holds_point_under_cursor(self) -> None:
        """Zooming in with the cursor over the content keeps the scene point under the cursor in place."""
        for cursor in (QPoint(60, 98), QPoint(171, 185), QPoint(300, 60)):
            with self.subTest(cursor=cursor):
                self.view.reset_scale()
                self._assert_zoom_holds(cursor, cursor, 3.0)

    def test_zoom_out_holds_point_under_cursor(self) -> None:
        """Zooming out from a zoomed view keeps the scene point under the cursor in place."""
        self.view.scene_scale = 4.0
        cursor = QPoint(150, 120)
        self._assert_zoom_holds(cursor, cursor, 0.75)

    def test_zoom_in_with_cursor_outside_content_holds_content_center(self) -> None:
        """Zooming in with the cursor beside the content holds the content center instead."""
        self.view.content_size = QSize(200, 600)
        cursor = QPoint(10, 150)
        self.assertFalse(self.view.widget_content_bounds.contains(cursor))
        self._assert_zoom_holds(cursor, self.view.widget_content_bounds.center(), 2.0)

    def test_zoom_without_cursor_holds_content_center(self) -> None:
        """With no cursor position, zooming holds the content center."""
        self._assert_zoom_holds(None, self.view.widget_content_bounds.center(), 2.0)

    def test_scale_has_lower_limit(self) -> None:
        """The setter raises scales below 0.01 to 0.01. The zoom steps stop higher, at MIN_IMAGE_ZOOM."""
        self.view.scene_scale = 0.0
        self.assertAlmostEqual(self.view.scene_scale, 0.01)

    def test_scale_without_fixed_scene_point_centers_offset_content(self) -> None:
        """scale_without_fixed_scene_point centers the view on the content center moved by the offset."""
        self.view.offset = QPointF(30.0, 20.0)
        self.view.set_cursor_pos(QPoint(20, 20))
        self.view.scale_without_fixed_scene_point(2.0)
        self.assertAlmostEqual(self.view.scene_scale, 2.0)
        expected = QPointF(CONTENT_SIZE.width() / 2 + 30.0, CONTENT_SIZE.height() / 2 + 20.0)
        self.assert_points_close(expected, self.scene_point_at(self.view.rect().center()), 1.0)


class ZoomStepTest(ImageGraphicsViewTestCase):
    """Tests zoom_in and zoom_out, which snap to whole scales near and above 100%."""

    def _step(self, start: float, zoom_in: bool, integer_scaling: bool = True) -> float:
        self.view.scene_scale = start
        if zoom_in:
            self.view.zoom_in(integer_scaling=integer_scaling)
        else:
            self.view.zoom_out(integer_scaling=integer_scaling)
        return self.view.scene_scale

    def test_steps_below_two_multiply_by_zoom_factor(self) -> None:
        """Between whole-scale snaps, a step multiplies or divides by ZOOM_FACTOR."""
        self.assertAlmostEqual(self._step(0.5, True), 0.5 * ZOOM_FACTOR)
        self.assertAlmostEqual(self._step(1.5, False), 1.5 / ZOOM_FACTOR)
        self.assertAlmostEqual(self._step(1.0, True), ZOOM_FACTOR)

    def test_steps_snap_to_one_when_crossing_it(self) -> None:
        """A step that would cross 100% stops on it."""
        self.assertAlmostEqual(self._step(0.95, True), 1.0)
        self.assertAlmostEqual(self._step(1.05, False), 1.0)

    def test_steps_above_two_move_by_whole_scales(self) -> None:
        """Above 200%, a step moves to the next whole scale."""
        self.assertAlmostEqual(self._step(3.0, True), 4.0)
        self.assertAlmostEqual(self._step(2.5, True), 3.0)
        self.assertAlmostEqual(self._step(4.0, False), 3.0)
        self.assertAlmostEqual(self._step(3.5, False), 3.0)
        self.assertAlmostEqual(self._step(1.9, True), 2.0)

    def test_steps_without_integer_scaling_multiply(self) -> None:
        """integer_scaling=False always multiplies or divides by ZOOM_FACTOR."""
        self.assertAlmostEqual(self._step(0.95, True, False), 0.95 * ZOOM_FACTOR)
        self.assertAlmostEqual(self._step(3.0, True, False), 3.0 * ZOOM_FACTOR)
        self.assertAlmostEqual(self._step(4.0, False, False), 4.0 / ZOOM_FACTOR)

    def test_steps_clamp_to_zoom_limits(self) -> None:
        """Steps stop at MIN_IMAGE_ZOOM and MAX_IMAGE_ZOOM."""
        self.assertAlmostEqual(self._step(MAX_IMAGE_ZOOM, True), MAX_IMAGE_ZOOM)
        self.assertAlmostEqual(self._step(MIN_IMAGE_ZOOM * 1.01, False), MIN_IMAGE_ZOOM)


class WheelTest(ImageGraphicsViewTestCase):
    """Tests wheel zoom, which the view handles in its own event filter."""

    def _wheel(self, delta_y: int) -> bool:
        center = QPointF(self.view.rect().center())
        event = QWheelEvent(center, QPointF(self.view.mapToGlobal(center)), QPoint(0, 0), QPoint(0, delta_y),
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase,
                            False)
        return self.view.eventFilter(self.view, event)

    def test_wheel_up_zooms_in_and_down_zooms_out(self) -> None:
        """A wheel step zooms one step, and the filter lets the event continue."""
        start = self.view.scene_scale
        self.assertFalse(self._wheel(120))
        self.assertAlmostEqual(self.view.scene_scale, start * ZOOM_FACTOR)
        self._wheel(-120)
        self.assertAlmostEqual(self.view.scene_scale, start)

    def test_horizontal_wheel_does_not_zoom(self) -> None:
        """A wheel event with no vertical movement leaves the scale alone."""
        start = self.view.scene_scale
        self._wheel(0)
        self.assertAlmostEqual(self.view.scene_scale, start)

    def test_wheel_ignored_without_mouse_navigation(self) -> None:
        """Disabling mouse navigation disables wheel zoom."""
        self.view.mouse_navigation_enabled = False
        start = self.view.scene_scale
        self._wheel(120)
        self.assertAlmostEqual(self.view.scene_scale, start)

    def test_leave_event_clears_cursor(self) -> None:
        """A Leave event reaching the filter clears the cursor position and emits cursor_moved with None."""
        self.view.set_cursor_pos(QPoint(10, 10))
        moves: list[object] = []
        self.view.cursor_moved.connect(moves.append)
        self.view.eventFilter(self.view, QEvent(QEvent.Type.Leave))
        self.assertIsNone(self.view.cursor_pos)
        self.assertEqual(moves, [None])


class OffsetTest(ImageGraphicsViewTestCase):
    """Tests the offset property, which pans in scene pixels."""

    def test_offset_moves_view_center_by_offset(self) -> None:
        """Changing the offset moves the scene point at the widget center by the same amount."""
        self.view.scene_scale = 2.0
        center = self.view.rect().center()
        before = self.scene_point_at(center)
        offsets: list[QPoint] = []
        self.view.offset_changed.connect(offsets.append)
        self.view.offset = self.view.offset + QPointF(30.0, -20.0)
        self.assert_points_close(before + QPointF(30.0, -20.0), self.scene_point_at(center), 1.0)
        self.assertEqual(offsets, [self.view.offset.toPoint()])
        self.assertFalse(self.view.is_at_default_view)

    def test_mapping_round_trips(self) -> None:
        """Mapping a widget point to the scene and back returns the same point, zoomed and panned."""
        self.view.scene_scale = 3.0
        self.view.offset = QPointF(17.0, 9.0)
        for widget_point in (QPoint(0, 0), QPoint(123, 45), QPoint(399, 299)):
            with self.subTest(point=widget_point):
                scene_point = self.view.widget_point_to_scene(widget_point)
                self.assert_points_close(QPointF(widget_point), QPointF(self.view.scene_point_to_widget(scene_point)),
                                         1.0)


class PanDragTest(ImageGraphicsViewTestCase):
    """Tests middle-button pan drags, which keep the grabbed scene point under the cursor at any drag speed."""

    def _middle_drag(self, start: QPoint, step: QPoint, steps: int) -> QPoint:
        """Drags with the middle button from `start` in `steps` moves of `step`, returning the end point."""
        def mouse_event(event_type: QEvent.Type, pos: QPoint, button: Qt.MouseButton,
                        buttons: Qt.MouseButton) -> QMouseEvent:
            return QMouseEvent(event_type, QPointF(pos), QPointF(pos), button, buttons, Qt.KeyboardModifier.NoModifier)

        middle = Qt.MouseButton.MiddleButton
        self.view.mousePressEvent(mouse_event(QEvent.Type.MouseButtonPress, start, middle, middle))
        pos = QPoint(start)
        for _ in range(steps):
            pos += step
            self.view.mouseMoveEvent(mouse_event(QEvent.Type.MouseMove, pos, Qt.MouseButton.NoButton, middle))
        self.view.mouseReleaseEvent(mouse_event(QEvent.Type.MouseButtonRelease, pos, middle,
                                                Qt.MouseButton.NoButton))
        return pos

    def test_drag_keeps_grabbed_point_under_cursor(self) -> None:
        """Slow and fast drags in each direction, zoomed in and out, end with the grabbed point under the cursor."""
        start = QPoint(200, 150)
        for scale in (0.5, 1.0, 2.0):
            for direction in (QPoint(1, 0), QPoint(-1, 0), QPoint(0, 1), QPoint(0, -1)):
                for step_size in (1, 20):
                    with self.subTest(scale=scale, direction=direction, step_size=step_size):
                        self.view.reset_scale()
                        self.view.scene_scale = scale
                        grabbed = self.view.mapToScene(start)
                        end = self._middle_drag(start, direction * step_size, 60 // step_size)
                        tolerance = 2.0 / scale
                        self.assert_points_close(grabbed, self.view.mapToScene(end), tolerance)

    def test_repeated_offset_set_does_not_move_view(self) -> None:
        """Setting the offset to its current value leaves the view in place, however many times it is set."""
        self.view.scene_scale = 1.3
        center = self.view.rect().center()
        before = self.scene_point_at(center)
        for _ in range(20):
            self.view.offset = self.view.offset
        self.assert_points_close(before, self.scene_point_at(center), 1.0)


class ZoomToBoundsTest(ImageGraphicsViewTestCase):
    """Tests zoom_to_bounds, which fills the view with a scene rectangle and a margin."""

    def test_bounds_centered_and_filling_view(self) -> None:
        """The bounds end up fully visible, filling the limiting dimension less a small margin, and centered to within
        ZOOM_TO_BOUNDS_CENTER_TOLERANCE."""
        bounds = QRect(300, 200, 100, 60)
        scales: list[float] = []
        self.view.scale_changed.connect(scales.append)
        self.view.zoom_to_bounds(bounds)
        widget_bounds = self.view.scene_rect_to_widget_rect(bounds.toRectF())
        self.assertTrue(self.view.rect().contains(widget_bounds))
        self.assert_points_close(QPointF(self.view.rect().center()), QPointF(widget_bounds.center()),
                                 ZOOM_TO_BOUNDS_CENTER_TOLERANCE)
        self.assertGreater(widget_bounds.width(), VIEW_SIZE.width() * 0.85)
        self.assertAlmostEqual(scales[-1], self.view.scene_scale)

    def test_reset_after_zoom_to_bounds(self) -> None:
        """reset_scale returns from a zoom_to_bounds view to the default view."""
        self.view.zoom_to_bounds(QRect(10, 10, 50, 50))
        self.view.reset_scale()
        self.assertTrue(self.view.is_at_default_view)


class KeybindingTest(ImageGraphicsViewTestCase):
    """Tests the zoom and pan keys a view with keybindings registers."""

    use_keybindings = True

    def _press_configured_key(self, config_key: str) -> None:
        """Presses the first key bound to `config_key`."""
        key, modifiers = get_key_with_modifiers(key_alternatives(KeyConfig().get(config_key))[0])
        assert key is not None
        # HotkeyFilter matches modifiers against QApplication.keyboardModifiers(), which a sent key event leaves set
        # for later tests, so the modifiers are patched in and the event carries none.
        with patch.object(QApplication, 'keyboardModifiers', return_value=modifiers):
            press_key(self.view, key)

    def test_zoom_keys(self) -> None:
        """The zoom in and zoom out keys step the zoom."""
        start = self.view.scene_scale
        self._press_configured_key(KeyConfig.ZOOM_IN)
        self.assertAlmostEqual(self.view.scene_scale, start * ZOOM_FACTOR)
        self._press_configured_key(KeyConfig.ZOOM_OUT)
        self.assertAlmostEqual(self.view.scene_scale, start)

    def test_pan_keys_move_offset_by_one(self) -> None:
        """Each pan key moves the offset one scene pixel in its direction."""
        for config_key, change in ((KeyConfig.PAN_LEFT, QPointF(-1.0, 0.0)), (KeyConfig.PAN_RIGHT, QPointF(1.0, 0.0)),
                                   (KeyConfig.PAN_UP, QPointF(0.0, -1.0)), (KeyConfig.PAN_DOWN, QPointF(0.0, 1.0))):
            with self.subTest(key=config_key):
                before = self.view.offset
                self._press_configured_key(config_key)
                self.assertEqual(self.view.offset, before + change)

    def test_hidden_view_ignores_keys(self) -> None:
        """A hidden view leaves its keys to other bindings."""
        self.view.hide()
        start = self.view.scene_scale
        self._press_configured_key(KeyConfig.ZOOM_IN)
        self.assertAlmostEqual(self.view.scene_scale, start)
