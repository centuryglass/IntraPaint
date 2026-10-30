"""Column packing: stacks sections top to bottom in columns while they fit a height budget.

`pack_columns` decides which items share a column, from their heights alone. `PackedColumns` owns the column widgets
and moves sections between them without rebuilding the sections. `DockPanel` and `StrokeBlock` use both, each placing
the column widgets in its own layout.
"""
from typing import Callable, Collection, Sequence

from PySide6.QtWidgets import QVBoxLayout, QWidget


def pack_columns(heights: Sequence[int], budget: int, spacing: int, alone: Collection[int] = ()) -> list[list[int]]:
    """Splits ordered items into columns and returns each column's item indices.

    An item goes under the previous one when the column's height, spacing included, stays within `budget`, and starts a
    new column otherwise. An item never splits, and one taller than the budget gets a column to itself. An item listed
    in `alone` never shares a column, so the items on either side of it start new ones. A budget of zero or less puts
    every item in its own column.
    """
    columns: list[list[int]] = []
    used = 0
    previous_alone = True
    for index, height in enumerate(heights):
        is_alone = index in alone
        if not previous_alone and not is_alone and used + spacing + height <= budget:
            columns[-1].append(index)
            used += spacing + height
        else:
            columns.append([index])
            used = height
        previous_alone = is_alone
    return columns


class PackedColumns:
    """The column widgets that hold packed sections.

    The owner removes `columns` from its layout, calls `fill` with a plan, which adds the columns in use.
    A section moves between columns without being rebuilt, so its state and focus survive.
    """

    def __init__(self) -> None:
        self._columns: list[QWidget] = []
        self._plan: list[tuple[QWidget, ...]] = []

    @property
    def columns(self) -> list[QWidget]:
        """Every column widget made so far, whether or not the current plan uses it."""
        return self._columns

    @property
    def plan(self) -> list[tuple[QWidget, ...]]:
        """The sections in each column, as of the last `fill` or `release`."""
        return self._plan

    def holds(self, widget: QWidget) -> bool:
        """Returns whether a column is the widget's parent."""
        return widget.parentWidget() in self._columns

    def fill(self, plan: list[tuple[QWidget, ...]], spacing: int, add_column: Callable[[QWidget], None],
             stretching: Collection[QWidget] = ()) -> None:
        """Moves each plan entry's sections into a column, and adds each column in use to the owner's layout in order
        with `add_column`. The columns are shown after they are added, since adding a widget to a layout reparents it.

        The owner has removed `columns` from its layout. Sections are shown after the move, since reparenting hides a
        widget, so only sections that are shown belong in a plan. A section in `stretching` takes the column's spare
        height.
        """
        self._plan = plan
        for sections in plan:
            for widget in sections:
                self.detach(widget)
        while len(self._columns) < len(plan):
            column = QWidget()
            column_layout = QVBoxLayout(column)
            column_layout.setContentsMargins(0, 0, 0, 0)
            column_layout.addStretch()
            self._columns.append(column)
        for column in self._columns:
            column.layout().setSpacing(spacing)
        for column, sections in zip(self._columns, plan):
            column_layout = column.layout()
            for widget in sections:
                column_layout.insertWidget(column_layout.count() - 1, widget, 1 if widget in stretching else 0)
                widget.show()
            add_column(column)
            column.show()
        for column in self._columns[len(plan):]:
            column.hide()

    def release(self, sections: Sequence[QWidget]) -> None:
        """Takes sections out of their columns and hides the columns, for an owner that stops packing. The owner puts
        the sections back in its own layout and shows them."""
        for widget in sections:
            self.detach(widget)
        for column in self._columns:
            column.hide()
        self._plan = []

    @staticmethod
    def detach(widget: QWidget) -> None:
        """Removes a widget from its parent's layout, leaving it a child of that parent."""
        parent = widget.parentWidget()
        if parent is not None and parent.layout() is not None:
            parent.layout().removeWidget(widget)
