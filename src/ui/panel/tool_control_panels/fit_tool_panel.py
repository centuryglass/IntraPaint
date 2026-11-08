"""A base for tool control panels that plan their own layout by fit, as `src.ui.layout.panel_fit.FitContent`.

The Tools panel measures such a panel at `fit_base_size`, then passes it the space left over with `set_fit_space`.
Outside a `DockPanel`, the panel plans for its own size when resized. Subclasses create `_planner`, a `FitPlanner` over
their items, and arrange their widgets in its `apply` callback.

A subclass whose strip stacks sections in columns (`src.ui.layout.column_packing`) uses `_packer`: it passes its
sections to `_packer.watch` once, calls `_packer.pack` when it arranges a strip and `_packer.release` when it arranges a
side panel. The column budget is the planned height, and `fit_base_size` measures with every section in its own column.
"""
from typing import Collection, Optional, Sequence

from PySide6.QtCore import QEvent, QMargins, QSize, Qt
from PySide6.QtWidgets import QBoxLayout, QGridLayout, QVBoxLayout, QWidget

from src.ui.layout.column_packing import PackedColumns, SectionPacker
from src.ui.layout.dock_panel import QWIDGETSIZE_MAX, DockPanel
from src.ui.layout.panel_fit import (strip_section_max_width, FitPlanner, Orientation, fresh_minimum_size,
                                     orientation_for_size)


class FitToolPanel(QWidget):
    """A tool control panel planned by fit. Optional controls a plan leaves out go in `overflow_content`, which the
    Tools panel shows in its More popover."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._space: Optional[QSize] = None
        self._planning = False
        self._orientation = Orientation.SIDE
        self._planner: Optional[FitPlanner] = None
        self._overflow = QWidget()
        self._overflow_layout = QVBoxLayout(self._overflow)
        self._overflow_layout.setContentsMargins(0, 0, 0, 0)
        self._packer = SectionPacker(self._column_budget, self._refit)

    def fit_base_size(self, orientation: Orientation) -> QSize:
        """Returns the minimum size with required items in their smallest forms, optional items left out, and every
        packed section in its own column, and keeps that arrangement until the next `set_fit_space`."""
        assert self._planner is not None
        with self._packer.base_measurement():
            return self._planner.base_size(orientation)

    def _column_budget(self) -> int:
        """Returns the height a strip's packed columns have: the planned space's less the layout's margins, or zero
        before the first plan."""
        space = None if self._planner is None else self._planner.available
        if space is None:
            return 0
        layout = self.layout()
        margins = layout.contentsMargins() if layout is not None else QMargins()
        return space.height() - margins.top() - margins.bottom()

    def set_fit_space(self, orientation: Orientation, size: QSize) -> None:
        """Plans for the space the Tools panel gives the panel."""
        assert self._planner is not None
        self._space = QSize(size)
        self._planner.update(orientation, size)

    def overflow_content(self) -> QWidget:
        """Returns the widget holding the controls the latest plan left out."""
        return self._overflow

    def _measure_fit(self) -> QSize:
        return fresh_minimum_size(self)

    def _host(self) -> Optional[DockPanel]:
        """Returns the `DockPanel` the panel is inside, or None."""
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, DockPanel):
                return parent
            parent = parent.parentWidget()
        return None

    def _refit(self) -> None:
        """Plans again after a row appears or disappears: the hosting panel if there is one, or else this panel."""
        host = self._host()
        if host is not None:
            host.refit()
        elif self._planner is not None and self._planner.placement is not None:
            self._plan_own_size(force=True)

    def _plan_own_size(self, force: bool = False) -> None:
        """Plans for the space the host gave the panel, or for its own size without a host. Trial placements can
        resize the panel, and the resize this causes doesn't start another plan."""
        if self._planning or self._planner is None:
            return
        self._planning = True
        try:
            if self._space is not None:
                self._planner.update(self._orientation, self._space, force)
            else:
                self._planner.update(orientation_for_size(self.size(), self._orientation), self.size(), force)
        finally:
            self._planning = False

    def _arrange_box_sections(self, layout: QBoxLayout, sections: Sequence[QWidget], orientation: Orientation) -> None:
        """Stacks sections top to bottom in a side panel, or packs a strip's into columns of up to
        `strip_section_max_width()` each. Spare room goes after them. `layout` holds only the sections, in order, and
        the spare room."""
        if orientation == Orientation.STRIP:
            layout.setDirection(QBoxLayout.Direction.LeftToRight)
            if not self._packer.packing:
                self._take_items(layout)
            for section in sections:
                self._cap_width(section)

            def _add_column(column: QWidget) -> None:
                members = self._packer.plan[layout.count()]
                column.setMaximumWidth(max(section.maximumWidth() for section in members))
                layout.addWidget(column)

            if self._packer.pack(sections, max(layout.spacing(), 0), _add_column, lambda: self._take_items(layout)):
                layout.addStretch(1)
            return
        layout.setDirection(QBoxLayout.Direction.TopToBottom)
        if not self._packer.packing:
            return
        released = self._packer.release()
        self._take_items(layout)
        for section in sections:
            PackedColumns.detach(section)
            section.setMaximumWidth(QWIDGETSIZE_MAX)
            layout.addWidget(section)
        layout.addStretch(1)
        # Leaving a packed column hid the sections that were shown:
        for section in released:
            section.show()

    @staticmethod
    def _take_items(layout: QBoxLayout) -> None:
        """Takes every item out of a layout, leaving its widgets where they are."""
        while layout.count() > 0:
            layout.takeAt(0)

    def _pack_grid_columns(self, grid: QGridLayout, sections: Sequence[QWidget], first_column: int = 0,
                           row_span: int = 1, alone: Collection[QWidget] = ()) -> int:
        """Packs a strip's sections into columns in the grid's first row, from `first_column`, and returns the column
        after the last. Each column spans `row_span` rows and is as wide as its widest section allows. A column holding
        a section in `alone` takes the rows' height, and the others sit at the top.

        The caller took `_packer.columns` out of the grid first, and calls `_packer.invalidate` when it did."""
        added = first_column

        def _add_column(column: QWidget) -> None:
            nonlocal added
            members = self._packer.plan[added - first_column]
            column.setMaximumWidth(max(section.maximumWidth() for section in members))
            if any(section in alone for section in members):
                grid.addWidget(column, 0, added, row_span, 1)
            else:
                grid.addWidget(column, 0, added, row_span, 1, Qt.AlignmentFlag.AlignTop)
            added += 1

        self._packer.pack(sections, max(grid.verticalSpacing(), 0), _add_column, alone=alone)
        return first_column + len(self._packer.plan)

    @staticmethod
    def _stretch_grid_columns(grid: QGridLayout, used_columns: int, strip: bool) -> None:
        """Shares spare width equally between a grid's used columns. In a strip, width past the columns' caps goes to
        the column after them, or the grid would spread it between them."""
        for column in range(used_columns):
            grid.setColumnStretch(column, 1)
        grid.setColumnStretch(used_columns, 1 if strip else 0)

    @staticmethod
    def _body_grid(body: QWidget) -> QGridLayout:
        layout = QGridLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        return layout

    @staticmethod
    def _clear(layout: QGridLayout, widgets: tuple[QWidget, ...]) -> None:
        """Takes widgets out of a grid and clears its stretch factors, so an arrangement leaves no trace of the last."""
        for widget in widgets:
            layout.removeWidget(widget)
        for index in range(layout.rowCount()):
            layout.setRowStretch(index, 0)
        for index in range(layout.columnCount()):
            layout.setColumnStretch(index, 0)

    @staticmethod
    def _cap_width(widget: QWidget) -> None:
        """Caps a section at `strip_section_max_width()`, or at its minimum width if that is wider."""
        widget.setMaximumWidth(QWIDGETSIZE_MAX)
        widget.setMaximumWidth(max(strip_section_max_width(), fresh_minimum_size(widget).width()))

    def event(self, event: QEvent) -> bool:
        """Forgets the host's space when the panel moves to a new parent, and plans for its own size when resized
        without a host.

        A panel inside a `DockPanel` waits for `set_fit_space` instead: the host's trial placements resize it, and
        planning then would replace the base arrangement the host is measuring.
        """
        if event.type() == QEvent.Type.ParentChange:
            self._space = None
        handled = super().event(event)
        if event.type() == QEvent.Type.Resize and self._space is None and self._host() is None:
            self._plan_own_size()
        return handled
