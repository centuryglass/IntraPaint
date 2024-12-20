"""Arrange equal-sized widgets in a grid with dimensions that adjust based on available space."""
import logging
import math
from typing import Optional

from PySide6.QtCore import QSize, Qt, QRect
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QWidget, QGridLayout

from src.util.visual.geometry_utils import get_scaled_placement
from src.util.math_utils import clamp

DEFAULT_MAX = 999
logger = logging.getLogger(__name__)


class GridContainer(QWidget):
    """Arrange equal-sized widgets in a grid with dimensions that adjust based on available space."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._children: list[QWidget] = []
        self._layout = QGridLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._max_rows = DEFAULT_MAX
        self._max_columns = DEFAULT_MAX
        self._min_rows = 1
        self._min_columns = 1
        self._rows = DEFAULT_MAX
        self._columns = DEFAULT_MAX
        self._fill_horizontal = False
        self._fill_vertical = False

    def add_widget(self, child: QWidget) -> None:
        """Add a child widget to the container."""
        if len(self._children) > 0:
            assert child.sizeHint() == self._children[0].sizeHint(), 'All widgets should have equal size hints.'
        self._children.append(child)
        self._update_grid_flow()

    def remove_widget(self, child: QWidget) -> None:
        """Remove a child widget from the container"""
        if child not in self._children:
            return
        self._children.remove(child)
        self._layout.removeWidget(child)
        self._update_grid_flow()

    @property
    def fill_horizontal(self) -> bool:
        """Whether grid items should be arranged to fill horizontal space. If set, disables fill_vertical."""
        return self._fill_horizontal

    @fill_horizontal.setter
    def fill_horizontal(self, should_fill: bool) -> None:
        if should_fill != self._fill_horizontal:
            self._fill_horizontal = should_fill
            if should_fill:
                self._fill_vertical = False
            self._update_grid_flow()

    @property
    def fill_vertical(self) -> bool:
        """Whether grid items should be arranged to fill vertical space. If set, disables fill_horizontal."""
        return self._fill_vertical

    @fill_vertical.setter
    def fill_vertical(self, should_fill: bool) -> None:
        if should_fill != self._fill_vertical:
            self._fill_vertical = should_fill
            if should_fill:
                self._fill_horizontal = False
            self._update_grid_flow()

    @property
    def max_rows(self) -> int:
        """Access the maximum permitted row count."""
        return self._max_rows

    @max_rows.setter
    def max_rows(self, new_max: int) -> None:
        self._max_rows = max(new_max, 1)
        if self._max_rows < self._min_rows:
            raise ValueError(f'new max {new_max} is less than minimum {self._min_rows}')
        self._update_grid_flow()

    @property
    def min_rows(self) -> int:
        """Access the minimum permitted row count."""
        return self._min_rows

    @min_rows.setter
    def min_rows(self, new_min: int) -> None:
        self._min_rows = max(new_min, 1)
        if self._max_rows < self._min_rows:
            raise ValueError(f'new min {new_min} is less than maximum {self._max_rows}')
        self._update_grid_flow()

    @property
    def max_columns(self) -> int:
        """Access the maximum permitted column count."""
        return self._max_columns

    @max_columns.setter
    def max_columns(self, new_max: int) -> None:
        self._max_columns = max(new_max, 1)
        if self._max_columns < self._min_rows:
            raise ValueError(f'new max {new_max} is less than minimum {self._min_columns}')
        self._update_grid_flow()

    @property
    def min_columns(self) -> int:
        """Access the minimum permitted column count."""
        return self._min_columns

    @min_columns.setter
    def min_columns(self, new_min: int) -> None:
        self._min_columns = max(new_min, 1)
        if self._max_columns < self._min_columns:
            raise ValueError(f'new min {new_min} is less than maximum {self._max_columns}')
        self._update_grid_flow()

    def actual_content_size(self) -> QSize:
        """Get the size taken by all grid items in their current arrangement."""
        if len(self._children) == 0:
            return QSize(0, 0)
        base_size = self._children[-1].sizeHint()
        actual_size = self._children[-1].size()
        if actual_size.width() > base_size.width():
            base_size.setWidth(actual_size.width())
        if actual_size.height() > base_size.height():
            base_size.setHeight(actual_size.height())
        base_size = base_size + QSize(self._layout.spacing(), self._layout.spacing())
        content_size = QSize(base_size.width() * self._columns, base_size.height() * self._rows)
        return content_size

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Update grid flow on resize."""
        self._update_grid_flow()

    def sizeHint(self) -> QSize:
        """Return a null sizeHint so the grid adapts to available space as needed."""
        return QSize()

    def _get_constrained_grid_bounds(self, ignore_bounds=False) -> tuple[int, int, int, int]:
        # Rows/column count must be within range, can't be less than 1:
        min_cols, max_cols, min_rows, max_rows = (max(edge, 1) for edge in (self._min_columns, self._max_columns,
                                                                            self._min_rows, self._max_rows))
        if len(self._children) > 0:
            if not ignore_bounds:
                width = self.width()
                height = self.height()
                child_width = self._children[-1].sizeHint().width()
                child_height = self._children[-1].sizeHint().height()

                # counts can't exceed the bounds:
                max_cols, max_rows = (min(edge, dim // max(c_dim, 1)) for edge, dim, c_dim
                                      in ((max_cols, width, child_width), (max_rows, height, child_height)))
            # dimensions shouldn't exceed the total number of items:
            max_cols, max_rows = (int(clamp(edge, 1, len(self._children))) for edge in (max_cols, max_rows))

        # minimums can't exceed maximums:
        min_cols, min_rows = (min(edge_min, edge_max) for edge_min, edge_max in ((min_cols, max_cols),
                                                                                 (min_rows, max_rows)))
        return min_cols, max_cols, min_rows, max_rows

    def _update_grid_flow(self) -> None:
        """Arrange grid items to fill the container as effectively as possible."""
        if len(self._children) == 0 or self.size().isEmpty():
            return
        min_cols, max_cols, min_rows, max_rows = self._get_constrained_grid_bounds()
        column_count = -1

        if self._fill_vertical:
            row_count = max(self.height() // self._children[-1].sizeHint().height(), 1)
            column_count = int(clamp(math.ceil(len(self._children) / row_count), min_cols, max_cols))
        elif self._fill_horizontal:
            child_width = max(self._children[-1].sizeHint().width(), self._children[-1].width())
            column_count = int(clamp(self.width() // max(1, child_width), min_cols, max_cols))
            while (child_width * column_count) >= self.width() and column_count > min_cols:
                column_count -= 1
        else:
            full_area = self.width() * self.height()
            best_fraction = 0.0
            for test_column_count in range(min_cols, max_cols + 1):
                row_count = math.ceil(len(self._children) / test_column_count)
                if not min_rows <= row_count <= max_rows:
                    continue
                child_bounds = QRect(0, 0, self.width() // test_column_count, self.height() // row_count)
                exact_child_bounds = get_scaled_placement(child_bounds, self._children[-1].size(), 0)
                child_area = exact_child_bounds.width() * exact_child_bounds.height() * len(self._children)
                fraction_used = child_area / full_area
                if fraction_used > best_fraction:
                    best_fraction = fraction_used
                    column_count = test_column_count
        if column_count < 0:
            logger.error(f'{self._min_columns}-{self._max_columns} columns and {self._min_rows}-{self._max_rows} cannot'
                         f' fit {len(self._children)} with size {self._children[-1].sizeHint()} within {self.size()}')
            column_count = min_cols

        row_count = math.ceil(len(self._children) / column_count)
        for i, child in enumerate(self._children):
            row = i // column_count
            col = i % column_count
            self._layout.addWidget(child, row, col)
        self._rows = row_count
        self._columns = column_count
        content_height = (self._children[-1].sizeHint().height() + self._layout.spacing() * 2) * row_count
        self.setMinimumHeight(content_height)
        self.update()
