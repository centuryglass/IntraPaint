"""Tests the layer transform tool through mouse input on the canvas and edits in its control panel."""
import math
import unittest

from PySide6.QtCore import QPoint, QPointF, QRectF
from PySide6.QtGui import QImage, QTransform, Qt

from src.tools.layer_transform_tool import LayerTransformTool
from src.ui.graphics_items.transform_outline import (TransformOutline, ORIGIN_HANDLE_ID, BR_HANDLE_ID,
                                                     TRANSFORM_MODE_ROTATE)
from src.ui.panel.tool_control_panels.layer_transform_tool_panel import LayerTransformToolPanel
from src.undo_stack import UndoStack
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

    def assert_panel_matches_outline(self) -> None:
        """Asserts that every panel field shows the outline's current value."""
        self.assertAlmostEqual(self.panel.x_position, self.outline.x_pos, places=2)
        self.assertAlmostEqual(self.panel.y_position, self.outline.y_pos, places=2)
        self.assertAlmostEqual(self.panel.layer_width, self.outline.width, places=2)
        self.assertAlmostEqual(self.panel.layer_height, self.outline.height, places=2)
        x_scale, y_scale = self.outline.transform_scale
        self.assertAlmostEqual(self.panel.x_scale, x_scale, places=2)
        self.assertAlmostEqual(self.panel.y_scale, y_scale, places=2)
        self.assertAlmostEqual(self.panel.rotation, self.outline.rotation_angle, places=2)

    def _handle_image_point(self, handle_id: str) -> QPoint:
        handle = self.outline._handles[handle_id]
        scene_point = handle.mapToScene(handle.rect().center())
        return QPoint(int(scene_point.x()), int(scene_point.y()))

    def test_activate_loads_layer(self) -> None:
        """Activating the tool loads the active layer's transform into the outline and the panel."""
        self.assertEqual(self.outline.transform(), self.layer.transform)
        self.assertEqual(self.outline.rect(), QRectF(0, 0, LAYER_WIDTH, LAYER_HEIGHT))
        self.assertEqual(self.panel.x_position, LAYER_OFFSET.x())
        self.assertEqual(self.panel.y_position, LAYER_OFFSET.y())
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
        self.assert_panel_matches_outline()

    def test_drag_undo(self) -> None:
        """Undoing a drag merged into one undo entry restores the layer's original position."""
        original = self.layer.transform
        start = QPoint(LAYER_OFFSET.x() + 20, LAYER_OFFSET.y() + 20)
        self.mouse_drag([start, start + QPoint(10, 5), start + QPoint(30, 40)])
        self.assertNotEqual(self.layer.transform, original)
        UndoStack().undo()
        self.assertEqual(self.layer.transform, original)
        self.assertEqual(self.outline.transform(), original)
        self.assert_panel_matches_outline()

    def test_drag_is_one_undo_step(self) -> None:
        """One drag adds one undo entry."""
        start = QPoint(LAYER_OFFSET.x() + 20, LAYER_OFFSET.y() + 20)
        self.mouse_drag([start, start + QPoint(10, 5), start + QPoint(30, 40)])
        self.assertEqual(UndoStack().undo_count(), 1)

    def test_corner_drag_scales(self) -> None:
        """Dragging the bottom-right handle scales the layer and leaves the top-left corner fixed."""
        start = self._handle_image_point(BR_HANDLE_ID)
        self.mouse_drag([start, start + QPoint(50, 25), start + QPoint(100, 50)])
        self.assert_points_equal(self._scene_point_of(QPointF()), QPointF(LAYER_OFFSET))
        self.assertAlmostEqual(self.outline.width, LAYER_WIDTH * 1.5, delta=1.0)
        self.assertAlmostEqual(self.outline.height, LAYER_HEIGHT * 1.5, delta=1.0)
        self.assertEqual(self.outline.transform(), self.layer.transform)
        self.assert_panel_matches_outline()

    def test_panel_position(self) -> None:
        """Setting X and Y in the panel moves the layer there, and the fields read back what was set."""
        self.panel._x_pos_box.setValue(40.0)
        self.panel._y_pos_box.setValue(60.0)
        self.assert_points_equal(self._scene_point_of(QPointF()), QPointF(40.0, 60.0))
        self.assertEqual(self.panel.x_position, 40.0)
        self.assertEqual(self.panel.y_position, 60.0)
        self.assert_panel_matches_outline()

    def test_panel_size(self) -> None:
        """Setting width and height in the panel scales the layer to that size and updates the scale fields."""
        self.panel._width_box.setValue(LAYER_WIDTH * 2.0)
        self.panel._height_box.setValue(LAYER_HEIGHT * 0.5)
        self.assertAlmostEqual(self.outline.width, LAYER_WIDTH * 2.0, places=2)
        self.assertAlmostEqual(self.outline.height, LAYER_HEIGHT * 0.5, places=2)
        self.assertAlmostEqual(self.panel.x_scale, 2.0, places=2)
        self.assertAlmostEqual(self.panel.y_scale, 0.5, places=2)
        self.assertEqual(self.outline.transform(), self.layer.transform)
        self.assert_panel_matches_outline()

    def test_panel_scale_keeps_center(self) -> None:
        """Setting a scale in the panel scales about the transformation origin, which starts at the layer center."""
        center = self._scene_point_of(QPointF(LAYER_WIDTH / 2, LAYER_HEIGHT / 2))
        self.panel._x_scale_box.setValue(2.0)
        self.assert_points_equal(self._scene_point_of(QPointF(LAYER_WIDTH / 2, LAYER_HEIGHT / 2)), center)

    def test_panel_rotation_keeps_center(self) -> None:
        """Setting a rotation in the panel rotates about the transformation origin, which starts at the layer
           center."""
        center = self._scene_point_of(QPointF(LAYER_WIDTH / 2, LAYER_HEIGHT / 2))
        self.panel._rotate_box.setValue(90.0)
        self.assertAlmostEqual(self.outline.rotation_angle, 90.0, places=2)
        self.assert_points_equal(self._scene_point_of(QPointF(LAYER_WIDTH / 2, LAYER_HEIGHT / 2)), center)
        self.assert_panel_matches_outline()

    def test_panel_x_under_rotation(self) -> None:
        """With the layer rotated, setting X moves the layer's leftmost point to X without changing the rotation."""
        self.layer.transform = QTransform.fromTranslate(LAYER_OFFSET.x(), LAYER_OFFSET.y()).rotate(30.0)
        self.panel._x_pos_box.setValue(50.0)
        self.assertAlmostEqual(min(pt.x() for pt in self._scene_corners()), 50.0, delta=POSITION_TOLERANCE)
        self.assertAlmostEqual(self.panel.x_position, 50.0, places=2)
        self.assertAlmostEqual(self.outline.rotation_angle, 30.0, places=2)
        self.assert_panel_matches_outline()

    def test_moving_origin_keeps_layer_fixed(self) -> None:
        """Dragging the transformation origin handle moves the origin, not the layer."""
        corners = self._scene_corners()
        start = self._handle_image_point(ORIGIN_HANDLE_ID)
        self.mouse_drag([start, start + QPoint(-40, -20), start + QPoint(-80, -40)])
        self.assertNotEqual(self.outline.transformation_origin,
                            QPointF(LAYER_WIDTH / 2, LAYER_HEIGHT / 2))
        for actual, expected in zip(self._scene_corners(), corners):
            self.assert_points_equal(actual, expected)

    def test_rotation_about_moved_origin(self) -> None:
        """After the origin handle moves, a panel rotation keeps the new origin's scene position fixed."""
        start = self._handle_image_point(ORIGIN_HANDLE_ID)
        self.mouse_drag([start, start + QPoint(-80, -40)])
        origin = QPointF(self.outline.transformation_origin)
        origin_in_scene = self._scene_point_of(origin)
        self.panel._rotate_box.setValue(45.0)
        self.assert_points_equal(self._scene_point_of(origin), origin_in_scene)

    def test_corner_drag_rotates_about_origin(self) -> None:
        """In rotate mode, dragging a corner rotates the layer about the transformation origin."""
        self.outline._mode = TRANSFORM_MODE_ROTATE
        center = self._scene_point_of(QPointF(LAYER_WIDTH / 2, LAYER_HEIGHT / 2))
        start = self._handle_image_point(BR_HANDLE_ID)
        self.mouse_drag([start, start + QPoint(-30, 30), start + QPoint(-60, 60)])
        self.assertNotAlmostEqual(self.outline.rotation_angle, 0.0, places=2)
        self.assert_points_equal(self._scene_point_of(QPointF(LAYER_WIDTH / 2, LAYER_HEIGHT / 2)), center)

    def test_corner_drag_rotation_follows_cursor(self) -> None:
        """In rotate mode, the dragged corner ends up in the cursor's direction from the origin, including on
           unevenly scaled and flipped layers."""
        for label, transform in (('scaled', QTransform.fromTranslate(300, 300).scale(3.0, 0.5)),
                                 ('flipped', QTransform.fromTranslate(300, 300).scale(-1.0, 1.0))):
            with self.subTest(label):
                self.layer.set_transform(transform)
                self.outline._mode = TRANSFORM_MODE_ROTATE
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
        self.assert_panel_matches_outline()
        self.assertAlmostEqual(self.panel.x_position, 10.0, places=2)
        self.assertAlmostEqual(self.panel.layer_width, LAYER_WIDTH * 2.0, places=2)

    def test_reset_transformation(self) -> None:
        """reset_transformation restores the transform the layer had when the tool loaded it, as one undo entry."""
        original = self.layer.transform
        self.panel._x_pos_box.setValue(40.0)
        UndoStack().clear()
        self.tool.reset_transformation()
        self.assertEqual(self.layer.transform, original)
        self.assertEqual(UndoStack().undo_count(), 1)
        UndoStack().undo()
        self.assert_points_equal(self._scene_point_of(QPointF()), QPointF(40.0, LAYER_OFFSET.y()))

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


if __name__ == '__main__':
    unittest.main()
