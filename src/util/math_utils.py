"""Miscellaneous math utility functions."""
import math

from src.util.shared_constants import MIN_NONZERO


def avoiding_zero(value: float) -> float:
    """Returns the closest value not between -.001 and .001"""
    if abs(value) >= MIN_NONZERO:
        return value
    return math.copysign(MIN_NONZERO, value)


def clamp(value: int | float, min_value: int | float, max_value: int | float) -> int | float:
    """Returns the value, adjusted if necessary to ensure that it is within an expected range."""
    assert min_value <= max_value
    return max(min_value, min(max_value, value))
