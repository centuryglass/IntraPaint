"""QLayout utility functions"""
from typing import Optional, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QSpacerItem, QWidget, QGridLayout, QHBoxLayout


def extract_layout_item(item: Optional[QLayoutItem]) -> QWidget | QLayout | QSpacerItem | None:
    """Return the item stored within a QLayoutItem."""
    if item is None or item.isEmpty():
        return None
    widget = item.widget()
    if widget is not None:
        return widget
    layout = item.layout()
    if layout is not None:
        return layout
    spacer = item.spacerItem()
    assert spacer is not None
    return spacer


def clear_layout(layout: QLayout, recursive=True, unparent=True, hide=False, clear_stretch=True):
    """Removes all items in a layout, optionally doing the same for recursive inner items."""
    while layout.count() > 0:
        item = extract_layout_item(layout.takeAt(0))
        if recursive and isinstance(item, QLayout):
            clear_layout(item, recursive, unparent, hide)
        elif isinstance(item, QWidget):
            if unparent:
                item.setParent(None)
            if hide:
                item.hide()
    if clear_stretch and isinstance(layout, QGridLayout):
        for row in range(layout.rowCount()):
            layout.setRowStretch(row, 0)
        for column in range(layout.columnCount()):
            layout.setColumnStretch(column, 0)


def synchronize_widths(widgets: List[Optional[QWidget]]) -> None:
    """Synchronizes the widths of several widgets."""
    min_width = 0
    for widget in widgets:
        if widget is None:
            continue
        min_width = max(min_width, widget.sizeHint().width())
    for widget in widgets:
        if widget is None:
            continue
        widget.setMinimumWidth(min_width)


def synchronize_row_widths(rows: List[List[Optional[QWidget]]]) -> None:
    """Synchronizes the widths of column widgets within several equal_sized rows."""
    if len(rows) < 2:
        return
    column_count = len(rows[0])
    assert all(len(row) == column_count for row in rows)
    columns: List[List[Optional[QWidget]]] = []
    for i in range(column_count):
        columns.append([])
    for row in rows:
        for i, widget in enumerate(row):
            columns[i].append(widget)
    for column in columns:
        synchronize_widths(column)


def wrap_widget_with_key_hints(widget: QWidget, left_hint: Optional[QWidget] = None,
                               right_hint: Optional[QWidget] = None, parent: Optional[QWidget] = None,
                               alignment=Qt.AlignmentFlag.AlignCenter) -> QWidget:
    """Wraps a widget in a small container widget, with key hints on one or both sides."""
    if left_hint is None and right_hint is None:
        raise RuntimeError('At least one key hint label should be non-null')
    container = QWidget(parent=parent)
    layout = QHBoxLayout(container)
    layout.setAlignment(alignment)
    layout.setSpacing(1)
    layout.setContentsMargins(1, 1, 1, 1)
    if left_hint is not None:
        layout.addWidget(left_hint)
    layout.addWidget(widget)
    if right_hint is not None:
        layout.addWidget(right_hint)
    return container
