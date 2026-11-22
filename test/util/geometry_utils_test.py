"""Test various geometry utility functions"""
import math
import random
import sys
import unittest

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QTransform
from PySide6.QtWidgets import QApplication

from src.util.visual.geometry_utils import extract_transform_parameters, combine_transform_parameters, transform_str, \
    transforms_approx_equal, panel_position, transform_at_panel_position
from src.util.math_utils import convert_degrees

app = QApplication.instance() or QApplication(sys.argv)

class TestGeometryUtils(unittest.TestCase):
    """Test various geometry utility functions"""

    def test_transform_parameters(self):
        """Transforms split into translation, scale, skew and rotation in a standard form, and recombine unchanged.

        Mirroring both axes is a 180 degree rotation, and mirroring one axis is mirroring the other plus 180 degrees.
        The standard form never has two negative scales, and picks the option with a rotation under 180 degrees.
        Switching between those readings leaves skew unchanged.
        """
        # (x_scale, y_scale, degrees) in, standard (x_scale, y_scale, degrees) out:
        cases = [
            ((1.0, 1.0, 0.0), (1.0, 1.0, 0.0)),
            ((1.0, 1.0, 90.0), (1.0, 1.0, 90.0)),
            ((1.0, 1.0, 180.0), (1.0, 1.0, 180.0)),
            ((1.0, 1.0, 270.0), (1.0, 1.0, 270.0)),
            ((1.0, 1.0, 359.5), (1.0, 1.0, 359.5)),
            ((2.0, 0.5, 30.0), (2.0, 0.5, 30.0)),
            ((-1.5, 1.0, 45.0), (-1.5, 1.0, 45.0)),
            ((1.0, -0.5, 179.0), (1.0, -0.5, 179.0)),
            ((-1.5, 1.0, 180.0), (1.5, -1.0, 0.0)),
            ((-1.5, 1.0, 225.0), (1.5, -1.0, 45.0)),
            ((-2.0, -0.5, 0.0), (2.0, 0.5, 180.0)),
            ((-2.0, -0.5, 300.0), (2.0, 0.5, 120.0)),
        ]
        for origin in (QPointF(0.0, 0.0), QPointF(2.0, -5.0)):
            for x_off, y_off in ((0.0, 0.0), (-3.0, 2.5)):
                for skew in (-60.0, -20.0, 0.0, 20.0, 60.0):
                    for (sx, sy, deg), (expected_sx, expected_sy, expected_deg) in cases:
                        with self.subTest(origin=origin, offset=(x_off, y_off), skew=skew, params=(sx, sy, deg)):
                            matrix = combine_transform_parameters(x_off, y_off, sx, sy, skew, deg, origin)
                            params = extract_transform_parameters(matrix, origin)
                            self.assertAlmostEqual(params.x_offset, x_off, 5)
                            self.assertAlmostEqual(params.y_offset, y_off, 5)
                            self.assertAlmostEqual(params.x_scale, expected_sx, 5)
                            self.assertAlmostEqual(params.y_scale, expected_sy, 5)
                            self.assertAlmostEqual(params.skew, skew, 5)
                            self._assert_angles_equal(params.rotation, expected_deg)
                            self.assertTrue(0.0 <= params.rotation < 360.0)
                            restored_matrix = combine_transform_parameters(*params, origin)
                            self._assert_transforms_equal(matrix, restored_matrix)

    def _assert_angles_equal(self, angle: float, expected: float) -> None:
        """Compares two angles in degrees on the circle, so 359.99999 matches 0."""
        angle_error = convert_degrees(angle - expected + 180.0) - 180.0
        self.assertAlmostEqual(angle_error, 0.0, 5)

    def _assert_transforms_equal(self, transform: QTransform, expected: QTransform) -> None:
        self.assertTrue(transforms_approx_equal(transform, expected, 5),
                        f'{transform_str(transform)}\n!=\n{transform_str(expected)}')

    def test_transform_parameters_random_matrices(self):
        """Random invertible matrices without perspective survive extract-then-combine at several origins."""
        rng = random.Random(1121)
        origins = (QPointF(0.0, 0.0), QPointF(50.0, 25.0), QPointF(-12.5, 300.0))
        checked = 0
        while checked < 500:
            values = [rng.uniform(-3.0, 3.0) for _ in range(4)] + [rng.uniform(-200.0, 200.0) for _ in range(2)]
            matrix = QTransform(*values)
            if abs(matrix.determinant()) < 0.01:
                continue
            checked += 1
            for origin in origins:
                with self.subTest(matrix=transform_str(matrix), origin=origin):
                    params = extract_transform_parameters(matrix, origin)
                    self.assertFalse(params.x_scale < 0 and params.y_scale < 0)
                    if params.x_scale < 0 or params.y_scale < 0:
                        self.assertLess(params.rotation, 180.0)
                    self.assertTrue(-90.0 < params.skew < 90.0)
                    self._assert_transforms_equal(combine_transform_parameters(*params, origin), matrix)

    def test_positive_skew_leans_right(self):
        """Positive skew about the center moves the top edge right and the bottom edge left."""
        rect = QRectF(0.0, 0.0, 100.0, 50.0)
        matrix = combine_transform_parameters(0.0, 0.0, 1.0, 1.0, 20.0, 0.0, rect.center())
        top_left = matrix.map(rect.topLeft())
        bottom_left = matrix.map(rect.bottomLeft())
        self.assertGreater(top_left.x(), rect.left())
        self.assertLess(bottom_left.x(), rect.left())
        self.assertAlmostEqual(top_left.y(), rect.top(), 5)
        self.assertAlmostEqual(top_left.x() - bottom_left.x(), rect.height() * math.tan(math.radians(20.0)), 5)

    def test_skewed_matrix_parameters(self):
        """A vertical shear reads as rotation plus a negative skew, and flips read with no skew."""
        params = extract_transform_parameters(QTransform(1.0, 0.3, 0.0, 1.0, 50.0, 50.0))
        self.assertAlmostEqual(params.rotation, 16.69924, 4)
        self.assertAlmostEqual(params.skew, -16.69924, 4)
        horizontal = extract_transform_parameters(QTransform.fromScale(-1.0, 1.0))
        self.assertEqual((horizontal.x_scale, horizontal.y_scale, horizontal.skew), (-1.0, 1.0, 0.0))
        self._assert_angles_equal(horizontal.rotation, 0.0)
        vertical = extract_transform_parameters(QTransform.fromScale(1.0, -1.0))
        self.assertEqual((vertical.x_scale, vertical.y_scale, vertical.skew), (1.0, -1.0, 0.0))
        self._assert_angles_equal(vertical.rotation, 0.0)

    def test_combine_rejects_right_angle_skew(self):
        """A skew of 90 degrees or more collapses the layer, so combine_transform_parameters rejects it."""
        for skew in (90.0, -90.0, 120.0):
            with self.subTest(skew=skew):
                with self.assertRaises(AssertionError):
                    combine_transform_parameters(0.0, 0.0, 1.0, 1.0, skew, 0.0)

    def test_transform_parameters_rejects_non_invertible(self):
        """A transform that collapses an axis has no scale, skew and rotation to extract."""
        with self.assertRaises(AssertionError):
            extract_transform_parameters(QTransform.fromScale(0.0, 1.0))

    def test_panel_position(self):
        """panel_position is the scene position of the rectangle's local top-left corner."""
        rect = QRectF(0, 0, 200, 100)
        self.assertEqual(panel_position(rect, QTransform.fromTranslate(10, 20)), QPointF(10, 20))
        rotated = QTransform().rotate(90) * QTransform.fromTranslate(300, 50)
        self.assertEqual(panel_position(rect, rotated), QPointF(300, 50))
        flipped = QTransform.fromScale(-1, 1) * QTransform.fromTranslate(300, 50)
        self.assertEqual(panel_position(rect, flipped), QPointF(300, 50))
        offset_rect = QRectF(5, 7, 200, 100)
        self.assertEqual(panel_position(offset_rect, rotated), rotated.map(QPointF(5, 7)))

    def test_panel_position_stable_under_rotation_about_corner(self):
        """Rotating about the top-left corner leaves panel_position unchanged."""
        rect = QRectF(0, 0, 200, 100)
        base = QTransform.fromTranslate(40, 60)
        self.assertEqual(panel_position(rect, QTransform().rotate(30) * base), panel_position(rect, base))

    def test_transform_at_panel_position(self):
        """transform_at_panel_position moves the top-left corner to the position and keeps rotation and scale."""
        rect = QRectF(0, 0, 200, 100)
        source = QTransform().rotate(30) * QTransform.fromScale(1.5, 0.5) * QTransform.fromTranslate(300, 50)
        moved = transform_at_panel_position(rect, source, QPointF(12.5, -4.0))
        position = panel_position(rect, moved)
        self.assertAlmostEqual(position.x(), 12.5, 5)
        self.assertAlmostEqual(position.y(), -4.0, 5)
        for m_source, m_moved in ((source.m11(), moved.m11()), (source.m12(), moved.m12()),
                                  (source.m21(), moved.m21()), (source.m22(), moved.m22())):
            self.assertEqual(m_source, m_moved)
