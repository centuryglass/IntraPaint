"""Tests the layer transform tool through mouse input on the canvas and edits in its control panel."""
import math
import unittest

from PySide6.QtCore import QPoint, QPointF, QRectF
from PySide6.QtGui import QImage, QTransform, Qt
from PySide6.QtWidgets import QMenu

from src.tools.layer_transform_tool import LayerTransformTool
from src.ui.graphics_items.transform_outline import (TransformOutline, ORIGIN_HANDLE_ID, BR_HANDLE_ID,
                                                     TRANSFORM_MODE_ROTATE)
from src.ui.input_fields.geometry_block import ANGLE, HEIGHT, SCALE_X, WIDTH, X, Y
from src.ui.panel.tool_control_panels.layer_transform_tool_panel import LayerTransformToolPanel
from src.undo_stack import UndoStack
from src.util.visual.geometry_utils import extract_transform_parameters
from test.render_assertions import full_render
from test.tools.tool_test_case import ToolTestCase

LAYER_WIDTH = 200
LAYER_HEIGHT = 100
LAYER_OFFSET = QPoint(100, 150)

# Tolerance in pixels for positions computed through matrix decomposition:
POSITION_TOLERANCE = 0.01


class LayerTransformToolTest(ToolTestCase):
    """Tests the transform tool's canvas outline, control panel and layer transform staying in agreement."""

    def setUp(self) -> None:
        super().setUp()
        image = QImage(LAYER_WIDTH, LAYER_HEIGHT, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.red)
        self.layer = self.image_stack.create_layer(image_data=image, transform=QTransform.fromTranslate(
            LAYER_OFFSET.x(), LAYER_OFFSET.y()))
        self.image_stack.active_layer = self.layer
        self.tool = LayerTransformTool(self.image_stack, self.image_viewer)
        self.tool_controller.add_tool(self.tool)
        self.activate_tool(self.tool)
        self.outline: TransformOutline = self.tool._transform_outline
        self.panel: LayerTransformToolPanel = self.tool._control_panel
        UndoStack().clear()

    def _scene_point_of(self, layer_point: QPointF) -> QPointF:
        """Maps a point in the layer's untransformed coordinates through the layer's current transform."""
        return self.layer.transform.map(layer_point)

    def _scene_corners(self) -> list[QPointF]:
        return [self._scene_point_of(QPointF(x, y)) for x, y in ((0, 0), (LAYER_WIDTH, 0), (0, LAYER_HEIGHT),
                                                                 (LAYER_WIDTH, LAYER_HEIGHT))]

    def assert_points_equal(self, actual: QPointF, expected: QPointF, msg: str = '') -> None:
        """Asserts that two points are within POSITION_TOLERANCE of each other on both axes."""
        self.assertAlmostEqual(actual.x(), expected.x(), delta=POSITION_TOLERANCE, msg=f'{msg} x: {actual} {expected}')
        self.assertAlmostEqual(actual.y(), expected.y(), delta=POSITION_TOLERANCE, msg=f'{msg} y: {actual} {expected}')

    def assert_panel_matches_state(self) -> None:
        """Asserts that every panel field shows the tool state's current value."""
        origin = self.tool.state.origin_pos
        self.assertAlmostEqual(self.panel.x_position, origin.x(), places=2)
        self.assertAlmostEqual(self.panel.y_position, origin.y(), places=2)
        self.assertAlmostEqual(self.panel.layer_width, self.tool.state.width, places=2)
        self.assertAlmostEqual(self.panel.layer_height, self.tool.state.height, places=2)
        x_scale, y_scale = self.tool.state.x_scale, self.tool.state.y_scale
        self.assertAlmostEqual(self.panel.x_scale, x_scale, places=2)
        self.assertAlmostEqual(self.panel.y_scale, y_scale, places=2)
        self.assertAlmostEqual(self.panel.rotation, self.tool.state.rotation, places=2)

    def _handle_image_point(self, handle_id: str) -> QPoint:
        handle = self.outline._handles[handle_id]
        scene_point = handle.mapToScene(handle.rect().center())
        return QPoint(int(scene_point.x()), int(scene_point.y()))

    def test_activate_loads_layer(self) -> None:
        """Activating the tool loads the active layer's transform into the outline and the panel."""
        self.assertEqual(self.outline.transform(), self.layer.transform)
        self.assertEqual(self.outline.rect(), QRectF(0, 0, LAYER_WIDTH, LAYER_HEIGHT))
        self.assertEqual(self.panel.x_position, LAYER_OFFSET.x() + LAYER_WIDTH / 2)
        self.assertEqual(self.panel.y_position, LAYER_OFFSET.y() + LAYER_HEIGHT / 2)
        self.assertEqual(self.panel.layer_width, LAYER_WIDTH)
        self.assertEqual(self.panel.layer_height, LAYER_HEIGHT)
        self.assertEqual(self.panel.x_scale, 1.0)
        self.assertEqual(self.panel.y_scale, 1.0)
        self.assertEqual(self.panel.rotation, 0.0)

    def test_drag_moves_layer(self) -> None:
        """Dragging inside the layer moves it by the drag distance and updates the panel."""
        start = QPoint(LAYER_OFFSET.x() + 20, LAYER_OFFSET.y() + 20)
        self.mouse_drag([start, start + QPoint(10, 5), start + QPoint(30, 40)])
        self.assert_points_equal(self._scene_point_of(QPointF()), QPointF(LAYER_OFFSET + QPoint(30, 40)))
        self.assertEqual(self.outline.transform(), self.layer.transform)
        self.assert_panel_matches_state()

    def test_drag_undo(self) -> None:
        """Undoing a drag merged into one undo entry restores the layer's original position."""
        original = self.layer.transform
        start = QPoint(LAYER_OFFSET.x() + 20, LAYER_OFFSET.y() + 20)
        self.mouse_drag([start, start + QPoint(10, 5), start + QPoint(30, 40)])
        self.assertNotEqual(self.layer.transform, original)
        UndoStack().undo()
        self.assertEqual(self.layer.transform, original)
        self.assertEqual(self.outline.transform(), original)
        self.assert_panel_matches_state()

    def test_drag_previews_without_changing_layer(self) -> None:
        """While the button is held, a preview item moves and the layer's transform stays as it was."""
        original = self.layer.transform
        start = QPoint(LAYER_OFFSET.x() + 20, LAYER_OFFSET.y() + 20)
        self.mouse_press(start)
        self.mouse_move(start + QPoint(10, 5))
        self.mouse_move(start + QPoint(30, 40))
        self.assertEqual(self.layer.transform, original)
        self.assertFalse(self.layer.visible)
        preview = self.tool._drag_preview
        self.assertIsNotNone(preview)
        self.assertEqual(preview.transform(), self.outline.transform())
        self.assert_panel_matches_state()
        self.mouse_release(start + QPoint(30, 40))
        self.assertIsNone(self.tool._drag_preview)
        self.assertTrue(self.layer.visible)

    def test_drag_result_matches_direct_transform(self) -> None:
        """A drag leaves the same composite and undo history as setting the final transform directly."""
        start = QPoint(LAYER_OFFSET.x() + 20, LAYER_OFFSET.y() + 20)
        self.mouse_drag([start, start + QPoint(10, 5), start + QPoint(30, 40)])
        self.image_stack.flush_render()
        dragged = full_render(self.image_stack)
        dragged_transform = self.layer.transform
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.layer.transform = dragged_transform
        self.image_stack.flush_render()
        self.assertEqual(full_render(self.image_stack), dragged)

    def test_canceled_drag_leaves_composite_unchanged(self) -> None:
        """Deselecting the layer mid-drag discards the preview and restores the layer and composite."""
        self.image_stack.flush_render()
        before = full_render(self.image_stack)
        original = self.layer.transform
        start = QPoint(LAYER_OFFSET.x() + 20, LAYER_OFFSET.y() + 20)
        self.mouse_press(start)
        self.mouse_move(start + QPoint(30, 40))
        self.assertIsNotNone(self.tool._drag_preview)
        self.tool.set_layer(None)
        self.assertIsNone(self.tool._drag_preview)
        self.assertTrue(self.layer.visible)
        self.assertEqual(self.layer.transform, original)
        self.image_stack.flush_render()
        self.assertEqual(full_render(self.image_stack), before)

    def test_non_left_click_does_not_start_drag(self) -> None:
        """A middle or right click on the outline leaves no drag in progress, so activating another layer shows it
        normally instead of as a drag preview."""
        lower_image = QImage(LAYER_WIDTH * 2, LAYER_HEIGHT * 2, QImage.Format.Format_ARGB32_Premultiplied)
        lower_image.fill(Qt.GlobalColor.blue)
        lower_layer = self.image_stack.create_layer(image_data=lower_image, layer_index=1)
        self.image_stack.active_layer = self.layer
        click_point = QPoint(LAYER_OFFSET.x() + 20, LAYER_OFFSET.y() + 20)
        for button in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            with self.subTest(button=button):
                self.mouse_press(click_point, button)
                self.mouse_release(click_point, button)
                self._close_layer_menu()
                self.image_stack.active_layer = lower_layer
                self.assertIsNone(self.tool._drag_preview)
                self.assertTrue(lower_layer.visible)
                self.tool.set_x(self.panel.x_position + 5)
                self.assertIsNone(self.tool._drag_preview)
                self.assertTrue(lower_layer.visible)
                self.image_stack.active_layer = self.layer

    def _close_layer_menu(self) -> None:
        """Closes the layer menu a right click opens, if any."""
        menu = self.tool._layer_menu
        if menu is not None:
            menu.close()

    def test_drag_is_one_undo_step(self) -> None:
        """One drag adds one undo entry."""
        start = QPoint(LAYER_OFFSET.x() + 20, LAYER_OFFSET.y() + 20)
        self.mouse_drag([start, start + QPoint(10, 5), start + QPoint(30, 40)])
        self.assertEqual(UndoStack().undo_count(), 1)

    def test_handle_drag_is_one_undo_step(self) -> None:
        """A corner handle drag adds one undo entry. An origin handle drag, which leaves the layer in place, adds none.
           Both are drags from press to release."""
        for handle_id, undo_count in ((BR_HANDLE_ID, 1), (ORIGIN_HANDLE_ID, 0)):
            with self.subTest(handle_id):
                UndoStack().clear()
                start = self._handle_image_point(handle_id)
                self.mouse_press(start)
                self.mouse_move(start + QPoint(10, 5))
                self.mouse_move(start + QPoint(30, 20))
                self.assertTrue(self.tool._mouse_dragging)
                self.mouse_release(start + QPoint(30, 20))
                self.assertFalse(self.tool._mouse_dragging)
                self.assertEqual(UndoStack().undo_count(), undo_count)

    def test_corner_drag_uses_preview(self) -> None:
        """While a corner handle is held, a preview item scales and the layer's transform stays as it was."""
        original = self.layer.transform
        start = self._handle_image_point(BR_HANDLE_ID)
        self.mouse_press(start)
        self.mouse_move(start + QPoint(50, 25))
        self.assertEqual(self.layer.transform, original)
        self.assertIsNotNone(self.tool._drag_preview)
        self.mouse_release(start + QPoint(50, 25))
        self.assertIsNone(self.tool._drag_preview)
        self.assertNotEqual(self.layer.transform, original)
        self.assertEqual(self.outline.transform(), self.layer.transform)

    def test_panel_field_drag_is_one_undo_step(self) -> None:
        """Scrub-dragging a panel field adds one undo entry, and undoing it restores the original transform."""
        original = self.layer.transform
        field = self.panel.geometry_block.field(X)
        field.dragStarted.emit()
        for x_pos in (10.0, 20.0, 30.0):
            field.set_value(x_pos)
        field.dragFinished.emit()
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assertEqual(self.layer.transform, original)
        self.assert_panel_matches_state()

    def test_corner_drag_scales(self) -> None:
        """Dragging the bottom-right handle scales the layer and leaves the top-left corner fixed."""
        start = self._handle_image_point(BR_HANDLE_ID)
        self.mouse_drag([start, start + QPoint(50, 25), start + QPoint(100, 50)])
        self.assert_points_equal(self._scene_point_of(QPointF()), QPointF(LAYER_OFFSET))
        self.assertAlmostEqual(self.tool.state.width, LAYER_WIDTH * 1.5, delta=1.0)
        self.assertAlmostEqual(self.tool.state.height, LAYER_HEIGHT * 1.5, delta=1.0)
        self.assertEqual(self.outline.transform(), self.layer.transform)
        self.assert_panel_matches_state()

    def test_panel_position(self) -> None:
        """Setting X and Y in the panel puts the transformation origin there, and the fields read back what was set."""
        self.panel.geometry_block.field(X).set_value(40.0)
        self.panel.geometry_block.field(Y).set_value(60.0)
        self.assert_points_equal(self._scene_point_of(QPointF(LAYER_WIDTH / 2, LAYER_HEIGHT / 2)), QPointF(40.0, 60.0))
        self.assertEqual(self.panel.x_position, 40.0)
        self.assertEqual(self.panel.y_position, 60.0)
        self.assert_panel_matches_state()

    def test_panel_position_stable_under_rotation_and_resize(self) -> None:
        """Rotating or resizing in the panel leaves X and Y unchanged."""
        before = (self.panel.x_position, self.panel.y_position)
        self.panel.geometry_block.field(ANGLE).set_value(45.0)
        self.panel.geometry_block.field(WIDTH).set_value(LAYER_WIDTH * 2.0)
        self.assertAlmostEqual(self.panel.x_position, before[0], places=2)
        self.assertAlmostEqual(self.panel.y_position, before[1], places=2)
        self.assert_panel_matches_state()

    def test_panel_size(self) -> None:
        """Setting width and height in the panel scales the layer to that size and updates the scale fields."""
        self.panel.geometry_block.field(WIDTH).set_value(LAYER_WIDTH * 2.0)
        self.panel.geometry_block.field(HEIGHT).set_value(LAYER_HEIGHT * 0.5)
        self.assertAlmostEqual(self.tool.state.width, LAYER_WIDTH * 2.0, places=2)
        self.assertAlmostEqual(self.tool.state.height, LAYER_HEIGHT * 0.5, places=2)
        self.assertAlmostEqual(self.panel.x_scale, 2.0, places=2)
        self.assertAlmostEqual(self.panel.y_scale, 0.5, places=2)
        self.assertEqual(self.outline.transform(), self.layer.transform)
        self.assert_panel_matches_state()

    def test_panel_size_keeps_flip(self) -> None:
        """Typing a width or height for a flipped layer resizes it and leaves it flipped."""
        for label, flip, field_name, size in (('horizontal', self.layer.flip_horizontal, WIDTH, LAYER_WIDTH * 1.5),
                                              ('vertical', self.layer.flip_vertical, HEIGHT, LAYER_HEIGHT * 1.5)):
            with self.subTest(label):
                self.layer.set_transform(QTransform.fromTranslate(LAYER_OFFSET.x(), LAYER_OFFSET.y()))
                flip()
                self.panel.geometry_block.field(field_name).set_value(size)
                transform = self.layer.transform
                self.assertLess(transform.determinant(), 0.0)
                self.assertAlmostEqual(abs(transform.determinant()), 1.5, places=4)
                self.assert_panel_matches_state()

    def test_panel_scale_keeps_center(self) -> None:
        """Setting a scale in the panel scales about the transformation origin, which starts at the layer center."""
        center = self._scene_point_of(QPointF(LAYER_WIDTH / 2, LAYER_HEIGHT / 2))
        self.panel.geometry_block.field(SCALE_X).set_value(2.0)
        self.assert_points_equal(self._scene_point_of(QPointF(LAYER_WIDTH / 2, LAYER_HEIGHT / 2)), center)

    def test_panel_rotation_keeps_center(self) -> None:
        """Setting a rotation in the panel rotates about the transformation origin, which starts at the layer
           center."""
        center = self._scene_point_of(QPointF(LAYER_WIDTH / 2, LAYER_HEIGHT / 2))
        self.panel.geometry_block.field(ANGLE).set_value(90.0)
        self.assertAlmostEqual(self.tool.state.rotation, 90.0, places=2)
        self.assert_points_equal(self._scene_point_of(QPointF(LAYER_WIDTH / 2, LAYER_HEIGHT / 2)), center)
        self.assert_panel_matches_state()

    def test_panel_x_under_rotation(self) -> None:
        """With the layer rotated, setting X moves the origin to X without changing the rotation."""
        self.layer.transform = QTransform.fromTranslate(LAYER_OFFSET.x(), LAYER_OFFSET.y()).rotate(30.0)
        self.panel.geometry_block.field(X).set_value(50.0)
        origin = self.outline.transformation_origin
        self.assertAlmostEqual(self._scene_point_of(origin).x(), 50.0, delta=POSITION_TOLERANCE)
        self.assertAlmostEqual(self.panel.x_position, 50.0, places=2)
        self.assertAlmostEqual(self.tool.state.rotation, 30.0, places=2)
        self.assert_panel_matches_state()

    def test_panel_edits_keep_skew(self) -> None:
        """Angle, width and X edits in the panel leave a skewed layer's skew unchanged."""
        self.layer.set_transform(QTransform(1.0, 0.3, 0.0, 1.0, 50.0, 50.0))
        origin = self.outline.transformation_origin
        skew = extract_transform_parameters(self.layer.transform, origin).skew
        self.assertNotAlmostEqual(skew, 0.0, places=2)
        for field_name, value in ((ANGLE, 45.0), (WIDTH, LAYER_WIDTH * 1.5), (X, 75.0)):
            with self.subTest(field_name):
                self.panel.geometry_block.field(field_name).set_value(value)
                self.assertEqual(self.outline.transform(), self.layer.transform)
                params = extract_transform_parameters(self.layer.transform, origin)
                self.assertAlmostEqual(params.skew, skew, places=4)
                self.assert_panel_matches_state()
        params = extract_transform_parameters(self.layer.transform, origin)
        self.assertAlmostEqual(params.rotation, 45.0, places=2)
        self.assertAlmostEqual(self.tool.state.width, LAYER_WIDTH * 1.5, places=2)
        self.assertAlmostEqual(self.panel.x_position, 75.0, places=2)

    def test_moving_origin_keeps_layer_fixed(self) -> None:
        """Dragging the transformation origin handle moves the origin, not the layer."""
        corners = self._scene_corners()
        start = self._handle_image_point(ORIGIN_HANDLE_ID)
        self.mouse_drag([start, start + QPoint(-40, -20), start + QPoint(-80, -40)])
        self.assertNotEqual(self.outline.transformation_origin,
                            QPointF(LAYER_WIDTH / 2, LAYER_HEIGHT / 2))
        for actual, expected in zip(self._scene_corners(), corners):
            self.assert_points_equal(actual, expected)
        self.assert_panel_matches_state()
        self.assert_points_equal(QPointF(self.panel.x_position, self.panel.y_position),
                                 self._scene_point_of(self.outline.transformation_origin))

    def test_origin_snaps_to_targets(self) -> None:
        """Dragging the origin handle near any of the nine snap targets lands exactly on it."""
        for x in (0, LAYER_WIDTH / 2, LAYER_WIDTH):
            for y in (0, LAYER_HEIGHT / 2, LAYER_HEIGHT):
                with self.subTest(target=(x, y)):
                    self.tool.set_transformation_origin(QPointF(LAYER_WIDTH / 2 + 7, LAYER_HEIGHT / 2 + 7))
                    target_scene = self._scene_point_of(QPointF(x, y))
                    self.outline.move_transformation_handle(ORIGIN_HANDLE_ID, target_scene + QPointF(3, -3))
                    self.assert_points_equal(self.outline.transformation_origin, QPointF(x, y))

    def test_origin_does_not_snap_between_targets(self) -> None:
        """Away from every snap target, the origin goes where it was dragged."""
        scene_pos = self._scene_point_of(QPointF(LAYER_WIDTH / 4, LAYER_HEIGHT / 4))
        self.outline.move_transformation_handle(ORIGIN_HANDLE_ID, scene_pos)
        self.assert_points_equal(self.outline.transformation_origin, QPointF(LAYER_WIDTH / 4, LAYER_HEIGHT / 4))

    def test_snapped_origin_follows_rotation(self) -> None:
        """Snap targets rotate with the layer, so a snapped corner can be placed by typing X and Y."""
        self.panel.geometry_block.field(ANGLE).set_value(30.0)
        corner = self._scene_point_of(QPointF(0, 0))
        self.outline.move_transformation_handle(ORIGIN_HANDLE_ID, corner + QPointF(2, 2))
        self.assert_points_equal(self.outline.transformation_origin, QPointF(0, 0))
        self.assert_points_equal(QPointF(self.panel.x_position, self.panel.y_position), corner)
        self.panel.geometry_block.field(X).set_value(20.0)
        self.panel.geometry_block.field(Y).set_value(30.0)
        self.assert_points_equal(self._scene_point_of(QPointF(0, 0)), QPointF(20.0, 30.0))

    def test_rotation_about_moved_origin(self) -> None:
        """After the origin handle moves, a panel rotation keeps the new origin's scene position fixed."""
        start = self._handle_image_point(ORIGIN_HANDLE_ID)
        self.mouse_drag([start, start + QPoint(-80, -40)])
        origin = QPointF(self.outline.transformation_origin)
        origin_in_scene = self._scene_point_of(origin)
        self.panel.geometry_block.field(ANGLE).set_value(45.0)
        self.assert_points_equal(self._scene_point_of(origin), origin_in_scene)

    def test_corner_drag_rotates_about_origin(self) -> None:
        """In rotate mode, dragging a corner rotates the layer about the transformation origin."""
        self.outline.mode = TRANSFORM_MODE_ROTATE
        center = self._scene_point_of(QPointF(LAYER_WIDTH / 2, LAYER_HEIGHT / 2))
        start = self._handle_image_point(BR_HANDLE_ID)
        self.mouse_drag([start, start + QPoint(-30, 30), start + QPoint(-60, 60)])
        self.assertNotAlmostEqual(self.tool.state.rotation, 0.0, places=2)
        self.assert_points_equal(self._scene_point_of(QPointF(LAYER_WIDTH / 2, LAYER_HEIGHT / 2)), center)

    def test_corner_drag_rotation_follows_cursor(self) -> None:
        """In rotate mode, the dragged corner ends up in the cursor's direction from the origin, including on
           unevenly scaled and flipped layers."""
        for label, transform in (('scaled', QTransform.fromTranslate(300, 300).scale(3.0, 0.5)),
                                 ('flipped', QTransform.fromTranslate(300, 300).scale(-1.0, 1.0))):
            with self.subTest(label):
                self.layer.set_transform(transform)
                self.outline.mode = TRANSFORM_MODE_ROTATE
                center = self._scene_point_of(QPointF(LAYER_WIDTH / 2, LAYER_HEIGHT / 2))
                start = self._handle_image_point(BR_HANDLE_ID)
                target = QPoint(round(center.x()), round(center.y()) + 150)
                self.mouse_drag([start, target])
                corner = self._scene_point_of(QPointF(LAYER_WIDTH, LAYER_HEIGHT))
                corner_angle = math.degrees(math.atan2(corner.y() - center.y(), corner.x() - center.x()))
                target_angle = math.degrees(math.atan2(target.y() - center.y(), target.x() - center.x()))
                self.assertAlmostEqual(corner_angle, target_angle, delta=0.5)

    def test_layer_size_change_keeps_origin(self) -> None:
        """When the active layer changes size, the transformation origin keeps its position relative to the layer
           bounds, and its handle stays on it."""
        start = self._handle_image_point(ORIGIN_HANDLE_ID)
        self.mouse_drag([start, start + QPoint(-50, -25)])
        origin = self.outline.transformation_origin
        relative_origin = QPointF(origin.x() / LAYER_WIDTH, origin.y() / LAYER_HEIGHT)
        self.assertNotEqual(relative_origin, QPointF(0.5, 0.5))
        bigger_image = QImage(LAYER_WIDTH * 2, LAYER_HEIGHT * 2, QImage.Format.Format_ARGB32_Premultiplied)
        bigger_image.fill(Qt.GlobalColor.red)
        self.layer.image = bigger_image
        self.assert_points_equal(self.outline.transformation_origin,
                                 QPointF(relative_origin.x() * LAYER_WIDTH * 2,
                                         relative_origin.y() * LAYER_HEIGHT * 2))
        handle = self.outline._handles[ORIGIN_HANDLE_ID]
        self.assert_points_equal(handle.rect().center(), self.outline.transformation_origin)

    def test_external_transform_change(self) -> None:
        """A transform change made outside the tool, such as an undo or a menu action, updates the outline and
           panel."""
        new_transform = QTransform.fromTranslate(10.0, 20.0).scale(2.0, 0.5)
        self.layer.set_transform(new_transform)
        self.assertEqual(self.outline.transform(), new_transform)
        self.assert_panel_matches_state()
        self.assertAlmostEqual(self.panel.x_position, 10.0 + LAYER_WIDTH, places=2)
        self.assertAlmostEqual(self.panel.layer_width, LAYER_WIDTH * 2.0, places=2)

    def test_undo_and_menu_rotate_readopt(self) -> None:
        """Undo and the menu's rotate change the layer from outside the tool, and the state follows each, keeping a
        moved origin."""
        self.tool.set_transformation_origin(QPointF(0.0, 0.0))
        self.panel.geometry_block.field(ANGLE).set_value(30.0)
        UndoStack().undo()
        self.assertEqual(self.outline.transform(), self.layer.transform)
        self.assertAlmostEqual(self.tool.state.rotation, 0.0, places=4)
        self.assertEqual(self.tool.state.relative_origin, QPointF(0.0, 0.0))
        self.layer.rotate(90)
        self.assertEqual(self.outline.transform(), self.layer.transform)
        self.assertAlmostEqual(self.tool.state.rotation, 90.0, places=4)
        self.assert_points_equal(self.tool.state.origin_pos, self._scene_point_of(QPointF(0.0, 0.0)))
        self.assert_panel_matches_state()

    def test_perspective_layer(self) -> None:
        """A layer with a perspective transform is shown as it is, with the fields and canvas handles disabled, and
        Clear transform removes the perspective and enables them again."""
        perspective = QTransform(1.0, 0.0, 0.001, 0.0, 1.0, 0.0, 100.0, 150.0, 1.0)
        self.layer.set_transform(perspective)
        self.assertIsNone(self.tool.state)
        self.assertEqual(self.outline.transform(), perspective)
        self.assertFalse(self.panel.geometry_block.isEnabled())
        self.assertFalse(self.panel.banner.isHidden())
        self.assertFalse(self.outline.isEnabled())
        self.assertTrue(self.panel.clear_button.isEnabled())
        self.assertTrue(self.panel.revert_button.isEnabled())
        self.tool.set_x(5.0)
        self.assertEqual(self.layer.transform, perspective)
        self.panel.clear_button.click()
        self.assertEqual(self.layer.transform, QTransform())
        self.assertIsNotNone(self.tool.state)
        self.assertTrue(self.panel.geometry_block.isEnabled())
        self.assertTrue(self.panel.banner.isHidden())
        self.assertTrue(self.outline.isEnabled())
        self.assert_panel_matches_state()

    def test_select_perspective_layer(self) -> None:
        """Selecting a layer that already has a perspective transform raises no error, and Revert restores it after
        Clear transform."""
        image = QImage(LAYER_WIDTH, LAYER_HEIGHT, QImage.Format.Format_ARGB32_Premultiplied)
        perspective = QTransform(1.0, 0.0, 0.0, 0.2, 1.0, 0.001, 0.0, 0.0, 1.0)
        other = self.image_stack.create_layer(image_data=image, transform=perspective)
        self.image_stack.active_layer = other
        self.assertIsNone(self.tool.state)
        self.assertFalse(self.panel.geometry_block.isEnabled())
        self.panel.clear_button.click()
        self.assertEqual(other.transform, QTransform())
        self.panel.revert_button.click()
        self.assertEqual(other.transform, perspective)
        self.assertIsNone(self.tool.state)

    def test_reset_transformation(self) -> None:
        """reset_transformation restores the transform the layer had when the tool loaded it, as one undo entry."""
        original = self.layer.transform
        self.panel.geometry_block.field(X).set_value(40.0)
        UndoStack().clear()
        self.tool.reset_transformation()
        self.assertEqual(self.layer.transform, original)
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assert_points_equal(self._scene_point_of(QPointF()), QPointF(40.0 - LAYER_WIDTH / 2, LAYER_OFFSET.y()))

    def test_group_revert_after_move(self) -> None:
        """Revert restores a layer group's transform from when it was selected, after the group was moved."""
        group = self.image_stack.create_layer_group('group')
        self.image_stack.move_layer(self.layer, group, 0)
        self.image_stack.active_layer = group
        original = self.layer.transform
        self.panel.geometry_block.field(X).set_value(40.3)
        self.assertNotEqual(self.layer.transform, original)
        self.panel.revert_button.click()
        self.assertEqual(self.layer.transform, original)
        self.assert_panel_matches_state()

    def test_revert_after_layer_size_change(self) -> None:
        """Revert restores the transform from when the layer was selected, after the layer changed size."""
        original = self.layer.transform
        self.panel.geometry_block.field(X).set_value(40.0)
        bigger_image = QImage(LAYER_WIDTH * 2, LAYER_HEIGHT * 2, QImage.Format.Format_ARGB32_Premultiplied)
        bigger_image.fill(Qt.GlobalColor.red)
        self.layer.image = bigger_image
        self.panel.revert_button.click()
        self.assertEqual(self.layer.transform, original)

    def test_group_transform_ends_with_selection(self) -> None:
        """Transforming a layer group moves its layers, and once another layer is active, a layer added to the group
        keeps its own transform."""
        group = self.image_stack.create_layer_group('group')
        self.image_stack.move_layer(self.layer, group, 0)
        self.image_stack.active_layer = group
        UndoStack().clear()
        self.panel.geometry_block.field(X).set_value(40.0)
        self.assert_points_equal(self._scene_point_of(QPointF()), QPointF(40.0 - LAYER_WIDTH / 2, LAYER_OFFSET.y()))
        self.image_stack.active_layer = self.layer
        added = self.image_stack.create_layer('added', layer_parent=group, layer_index=0)
        self.assertEqual(added.transform, QTransform())
        UndoStack().undo()  # The layer creation
        UndoStack().undo()  # The active layer change
        UndoStack().undo()  # The group transform
        self.assert_points_equal(self._scene_point_of(QPointF()), QPointF(LAYER_OFFSET))

    def test_layer_click_activates_layer(self) -> None:
        """Clicking another layer on the canvas, outside the active layer's outline, makes it active."""
        other_image = QImage(50, 50, QImage.Format.Format_ARGB32_Premultiplied)
        other_image.fill(Qt.GlobalColor.blue)
        other = self.image_stack.create_layer(image_data=other_image, transform=QTransform.fromTranslate(400, 400))
        self.image_stack.active_layer = self.layer
        self.mouse_drag([QPoint(420, 420)])
        self.assertEqual(self.image_stack.active_layer, other)
        self.assertEqual(self.outline.rect(), QRectF(0, 0, 50, 50))
        self.assertEqual(self.outline.transformation_origin, QPointF(25, 25))

    def _create_blue_layer_over_active(self):
        blue_image = QImage(50, 50, QImage.Format.Format_ARGB32_Premultiplied)
        blue_image.fill(Qt.GlobalColor.blue)
        return self.image_stack.create_layer(image_data=blue_image, transform=QTransform.fromTranslate(400, 400))

    def test_layer_click_picks_topmost_overlapping_layer(self) -> None:
        """Clicking where two layers overlap outside the active layer activates the upper one."""
        lower = self._create_blue_layer_over_active()
        self.image_stack.active_layer = lower  # New layers are inserted just above the active layer.
        upper = self._create_blue_layer_over_active()
        self.image_stack.active_layer = self.layer
        self.mouse_drag([QPoint(420, 420)])
        self.assertEqual(self.image_stack.active_layer, upper)
        self.assertNotEqual(self.image_stack.active_layer, lower)

    def test_layer_click_skips_hidden_layer(self) -> None:
        """A hidden layer is never activated by a canvas click, so the click picks the visible layer beneath it."""
        lower = self._create_blue_layer_over_active()
        self.image_stack.active_layer = lower  # New layers are inserted just above the active layer.
        upper = self._create_blue_layer_over_active()
        upper.visible = False
        self.image_stack.active_layer = self.layer
        self.mouse_drag([QPoint(420, 420)])
        self.assertEqual(self.image_stack.active_layer, lower)

    def test_temporary_ratio_lock_reaches_outline(self) -> None:
        """Holding the fixed-aspect modifier keeps canvas edits at the layer's ratio without changing the stored
        "Keep aspect ratio" setting."""
        block = self.panel.geometry_block
        block.set_temporary_lock(True)
        self.assertTrue(self.tool._ratio_locked)
        self.assertFalse(self.panel.preserve_aspect_ratio)
        self.tool.set_width(LAYER_WIDTH * 2.0)
        self.assertAlmostEqual(self.tool.state.height, LAYER_HEIGHT * 2.0, places=2)
        block.set_temporary_lock(False)
        self.assertFalse(self.tool._ratio_locked)

    def test_ratio_lock_survives_layer_change(self) -> None:
        """With "Keep aspect ratio" on, canvas edits to the next selected layer keep its ratio."""
        image = QImage(LAYER_WIDTH, LAYER_HEIGHT, QImage.Format.Format_ARGB32_Premultiplied)
        other_layer = self.image_stack.create_layer(image_data=image)
        self.panel.geometry_block.set_ratio_locked(True)
        self.image_stack.active_layer = other_layer
        self.assertTrue(self.tool._ratio_locked)
        self.tool.set_width(LAYER_WIDTH * 2.0)
        self.assertAlmostEqual(self.tool.state.height, LAYER_HEIGHT * 2.0, places=2)


    def test_right_click_lists_layers_under_cursor(self) -> None:
        """Right-click lists the layers under the cursor, topmost first, and choosing one makes it active."""
        image = QImage(LAYER_WIDTH, LAYER_HEIGHT, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.blue)
        upper = self.image_stack.create_layer('upper', image, transform=QTransform.fromTranslate(
            LAYER_OFFSET.x(), LAYER_OFFSET.y()))
        self.image_stack.active_layer = upper
        point = LAYER_OFFSET + QPoint(20, 20)
        self.mouse_drag([point], Qt.MouseButton.RightButton)
        menu = self.tool._layer_menu
        self.assertIsInstance(menu, QMenu)
        actions = menu.actions()
        self.assertEqual([action.text() for action in actions], [upper.name, self.layer.name])
        actions[1].trigger()
        self.assertIs(self.image_stack.active_layer, self.layer)


if __name__ == '__main__':
    unittest.main()