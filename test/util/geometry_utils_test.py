"""Test various geometry utility functions"""
import math
import sys
import unittest

from PySide6.QtCore import QPointF, QLineF
from PySide6.QtGui import QTransform
from PySide6.QtWidgets import QApplication

from src.util.geometry_utils import extract_transform_parameters, combine_transform_parameters, transform_str, \
    transforms_approx_equal
from src.util.math_utils import convert_degrees

app = QApplication.instance() or QApplication(sys.argv)

class TestGeometryUtils(unittest.TestCase):
    """Test various geometry utility functions"""

    def test_transform_parameters(self):
        """Ensure transformations can be reliably divided into rotation, scale, and translation components, and merged
           back into complete transformations."""
        def range_f(start, end, step):
            """Floating-point range iterator."""
            while start < end:
                yield start
                start += step

        x_err_map = {}
        y_err_map = {}
        valid_signs = set()
        invalid_signs = set()

        def sign_str(mat, angle):
            def sign_char(n):
                if n == 0:
                    return '0'
                if n > 0:
                    return '+'
                return '-'
            s = f'angle: {sign_char(angle)}\n'
            s += sign_char(mat.m11()) + ', '
            s += sign_char(mat.m12()) + '\n'
            s += sign_char(mat.m21()) + ', '
            s += sign_char(mat.m22()) + '\n---'
            return s

        for origin in [QPointF(0.0, 0.0), QPointF(2.0, -5.0)]:
            for x_off in range(-3, 3):
                for y_off in range(-3, 3):
                    for sx in range_f(-2.0, 2.0, 0.5):
                        for sy in range_f(-2.0, 2.0, 0.5):
                            for deg in range_f(0.0, 360.0, 1.5):
                                if sx == 0 or sy == 0:
                                    continue

                                matrix = QTransform.fromTranslate(-origin.x(), -origin.y())
                                matrix *= QTransform.fromScale(sx, sy)
                                matrix *= QTransform().rotate(deg)
                                matrix *= QTransform.fromTranslate(x_off + origin.x(), y_off + origin.y())
                                if not matrix.isInvertible():
                                    continue  # Non-invertible transformations aren't allowed
                                final_x, final_y, final_sx, final_sy, final_deg = extract_transform_parameters(matrix,
                                                                                                               origin)
                                if sx < 0 and sy < 0:
                                    # Mirroring both x and y is equivalent to rotation:
                                    x_scale = sx * -1
                                    y_scale = sy * -1
                                    angle = convert_degrees(deg - 180)
                                elif ((sx < 0) or (sy < 0)) and convert_degrees(deg) >= 180.0:
                                    # Mirroring x is equivalent to mirroring y and rotating 180 degrees, so standardize
                                    # by picking the option with the smaller angle.
                                    x_scale = -sx
                                    y_scale = -sy
                                    angle = convert_degrees(deg - 180)
                                else:
                                    x_scale = sx
                                    y_scale = sy
                                    angle = convert_degrees(deg)

                                if not math.isclose(convert_degrees(final_deg), angle) \
                                        or not math.isclose(final_sx, x_scale, abs_tol=0.00001) \
                                        or not math.isclose(final_sy, y_scale, abs_tol=0.00001) \
                                        or not math.isclose(final_x, x_off, abs_tol=0.00001) \
                                        or not math.isclose(final_y, y_off, abs_tol=0.00001):
                                    # Print full diagnostic output before failing:
                                    print(f'FAILED:\nExpected values:\n\t{convert_degrees(angle)}'
                                          f' degrees, x={x_off}, y={y_off}, sx={x_scale}, sy={y_scale}')
                                    print(f'Values returned:\n\t{convert_degrees(final_deg)} degrees, x={final_x}, '
                                          f'y={final_y} sx={final_sx}, sy={final_sy}'
                                          f'\nDeterminant: {matrix.m11() * matrix.m22() - matrix.m12() * matrix.m21()}'
                                          f'\nFull matrix:')
                                    print(transform_str(matrix))
                                self.assertAlmostEqual(convert_degrees(final_deg), angle)
                                self.assertAlmostEqual(final_x, x_off,  5)
                                self.assertAlmostEqual(final_y, y_off, 5)
                                self.assertAlmostEqual(final_sx, x_scale, 5)
                                self.assertAlmostEqual(final_sy, y_scale, 5)
                                restored_matrix = combine_transform_parameters(final_x, final_y, final_sx, final_sy,
                                                                               final_deg, origin)
                                self.assertTrue(transforms_approx_equal(matrix, restored_matrix, 5))
