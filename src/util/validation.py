"""Provides a convenience function for miscellaneous validation."""
import json
from typing import Any, Iterable

from PyQt5.QtCore import QSize
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget, QLayout, QSizePolicy


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


def layout_debug(widget: QWidget) -> None:
    """Dump nested layout info to a JSON file for inspection."""
    layout_data = {}

    def _policy_str(policy: QSizePolicy.Policy) -> str:
        match policy:
            case QSizePolicy.Policy.Expanding:
                return 'Expanding'
            case QSizePolicy.Policy.MinimumExpanding:
                return 'MinimumExpanding'
            case QSizePolicy.Policy.Fixed:
                return 'Fixed'
            case QSizePolicy.Policy.Maximum:
                return 'Maximum'
            case QSizePolicy.Policy.Preferred:
                return 'Preferred'
            case QSizePolicy.Policy.Ignored:
                return 'ignored'
            case _:
                return f'unknown ({policy})'

    def _record_size(width_key: str, height_key: str, size: QSize, record: dict):
        if size is not None and not size.isNull():
            record[width_key] = size.width()
            record[height_key] = size.height()

    def _add_item(item: QLayout | QWidget, record: dict) -> None:
        record['type'] = str(item.__class__)
        if hasattr(item, 'sizePolicy'):
            record['w_policy'] = _policy_str(item.sizePolicy().horizontalPolicy())
            record['h_policy'] = _policy_str(item.sizePolicy().verticalPolicy())
        _record_size('minW', 'minH', item.minimumSize(), record)
        _record_size('maxW', 'maxH', item.minimumSize(), record)
        _record_size('hintW', 'hintH', item.sizeHint(), record)
        if isinstance(item, QWidget):
            _record_size('w', 'h', item.size(), record)
            layout = item.layout()
            if layout is not None:
                record['layout'] = {}
                _add_item(layout, record['layout'])
        else:
            assert isinstance(item, QLayout)
            record['spacing'] = item.spacing()
            record['margins'] = str(item.contentsMargins())
            record['children'] = []
            for i in range(item.count()):
                child = item.itemAt(i)
                widget = child.widget()
                if widget is not None:
                    data = {}
                    _add_item(widget, data)
                    record['children'].append(data)
                else:
                    layout = child.layout()
                    if layout is not None:
                        data = {}
                        _add_item(layout, data)
                        record['children'].append(data)
    _add_item(widget, layout_data)
    json.dump(layout_data, open('layout-debug.json', 'w'), indent=2)
