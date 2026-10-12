"""Test various geometry utility functions"""
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
        """Transforms split into translation, scale and rotation in a standard form, and recombine unchanged.

        Mirroring both axes is a 180 degree rotation, and mirroring one axis is mirroring the other plus 180 degrees.
        The standard form never has two negative scales, and picks the option with a rotation under 180 degrees.
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
                for (sx, sy, deg), (expected_sx, expected_sy, expected_deg) in cases:
                    with self.subTest(origin=origin, offset=(x_off, y_off), params=(sx, sy, deg)):
                        matrix = combine_transform_parameters(x_off, y_off, sx, sy, deg, origin)
                        final_x, final_y, final_sx, final_sy, final_deg = extract_transform_parameters(matrix, origin)
                        self.assertAlmostEqual(final_x, x_off, 5)
                        self.assertAlmostEqual(final_y, y_off, 5)
                        self.assertAlmostEqual(final_sx, expected_sx, 5)
                        self.assertAlmostEqual(final_sy, expected_sy, 5)
                        # Compare on the circle, so 359.99999 matches 0:
                        angle_error = convert_degrees(final_deg - expected_deg + 180.0) - 180.0
                        self.assertAlmostEqual(angle_error, 0.0, 5)
                        self.assertTrue(0.0 <= final_deg < 360.0)
                        restored_matrix = combine_transform_parameters(final_x, final_y, final_sx, final_sy,
                                                                       final_deg, origin)
                        self.assertTrue(transforms_approx_equal(matrix, restored_matrix, 5),
                                        f'{transform_str(matrix)}\n!=\n{transform_str(restored_matrix)}')

    def test_transform_parameters_rejects_non_invertible(self):
        """A transform that collapses an axis has no scale and rotation to extract."""
        with self.assertRaises(AssertionError):
            extract_transform_parameters(QTransform.fromScale(0.0, 1.0))

    def test_panel_position(self):
        """panel_position is the top-left of the transformed bounding box."""
        rect = QRectF(0, 0, 200, 100)
        self.assertEqual(panel_position(rect, QTransform.fromTranslate(10, 20)), QPointF(10, 20))
        rotated = QTransform().rotate(90) * QTransform.fromTranslate(300, 50)
        self.assertEqual(panel_position(rect, rotated), QPointF(200, 50))
        flipped = QTransform.fromScale(-1, 1) * QTransform.fromTranslate(300, 50)
        self.assertEqual(panel_position(rect, flipped), QPointF(100, 50))

    def test_transform_at_panel_position(self):
        """transform_at_panel_position moves the bounding box to the position and keeps rotation and scale."""
        rect = QRectF(0, 0, 200, 100)
        source = QTransform().rotate(30) * QTransform.fromScale(1.5, 0.5) * QTransform.fromTranslate(300, 50)
        moved = transform_at_panel_position(rect, source, QPointF(12.5, -4.0))
        position = panel_position(rect, moved)
        self.assertAlmostEqual(position.x(), 12.5, 5)
        self.assertAlmostEqual(position.y(), -4.0, 5)
        for m_source, m_moved in ((source.m11(), moved.m11()), (source.m12(), moved.m12()),
                                  (source.m21(), moved.m21()), (source.m22(), moved.m22())):
            self.assertEqual(m_source, m_moved)
