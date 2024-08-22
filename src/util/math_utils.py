"""Miscellaneous math utility functions."""
import math

from src.util.shared_constants import MIN_NONZERO


def avoiding_zero(value: float) -> float:
    """Returns the closest value not between -.001 and .001"""
    if abs(value) >= MIN_NONZERO:
        return value
    return math.copysign(MIN_NONZERO, value)


def matching_comparison_to_zero(value1: int | float, value2: int | float) -> bool:
    """Return true if both values are greater than zero, both values are less than zero, or both values equal zero."""
    return (value1 == value2 == 0) or (value1 > 0 and value2 > 0) or (value1 < 0 and value2 < 0)


def clamp(value: int | float, min_value: int | float, max_value: int | float) -> int | float:
    """Returns the value, adjusted if necessary to ensure that it is within an expected range."""
    assert min_value <= max_value
    return max(min_value, min(max_value, value))


def convert_degrees(deg):
    """Keep measurements in the 0.0 <= deg < 360.0 range"""
    while deg < 0:
        deg += 360.0
    while deg >= 360.0:
        deg -= 360.0
    return deg
