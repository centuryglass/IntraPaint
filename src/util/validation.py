"""Provides a convenience function for miscellaneous validation."""
import json
from typing import Any, Iterable

from PySide6.QtCore import QSize, QRect, QRectF, QSizeF, QMargins, QMarginsF
from PySide6.QtGui import QColor, Qt, QRegion, QScreen
from PySide6.QtWidgets import QWidget, QLayout, QSizePolicy, QBoxLayout, QGridLayout

from src.util.shared_constants import MAX_WIDGET_SIZE


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
    assert isinstance(index, int)
    assert isinstance(list_value, list)
    if not 0 <= index < (len(list_value) + 1 if allow_end else len(list_value)):
        raise ValueError(f'index {index} is invalid, expected (0 <= index < {len(list_value)})')


def debug_widget_bounds(widget: QWidget, color: QColor) -> None:
    """Sets a widget background to a solid color, useful for debugging layout issues."""
    palette = widget.palette()
    palette.setColor(widget.backgroundRole(), color)
    widget.setPalette(palette)
    widget.setAutoFillBackground(True)


def size_policy_str(policy: QSizePolicy.Policy | QSizePolicy) -> str:
    """Get a string representation of a QSizePolicy."""
    if isinstance(policy, QSizePolicy):
        return (f'horizontal: {size_policy_str(policy.horizontalPolicy())},'
                f' vertical: {size_policy_str(policy.verticalPolicy())},'
                f' horizontal stretch: {policy.horizontalStretch()},'
                f' vertical stretch: {policy.verticalStretch()},'
                f' control type: {policy.controlType()}')
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


def alignment_str(alignment: Qt.AlignmentFlag) -> str:
    """Get a string representation of a Qt alignment."""
    matching = []
    alignments = {
        Qt.AlignmentFlag.AlignTop: 'top',
        Qt.AlignmentFlag.AlignCenter: 'center',
        Qt.AlignmentFlag.AlignBottom: 'bottom',
        Qt.AlignmentFlag.AlignLeft: 'left',
        Qt.AlignmentFlag.AlignRight: 'right',
        Qt.AlignmentFlag.AlignBaseline: 'baseline',
        Qt.AlignmentFlag.AlignJustify: 'justify',
        Qt.AlignmentFlag.AlignVCenter: 'center-vertical',
        Qt.AlignmentFlag.AlignHCenter: 'center-horizontal',
        Qt.AlignmentFlag.AlignAbsolute: 'absolute',
    }
    for alignment_type, name in alignments.items():
        if alignment_type == (alignment & alignment_type):
            matching.append(name)
    if len(matching) == 0:
        return 'None'
    return ' | '.join(matching)


def rect_str(rect: QRect | QRectF) -> str:
    """Returns a string representation of a Qt rectangle."""
    if rect is None:
        return 'None'
    if not isinstance(rect, (QRect, QRectF)):
        return str(rect)
    return f'{rect.width()}x{rect.height()} at ({rect.x()}, {rect.y()})'


def region_str(region: QRegion) -> str:
    """Returns a string representation of a Qt Region object."""
    if region is None:
        return 'None'
    if not isinstance(region, QRegion):
        return str(region)
    text = f'{rect_str(region.boundingRect())}: '
    if region.rectCount() < 3:
        # noinspection PyUnresolvedReferences
        text += ', '.join((rect_str(region[i]) for i in range(region.rectCount())))
    else:
        text += f'{region.rectCount()} regions'
    return text


def size_str(size: QSize | QSizeF) -> str:
    """Returns a string representation of a Qt size object."""
    if size is None:
        return 'None'
    if not isinstance(size, (QSize, QSizeF)):
        return str(size)
    return f'{size.width()}x{size.height()}'


def margins_str(margins: QMargins | QMarginsF) -> str:
    """Returns a string representation of a Qt margin object."""
    if margins is None:
        return 'None'
    if not isinstance(margins, (QMargins, QMarginsF)):
        return str(margins)
    return f'left: {margins.left()}, right: {margins.right()}, top: {margins.top()}, bottom: {margins.bottom()}'


def screen_str(screen: QScreen) -> str:
    """Returns a string representation of a Qt screen object."""
    if screen is None:
        return 'None'
    if not isinstance(screen, QScreen):
        return str(screen)
    return f'screen "{screen.name()}" at {rect_str(screen.geometry())}'


def orientation_str(orientation: Qt.Orientation) -> str:
    """Returns a string representation of a Qt orientation."""
    if orientation is None:
        return 'None'
    if not isinstance(orientation, Qt.Orientation):
        return str(orientation)
    return 'horizontal' if orientation == Qt.Orientation.Horizontal else 'vertical'


def all_layout_info(item: Any, include_containing_layout_data=True) -> dict[str, str]:
    """Get all layout info for a single item, checking for all known properties."""
    layout_data = {'type': str(type(item))}
    expected_attrs = [
        ('text', None),
        ('sizePolicy', size_policy_str),
        ('alignment', alignment_str),
        ('spacing', None),
        ('layout', None),
        ('isEnabled', None),
        ('isHidden', None),
        ('isVisible', None),
        ('geometry', rect_str),
        ('frameGeometry', rect_str),
        ('contentsMargins', margins_str),
        ('contentsRect', rect_str),
        ('sizeHint', size_str),
        ('minimumSizeHint', size_str),
        ('maximumSize', size_str),
        ('minimumSize', size_str),
        ('childrenRect', rect_str),
        ('childrenRegion', region_str),
        ('mask', region_str),
        ('orientation', orientation_str),
        ('get_orientation', orientation_str),
        ('screen', screen_str),
        ('baseSize', size_str),
        ('sizeIncrement', size_str),
        ('styleSheet', None)
    ]
    for attr_name, str_getter in expected_attrs:
        if not hasattr(item, attr_name):
            continue
        item_attr = getattr(item, attr_name)
        if callable(item_attr):
            item_attr = item_attr()
        text = str(item_attr) if str_getter is None else str_getter(item_attr)
        layout_data[attr_name] = text
    possible_duplicates = [
        ('geometry', 'frameGeometry'),
        ('sizeHint', 'minimumSizeHint')
    ]
    for key1, key2 in possible_duplicates:
        if key1 in layout_data and key2 in layout_data and layout_data[key1] == layout_data[key2]:
            del layout_data[key2]

    if isinstance(item, QWidget) and include_containing_layout_data:
        parent = item.parentWidget()
        if isinstance(parent, QWidget):
            layout = parent.layout()
            if layout is not None:
                idx = layout.indexOf(item)
                layout_data['layout:index'] = str(idx)
                if idx >= 0:
                    layout_data['layout:spacing'] = str(layout.spacing())
                    layout_data['layout:margins'] = margins_str(layout.contentsMargins())
                    layout_data['layout:alignment'] = alignment_str(layout.alignment())
                    if isinstance(layout, QBoxLayout):
                        full_stretch = 0
                        for i in range(layout.count()):
                            full_stretch += layout.stretch(i)
                        layout_data['layout:stretch'] = f'{layout.stretch(idx)}/{full_stretch}'
                    if isinstance(layout, QGridLayout):
                        row, col, r_span, col_span = layout.getItemPosition(idx)
                        layout_data['layout:size,row,col'] = f'{col_span}x{r_span}, {row},{col}'
                        row_stretch = 0
                        col_stretch = 0
                        for i in range(col, col+col_span, 1):
                            col_stretch += layout.columnStretch(i)
                        for i in range(row, row+r_span, 1):
                            row_stretch += layout.rowStretch(i)
                        s_row_full = 0
                        s_col_full = 0
                        for i in range(layout.columnCount()):
                            s_col_full += layout.columnStretch(i)
                        for i in range(layout.rowCount()):
                            s_row_full += layout.rowStretch(i)
                        layout_data['layout:stretch(x,y)'] = f'{col_stretch},{row_stretch} / {s_col_full},{s_row_full}'
                        layout_data['layout:grid_min'] = (f'{layout.columnMinimumWidth(col)}'
                                                          f'x{layout.rowMinimumHeight(row)}')

    ignored_values = [rect_str(QRect()), rect_str(QRectF()), size_str(QSize()), size_str(QSizeF()),
                      region_str(QRegion()), 'None', '', QSize(MAX_WIDGET_SIZE, MAX_WIDGET_SIZE)]
    keys = list(layout_data.keys())
    for key in keys:
        if layout_data[key] in ignored_values:
            del layout_data[key]
    return layout_data


def layout_debug(widget: QWidget) -> None:
    """Dump nested layout info to a JSON file for inspection."""
    layout_data: dict[str, Any] = {}

    def _add_item(item: QLayout | QWidget, record: dict[str, Any]) -> None:
        item_data = all_layout_info(item, True)
        for k, v in item_data.items():
            record[k] = v
        if isinstance(item, QWidget):
            layout = item.layout()
            if layout is not None:
                record['layout'] = {}
                _add_item(layout, record['layout'])
        elif isinstance(item, QLayout):
            record['children'] = []
            for i in range(item.count()):
                child = item.itemAt(i)
                assert child is not None
                child_widget = child.widget()
                data: dict[str, Any] = {}
                if child_widget is not None:
                    _add_item(child_widget, data)
                    record['children'].append(data)
                else:
                    layout = child.layout()
                    if layout is not None:
                        _add_item(layout, data)
                        record['children'].append(data)
    _add_item(widget, layout_data)
    json.dump(layout_data, open('layout-debug.json', 'w', encoding='utf-8'), indent=2)
