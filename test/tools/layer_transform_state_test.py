"""Tests TransformState's edits, projection and decomposition."""
import unittest

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QTransform

from src.tools.layer_transform_state import MAX_SKEW, TransformState
from src.util.visual.geometry_utils import combine_transform_parameters
from test.base_test_case import IntraPaintTestCase

RECT = QRectF(10.0, 20.0, 200.0, 100.0)
TOLERANCE = 1e-6


def _skewed_state() -> TransformState:
    """Returns a state that is scaled unevenly, skewed, rotated and moved, about the rectangle's center."""
    matrix = combine_transform_parameters(30.0, -15.0, 1.5, 0.75, 20.0, 35.0, RECT.center())
    state = TransformState.from_matrix(matrix, RECT)
    assert state is not None
    return state


def _perpendicular(state: TransformState, point: QPointF, along: QPointF, distance: float) -> QPointF:
    """Returns a scene offset of distance, perpendicular to the scene direction that along takes at point."""
    direction = state.matrix().map(point + along) - state.matrix().map(point)
    length = (direction.x() ** 2 + direction.y() ** 2) ** 0.5
    return QPointF(-direction.y(), direction.x()) * (distance / length)


class TransformStateTest(IntraPaintTestCase):
    """Tests TransformState."""

    def assert_points_equal(self, actual: QPointF, expected: QPointF) -> None:
        """Asserts that two points are within TOLERANCE on both axes."""
        self.assertAlmostEqual(actual.x(), expected.x(), delta=TOLERANCE, msg=f'{actual} {expected}')
        self.assertAlmostEqual(actual.y(), expected.y(), delta=TOLERANCE, msg=f'{actual} {expected}')

    def assert_matrices_equal(self, actual: QTransform, expected: QTransform) -> None:
        """Asserts that every entry of two matrices is within TOLERANCE."""
        for name in ('m11', 'm12', 'm13', 'm21', 'm22', 'm23', 'm31', 'm32', 'm33'):
            self.assertAlmostEqual(getattr(actual, name)(), getattr(expected, name)(), delta=TOLERANCE, msg=name)

    def test_from_matrix_reads_fields(self) -> None:
        """from_matrix reads the fields combine_transform_parameters was given, and the origin's scene position."""
        state = _skewed_state()
        self.assertAlmostEqual(state.x_scale, 1.5)
        self.assertAlmostEqual(state.y_scale, 0.75)
        self.assertAlmostEqual(state.skew, 20.0)
        self.assertAlmostEqual(state.rotation, 35.0)
        self.assert_points_equal(state.origin_pos, RECT.center() + QPointF(30.0, -15.0))
        self.assertEqual(state.rect, RECT)

    def test_from_matrix_keeps_matrix(self) -> None:
        """Reading a matrix and projecting it back returns the same matrix."""
        matrix = QTransform(1.0, 0.3, 0.0, 1.0, 50.0, 50.0)
        state = TransformState.from_matrix(matrix, RECT)
        assert state is not None
        self.assertEqual(state.matrix(), matrix)

    def test_edited_matrix_matches_fields(self) -> None:
        """After an edit, the matrix is projected from the fields."""
        state = _skewed_state().with_rotation(10.0)
        origin = state.origin_local
        expected = combine_transform_parameters(state.origin_pos.x() - origin.x(), state.origin_pos.y() - origin.y(),
                                                state.x_scale, state.y_scale, state.skew, 10.0, origin)
        self.assertEqual(state.matrix(), expected)

    def test_from_matrix_rejects_perspective(self) -> None:
        """from_matrix returns None for a perspective or non-invertible matrix."""
        for label, matrix in (('perspective', QTransform(1.0, 0.0, 0.001, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)),
                              ('non-invertible', QTransform(1.0, 0.0, 1.0, 0.0, 0.0, 0.0))):
            with self.subTest(label):
                self.assertIsNone(TransformState.from_matrix(matrix, RECT))

    def test_edits_keep_origin(self) -> None:
        """Rotation, skew, scale and size edits keep the origin's scene position and the other fields."""
        state = _skewed_state()
        for label, edited in (('rotation', state.with_rotation(80.0)), ('skew', state.with_skew(-10.0)),
                              ('scale', state.with_scale(2.0, 3.0)), ('size', state.with_size(50.0, 400.0))):
            with self.subTest(label):
                self.assert_points_equal(edited.origin_pos, state.origin_pos)
                self.assert_points_equal(edited.matrix().map(edited.origin_local), state.origin_pos)
        sized = state.with_size(50.0, 400.0)
        self.assertAlmostEqual(sized.width, 50.0)
        self.assertAlmostEqual(sized.height, 400.0)
        self.assertEqual((sized.skew, sized.rotation), (state.skew, state.rotation))

    def test_with_size_keeps_flip(self) -> None:
        """with_size keeps each scale's sign."""
        state = TransformState.from_matrix(QTransform.fromScale(-1.0, 1.0), RECT)
        assert state is not None
        sized = state.with_size(400.0, 100.0)
        self.assertLess(sized.matrix().determinant(), 0.0)
        self.assertAlmostEqual(sized.width, 400.0)

    def test_with_scale_avoids_zero(self) -> None:
        """A scale of zero becomes the smallest nonzero scale, so the matrix stays invertible."""
        state = _skewed_state().with_scale(0.0, -0.0)
        self.assertTrue(state.matrix().isInvertible())

    def test_moves(self) -> None:
        """moved_by and with_origin_pos translate the matrix and change nothing else."""
        state = _skewed_state()
        moved = state.moved_by(7.0, -3.0)
        self.assert_matrices_equal(moved.matrix(), state.matrix() * QTransform.fromTranslate(7.0, -3.0))
        placed = state.with_origin_pos(QPointF(1.0, 2.0))
        self.assert_points_equal(placed.origin_pos, QPointF(1.0, 2.0))
        self.assertEqual((placed.x_scale, placed.y_scale, placed.skew, placed.rotation),
                         (state.x_scale, state.y_scale, state.skew, state.rotation))

    def test_with_relative_origin_keeps_matrix(self) -> None:
        """Moving the origin leaves the matrix unchanged and moves origin_pos to the new origin's scene position."""
        for label, state in (('read', _skewed_state()), ('edited', _skewed_state().with_rotation(12.0))):
            with self.subTest(label):
                moved = state.with_relative_origin(QPointF(0.0, 1.0))
                self.assert_matrices_equal(moved.matrix(), state.matrix())
                self.assert_points_equal(moved.origin_pos, state.matrix().map(RECT.bottomLeft()))
                rotated = moved.with_rotation(moved.rotation + 30.0)
                self.assert_points_equal(rotated.matrix().map(RECT.bottomLeft()), moved.origin_pos)

    def test_with_relative_origin_clamps(self) -> None:
        """The relative origin is clamped to the rectangle."""
        state = _skewed_state().with_relative_origin(QPointF(-1.0, 2.0))
        self.assertEqual(state.relative_origin, QPointF(0.0, 1.0))

    def test_anchored(self) -> None:
        """anchored moves the state so the local point lands on the scene point."""
        state = _skewed_state().anchored(RECT.topRight(), QPointF(5.0, 6.0))
        self.assert_points_equal(state.matrix().map(RECT.topRight()), QPointF(5.0, 6.0))

    def test_corner_scale_keeps_skew_and_rotation(self) -> None:
        """Moving a corner scales the state holding the opposite corner, and keeps skew and rotation."""
        state = _skewed_state()
        fixed_scene = state.matrix().map(RECT.topLeft())
        target = RECT.bottomRight() + QPointF(50.0, 20.0)
        scaled = state.with_corner_moved(RECT.bottomRight(), target)
        self.assert_points_equal(scaled.matrix().map(RECT.topLeft()), fixed_scene)
        self.assert_points_equal(scaled.matrix().map(RECT.bottomRight()), state.matrix().map(target))
        self.assertAlmostEqual(scaled.skew, state.skew, delta=TOLERANCE)
        self.assertAlmostEqual(scaled.rotation, state.rotation, delta=TOLERANCE)
        self.assertAlmostEqual(scaled.x_scale, state.x_scale * 250.0 / 200.0, delta=TOLERANCE)
        self.assertAlmostEqual(scaled.y_scale, state.y_scale * 120.0 / 100.0, delta=TOLERANCE)
        self.assertEqual(scaled.relative_origin, state.relative_origin)

    def test_corner_scale_keeps_ratio(self) -> None:
        """With a fixed ratio, a corner move keeps abs(x_scale / y_scale) at it."""
        state = _skewed_state()
        scaled = state.with_corner_moved(RECT.bottomRight(), RECT.bottomRight() + QPointF(50.0, 0.0), 2.0)
        self.assertAlmostEqual(abs(scaled.x_scale / scaled.y_scale), 2.0, delta=TOLERANCE)

    def test_corner_turn(self) -> None:
        """Turning a corner toward a scene point rotates about the origin until the corner points there."""
        state = _skewed_state()
        target = state.origin_pos + QPointF(0.0, 100.0)
        turned = state.with_corner_turned(RECT.bottomRight(), target)
        corner = turned.matrix().map(RECT.bottomRight()) - turned.origin_pos
        self.assertAlmostEqual(corner.x(), 0.0, delta=TOLERANCE)
        self.assertGreater(corner.y(), 0.0)
        self.assert_points_equal(turned.origin_pos, state.origin_pos)

    def test_edge_scale_changes_one_axis(self) -> None:
        """Moving an edge midpoint scales only its axis, holding the opposite edge, and keeps skew and rotation."""
        state = _skewed_state()
        for edge, target, axis in ((QPointF(RECT.center().x(), RECT.top()), QPointF(0.0, RECT.top() - 50.0), 'y'),
                                   (QPointF(RECT.right(), RECT.center().y()), QPointF(RECT.right() + 100.0, 0.0),
                                    'x')):
            with self.subTest(axis):
                opposite = QPointF(RECT.left() + RECT.right() - edge.x(), RECT.top() + RECT.bottom() - edge.y())
                scaled = state.with_edge_moved(edge, target)
                for x in (RECT.left(), RECT.right()) if axis == 'y' else (opposite.x(),):
                    for y in (opposite.y(),) if axis == 'y' else (RECT.top(), RECT.bottom()):
                        self.assert_points_equal(scaled.matrix().map(QPointF(x, y)), state.matrix().map(QPointF(x, y)))
                self.assertAlmostEqual(scaled.skew, state.skew, delta=TOLERANCE)
                self.assertAlmostEqual(scaled.rotation, state.rotation, delta=TOLERANCE)
                if axis == 'y':
                    self.assertAlmostEqual(scaled.x_scale, state.x_scale, delta=TOLERANCE)
                    self.assertAlmostEqual(scaled.y_scale, state.y_scale * 1.5, delta=TOLERANCE)
                else:
                    self.assertAlmostEqual(scaled.x_scale, state.x_scale * 1.5, delta=TOLERANCE)
                    self.assertAlmostEqual(scaled.y_scale, state.y_scale, delta=TOLERANCE)

    def test_edge_scale_keeps_ratio(self) -> None:
        """With a fixed ratio, an edge move scales both axes about the opposite edge's midpoint."""
        state = _skewed_state()
        edge = QPointF(RECT.center().x(), RECT.bottom())
        opposite = QPointF(RECT.center().x(), RECT.top())
        ratio = abs(state.x_scale / state.y_scale)
        scaled = state.with_edge_moved(edge, edge + QPointF(0.0, 50.0), ratio)
        self.assertAlmostEqual(scaled.y_scale, state.y_scale * 1.5, delta=TOLERANCE)
        self.assertAlmostEqual(abs(scaled.x_scale / scaled.y_scale), ratio, delta=TOLERANCE)
        self.assert_points_equal(scaled.matrix().map(opposite), state.matrix().map(opposite))

    def test_top_edge_shear_changes_only_skew(self) -> None:
        """Sliding the top edge changes skew and position only, holds the bottom edge, and lands the dragged midpoint
           on the target."""
        state = _skewed_state()
        top = QPointF(RECT.center().x(), RECT.top())
        on_edge = state.matrix().map(top + QPointF(30.0, 0.0))
        sheared = state.with_edge_sheared(top, on_edge + _perpendicular(state, top, QPointF(1.0, 0.0), 12.0))
        for x in (RECT.left(), RECT.right()):
            point = QPointF(x, RECT.bottom())
            self.assert_points_equal(sheared.matrix().map(point), state.matrix().map(point))
        self.assert_points_equal(sheared.matrix().map(top), on_edge)
        self.assertNotAlmostEqual(sheared.skew, state.skew, places=2)
        self.assertAlmostEqual(sheared.rotation, state.rotation, delta=TOLERANCE)
        self.assertAlmostEqual(sheared.x_scale, state.x_scale, delta=TOLERANCE)
        self.assertAlmostEqual(sheared.y_scale, state.y_scale, delta=TOLERANCE)

    def test_side_edge_shear_holds_opposite_edge(self) -> None:
        """Sliding the right edge holds the left edge and lands the dragged midpoint on the target."""
        state = _skewed_state()
        right = QPointF(RECT.right(), RECT.center().y())
        on_edge = state.matrix().map(right + QPointF(0.0, 25.0))
        sheared = state.with_edge_sheared(right, on_edge + _perpendicular(state, right, QPointF(0.0, 1.0), -7.0))
        for y in (RECT.top(), RECT.bottom()):
            point = QPointF(RECT.left(), y)
            self.assert_points_equal(sheared.matrix().map(point), state.matrix().map(point))
        self.assert_points_equal(sheared.matrix().map(right), on_edge)

    def test_edge_shear_stops_at_max_skew(self) -> None:
        """A top-edge shear far to the left stops at -MAX_SKEW, still holding the opposite edge."""
        state = TransformState.from_matrix(QTransform(), RECT)
        assert state is not None
        top = QPointF(RECT.center().x(), RECT.top())
        sheared = state.with_edge_sheared(top, QPointF(-100000.0, top.y()))
        self.assertAlmostEqual(sheared.skew, -MAX_SKEW, delta=0.01)
        point = QPointF(RECT.left(), RECT.bottom())
        self.assert_points_equal(sheared.matrix().map(point), point)

    def test_positive_skew_moves_top_edge_right(self) -> None:
        """Positive skew about the center moves the top edge right and the bottom edge left."""
        state = TransformState.from_matrix(QTransform(), RECT)
        assert state is not None
        skewed = state.with_skew(20.0)
        self.assertGreater(skewed.matrix().map(RECT.topLeft()).x(), RECT.left())
        self.assertLess(skewed.matrix().map(RECT.bottomLeft()).x(), RECT.left())

    def test_state_is_immutable(self) -> None:
        """Changing a Qt value read from a state leaves the state unchanged."""
        state = _skewed_state()
        rect = state.rect
        rect.setWidth(1.0)
        origin = state.origin_pos
        origin.setX(-500.0)
        self.assertEqual(state.rect, RECT)
        self.assertNotEqual(state.origin_pos, origin)


if __name__ == '__main__':
    unittest.main()
