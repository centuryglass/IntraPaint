"""Tests the pure column packer and the column widgets that hold packed sections."""
from PySide6.QtWidgets import QWidget

from src.ui.layout.column_packing import PackedColumns, pack_columns
from test.base_test_case import IntraPaintTestCase


class ColumnPackingTest(IntraPaintTestCase):
    """Tests `pack_columns` and `PackedColumns`."""

    def test_everything_fits_in_one_column(self) -> None:
        """Items whose heights and spacing fit the budget share a column."""
        self.assertEqual(pack_columns([10, 20, 30], 100, 5), [[0, 1, 2]])

    def test_each_item_gets_its_own_column(self) -> None:
        """Items that can't stack under each other fill a column apiece."""
        self.assertEqual(pack_columns([60, 60, 60], 100, 5), [[0], [1], [2]])

    def test_exact_fit_stacks(self) -> None:
        """A column exactly as tall as the budget keeps its last item."""
        self.assertEqual(pack_columns([40, 55], 100, 5), [[0, 1]])
        self.assertEqual(pack_columns([40, 56], 100, 5), [[0], [1]])

    def test_zero_budget_gives_every_item_a_column(self) -> None:
        """With no budget, as before the first plan, nothing stacks."""
        self.assertEqual(pack_columns([10, 20], 0, 5), [[0], [1]])

    def test_tall_item_starts_a_column_and_the_next_item_can_join_it(self) -> None:
        """An item taller than the budget stands alone, and later items fill what room it leaves."""
        self.assertEqual(pack_columns([150, 10, 10], 100, 5), [[0], [1, 2]])

    def test_new_column_resets_the_height(self) -> None:
        """Items after a break stack from the top of the new column."""
        self.assertEqual(pack_columns([50, 50, 50, 50], 105, 5), [[0, 1], [2, 3]])

    def test_alone_items_never_share(self) -> None:
        """An item in `alone` breaks the stack before and after it."""
        self.assertEqual(pack_columns([10, 10, 10, 10], 100, 5, alone={1}), [[0], [1], [2, 3]])
        self.assertEqual(pack_columns([10, 10], 100, 5, alone={0}), [[0], [1]])

    def test_no_items(self) -> None:
        """Nothing packs to no columns."""
        self.assertEqual(pack_columns([], 100, 5), [])

    def test_columns_keep_widgets_between_plans(self) -> None:
        """Re-planning moves the same widget objects between columns, shown."""
        parent = QWidget()
        widgets = [QWidget(parent) for _ in range(3)]
        packed = PackedColumns()
        columns: list[QWidget] = []
        packed.fill([(widgets[0], widgets[1]), (widgets[2],)], 4, columns.append)
        self.assertEqual(len(columns), 2)
        self.assertTrue(all(packed.holds(widget) for widget in widgets))
        columns = []
        packed.fill([tuple(widgets)], 4, columns.append)
        self.assertEqual(len(columns), 1)
        self.assertTrue(all(widget.parentWidget() is columns[0] and not widget.isHidden() for widget in widgets))
        self.assertTrue(packed.columns[1].isHidden())
        packed.release(widgets)
        self.assertEqual(packed.plan, [])
        self.assertEqual(columns[0].layout().count(), 1)
