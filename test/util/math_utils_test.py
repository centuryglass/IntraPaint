"""Test the numeric helpers in math_utils."""
from src.util.math_utils import avoiding_zero, matching_comparison_to_zero, clamp, convert_degrees
from src.util.shared_constants import MIN_NONZERO
from test.base_test_case import IntraPaintTestCase


class TestMathUtils(IntraPaintTestCase):
    """Test the numeric helpers in math_utils."""

    def test_avoiding_zero_keeps_values_outside_the_dead_zone(self) -> None:
        """Values at or beyond MIN_NONZERO in either direction pass through unchanged."""
        for value in (MIN_NONZERO, -MIN_NONZERO, 0.5, -3.0, 1e9):
            self.assertEqual(avoiding_zero(value), value)

    def test_avoiding_zero_pushes_small_values_out_by_sign(self) -> None:
        """Values inside the dead zone become MIN_NONZERO with the input's sign, including signed zero."""
        self.assertEqual(avoiding_zero(0.0), MIN_NONZERO)
        self.assertEqual(avoiding_zero(-0.0), -MIN_NONZERO)
        self.assertEqual(avoiding_zero(MIN_NONZERO / 2), MIN_NONZERO)
        self.assertEqual(avoiding_zero(-MIN_NONZERO / 2), -MIN_NONZERO)

    def test_matching_comparison_to_zero(self) -> None:
        """Two values match when both are positive, both are negative, or both are zero."""
        for first, second in ((1, 5.0), (-1, -0.1), (0, 0.0)):
            self.assertTrue(matching_comparison_to_zero(first, second), f'{first}, {second}')
        for first, second in ((1, -1), (0, 1), (-2, 0), (0.0, -0.5)):
            self.assertFalse(matching_comparison_to_zero(first, second), f'{first}, {second}')

    def test_clamp(self) -> None:
        """Values outside the range move to the nearest bound, and values inside it are unchanged."""
        self.assertEqual(clamp(5, 0, 10), 5)
        self.assertEqual(clamp(-1, 0, 10), 0)
        self.assertEqual(clamp(11, 0, 10), 10)
        self.assertEqual(clamp(0.5, 0.5, 0.5), 0.5)
        self.assertEqual(clamp(2.5, -1.0, 1.0), 1.0)

    def test_clamp_rejects_inverted_range(self) -> None:
        """A minimum above the maximum fails its assertion."""
        with self.assertRaises(AssertionError):
            clamp(1, 10, 0)

    def test_convert_degrees_wraps_into_one_turn(self) -> None:
        """Angles wrap into 0 <= degrees < 360, with 360 itself becoming 0."""
        for degrees, expected in ((0.0, 0.0), (359.5, 359.5), (360.0, 0.0), (725.0, 5.0), (-90.0, 270.0),
                                  (-720.0, 0.0)):
            self.assertAlmostEqual(convert_degrees(degrees), expected, msg=f'{degrees}')
