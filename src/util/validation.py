"""Provides a convenience function for miscellaneous validation."""
from typing import Any, Iterable

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget


def assert_type(value: Any, expected_type: Any) -> None:
    """Checks if a value's type matches expectations.

    Parameters
    ----------
    value : any
        The value to validate
    expected_type : type or class or tuple of types or classes
        Valid type or types that the value could match.
    Raises
    ------
    TypeError
        If the value is not of the expected type.
    """
    if not isinstance(value, expected_type):
        raise TypeError(f'Expected value of type {expected_type}, got value {value}')


def assert_types(values: Iterable[Any], expected_type: Any) -> None:
    """Checks if a group of values all have certain expected types.

    Parameters
    ----------
    values : iterable
        A collection of values to validate
    expected_type : type or class or tuple of types or classes
        Valid type or types that the value could match.
    Raises
    ------
    TypeError
        If the value is not of the expected type.

    Args:
        values:
    """
    for value in values:
        if not isinstance(value, expected_type):
            raise TypeError(f'Expected value of type {expected_type}, got value {value}')


def assert_valid_index(index: Any, list_value: list[Any], allow_end: bool = False) -> None:
    """Checks if a value is a valid index into a list.

    Parameters
    ----------
    index : int
        Index to validate
    list_value : list
        The list being indexed
    allow_end : bool, default=False
        If true, also accept the index one past the end of the list.
    Raises
    ------
    TypeError
        If the index is not an int, or list_value is not a list.
    ValueError
        If the index is not within the list bounds.
    """
    assert_type(index, int)
    assert_type(list_value, list)
    if not 0 <= index < (len(list_value) + 1 if allow_end else len(list_value)):
        raise ValueError(f'index {index} is invalid, expected (0 <= index < {len(list_value)})')


def debug_widget_bounds(widget: QWidget, color: QColor) -> None:
    """Sets a widget background to a solid color, useful for debugging layout issues."""
    palette = widget.palette()
    palette.setColor(widget.backgroundRole(), color)
    widget.setPalette(palette)
    widget.setAutoFillBackground(True)
