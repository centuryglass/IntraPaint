"""Tests GridContainer's row and column counts in each fill mode."""
import sys

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QWidget

from src.ui.layout.grid_container import GridContainer
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

CELL_SIZE = 50


class _Cell(QWidget):
    """Fixed-size grid item with a matching size hint."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(CELL_SIZE, CELL_SIZE)

    def sizeHint(self) -> QSize:
        """Returns the fixed cell size."""
        return QSize(CELL_SIZE, CELL_SIZE)


class GridContainerTest(IntraPaintTestCase):
    """Fills a shown GridContainer with equal cells and resizes it."""

    def setUp(self) -> None:
        super().setUp()
        self.grid = GridContainer()
        self.grid.resize(300, 300)
        self.grid.show()
        self.cells: list[_Cell] = []

    def tearDown(self) -> None:
        self.grid.close()
        super().tearDown()

    def _add_cells(self, count: int) -> None:
        for _ in range(count):
            cell = _Cell()
            self.cells.append(cell)
            self.grid.add_widget(cell)

    def _grid_shape(self) -> tuple[int, int]:
        """Returns (rows, columns) as placed in the grid layout."""
        layout = self.grid.layout()
        rows = set()
        columns = set()
        for cell in self.cells:
            row, column, _, _ = layout.getItemPosition(layout.indexOf(cell))
            rows.add(row)
            columns.add(column)
        return len(rows), len(columns)

    def test_default_mode_picks_best_area_use(self) -> None:
        """Nine square cells in a square container form a 3x3 grid."""
        self._add_cells(9)
        self.assertEqual(self._grid_shape(), (3, 3))

    def test_cells_fill_in_row_order(self) -> None:
        """Items go left to right, then top to bottom."""
        self._add_cells(9)
        layout = self.grid.layout()
        positions = [layout.getItemPosition(layout.indexOf(cell))[:2] for cell in self.cells]
        self.assertEqual(positions, [(i // 3, i % 3) for i in range(9)])

    def test_fill_horizontal_column_count(self) -> None:
        """Columns fill the width, leaving a margin: 200px fits three 50px columns, 201px fits four."""
        self.grid.fill_horizontal = True
        self._add_cells(10)
        self.grid.resize(200, 300)
        self.assertEqual(self._grid_shape(), (4, 3))
        self.grid.resize(201, 300)
        self.assertEqual(self._grid_shape(), (3, 4))

    def test_fill_vertical_row_count(self) -> None:
        """Rows fill the height, and columns hold the rest."""
        self.grid.fill_vertical = True
        self._add_cells(10)
        self.grid.resize(300, 100)
        self.assertEqual(self._grid_shape(), (2, 5))

    def test_fill_vertical_grows_and_shrinks(self) -> None:
        """In fill_vertical mode the height sets the row count both ways."""
        self.grid.fill_vertical = True
        self._add_cells(10)
        self.grid.resize(300, 250)
        self.assertEqual(self._grid_shape(), (5, 2))
        self.grid.resize(300, 100)
        self.assertEqual(self.grid.height(), 100)
        self.assertEqual(self._grid_shape(), (2, 5))

    def test_fill_modes_are_exclusive(self) -> None:
        """Setting one fill mode clears the other."""
        self.grid.fill_horizontal = True
        self.grid.fill_vertical = True
        self.assertFalse(self.grid.fill_horizontal)
        self.grid.fill_horizontal = True
        self.assertFalse(self.grid.fill_vertical)

    def test_max_columns_limits_width(self) -> None:
        """A column limit pushes extra items into more rows."""
        self.grid.fill_horizontal = True
        self.grid.max_columns = 2
        self._add_cells(6)
        self.assertEqual(self._grid_shape(), (3, 2))

    def test_min_columns_limits_default_mode(self) -> None:
        """A column minimum rules out narrower grids that would use more area."""
        self.grid.min_columns = 4
        self._add_cells(9)
        self.assertEqual(self._grid_shape(), (3, 4))

    def test_space_overrides_min_columns(self) -> None:
        """Available width caps the column count even below the column minimum."""
        self.grid.fill_horizontal = True
        self.grid.min_columns = 3
        self._add_cells(6)
        self.grid.resize(60, 300)
        self.assertEqual(self._grid_shape(), (6, 1))

    def test_column_limits_are_checked_against_each_other(self) -> None:
        """A column maximum below the column minimum raises, and the row minimum doesn't affect it."""
        self.grid.min_rows = 3
        self.grid.max_columns = 2
        self.grid.max_columns = 5
        self.grid.min_columns = 3
        with self.assertRaises(ValueError):
            self.grid.max_columns = 2

    def test_remove_widget_reflows(self) -> None:
        """Removing items reflows the rest."""
        self._add_cells(9)
        removed = self.cells.pop()
        self.grid.remove_widget(removed)
        for _ in range(4):
            self.grid.remove_widget(self.cells.pop())
        self.assertEqual(self._grid_shape(), (2, 2))
        self.assertEqual(self.grid.layout().indexOf(removed), -1)
