"""Column packing: stacks sections top to bottom in columns while they fit a height budget.

`pack_columns` decides which items share a column, from their heights alone. `PackedColumns` owns the column widgets
and moves sections between them without rebuilding the sections. `SectionPacker` is what a panel uses: it measures the
sections, plans and fills the columns within the panel's budget, and plans again when a section opens or closes. Each
owner places the column widgets in its own layout.
"""
from contextlib import contextmanager
from typing import Callable, Collection, Iterator, Sequence

from PySide6.QtWidgets import QVBoxLayout, QWidget

from src.ui.layout.panel_fit import fresh_minimum_size, held_weakly
from src.ui.widget.panel_section import PanelSection


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


class SectionPacker:
    """Packs a strip's sections into columns, for a panel that opts in to column packing.

    - The owner calls `pack` each time it arranges a strip, and `release` when it leaves one. Between the two the packer
      is `packing`.
    - `pack` measures the shown sections with `fresh_minimum_size`, splits them into columns that fit `budget()` with
      `pack_columns`, and moves them into the columns. Hidden sections take no column.
    - `budget()` returns the height a column has, or zero before the owner's first plan, which gives every section its
      own column. Inside `base_measurement` the budget is zero, so a base size measured there doesn't depend on
      earlier plans.
    - While packing, opening or closing a section passed to `watch` calls `replan`, since its height decides the
      columns.

    Bound-method callbacks are held weakly, since the owner owns the packer.
    """

    def __init__(self, budget: Callable[[], int], replan: Callable[[], None]) -> None:
        self._budget = held_weakly(budget)
        self._replan = held_weakly(replan)
        self._columns = PackedColumns()
        self._packing = False
        # Whether the columns are in the owner's layout as the current plan has them:
        self._placed = False
        self._base_depth = 0

    @property
    def packing(self) -> bool:
        """Whether the owner is arranged as a packing strip: `pack` ran, and `release` hasn't since."""
        return self._packing

    @property
    def columns(self) -> list[QWidget]:
        """Every column widget made so far, for the owner to take out of its layout."""
        return self._columns.columns

    @property
    def plan(self) -> list[tuple[QWidget, ...]]:
        """The sections in each column, as of the last `pack` or `release`."""
        return self._columns.plan

    def holds(self, widget: QWidget) -> bool:
        """Returns whether a column is the widget's parent."""
        return self._columns.holds(widget)

    def budget(self) -> int:
        """Returns the height a column has: zero inside `base_measurement`, and otherwise the owner's budget."""
        return 0 if self._base_depth > 0 else self._budget()

    @contextmanager
    def base_measurement(self) -> Iterator[None]:
        """Packs every section into its own column while the block runs."""
        self._base_depth += 1
        try:
            yield
        finally:
            self._base_depth -= 1

    def watch(self, section: PanelSection) -> None:
        """Plans again when the section opens or closes while packing."""
        section.expanded_changed.connect(self._section_toggled)

    def invalidate(self) -> None:
        """Makes the next `pack` fill the columns even with an unchanged plan, after the owner took them out of its
        layout."""
        self._placed = False

    def pack(self, sections: Sequence[QWidget], spacing: int, add_column: Callable[[QWidget], None],
             clear: Callable[[], None] = lambda: None, alone: Collection[QWidget] = ()) -> bool:
        """Packs the shown sections, in order, into columns with `spacing` between sections, and returns whether the
        columns changed.

        While the plan and the placed columns are unchanged, this does nothing. Otherwise `clear` takes `columns`, and
        anything the owner places after them, out of its layout, and `add_column` adds each column in use in order. A
        section in `alone` never shares a column, and takes its column's spare height.
        """
        self._packing = True
        shown = [section for section in sections if not section.isHidden()]
        heights = [fresh_minimum_size(section).height() for section in shown]
        alone_indices = {index for index, section in enumerate(shown) if section in alone}
        plan = [tuple(shown[index] for index in column)
                for column in pack_columns(heights, self.budget(), spacing, alone_indices)]
        if self._placed and plan == self._columns.plan:
            return False
        clear()
        self._columns.fill(plan, spacing, add_column, alone)
        self._placed = True
        return True

    def release(self) -> list[QWidget]:
        """Leaves packing. Takes the sections still in a column out of it and hides the columns, and returns those
        sections in order. The owner removes `columns` from its layout, puts the sections back in it and shows them,
        since reparenting hides a widget. A section the owner moved elsewhere since the last `pack` stays there."""
        released = [section for column in self._columns.plan for section in column if self.holds(section)]
        self._columns.release(released)
        self._packing = False
        self._placed = False
        return released

    def _section_toggled(self, _expanded: bool) -> None:
        if self._packing:
            self._replan()
