"""Tests the pure column packer, the column widgets that hold packed sections, and the packer panels use."""
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from src.ui.layout.column_packing import PackedColumns, SectionPacker, pack_columns
from src.ui.widget.panel_section import PanelSection
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


class _PackingOwner(QWidget):
    """A strip of three sections that packs them within `budget`, and counts the plans a toggle asks for."""

    def __init__(self, budget: int) -> None:
        super().__init__()
        self.budget = budget
        self.replans = 0
        self.row = QHBoxLayout(self)
        self.sections = [PanelSection(title, QLabel(title)) for title in ('First', 'Second', 'Third')]
        self.packer = SectionPacker(self.column_budget, self.replan)
        for section in self.sections:
            self.row.addWidget(section)
            self.packer.watch(section)

    def column_budget(self) -> int:
        """Returns the height a column has."""
        return self.budget

    def replan(self) -> None:
        """Counts a plan the packer asked for."""
        self.replans += 1

    def pack(self) -> bool:
        """Packs the sections into the row."""
        def _clear() -> None:
            for column in self.packer.columns:
                self.row.removeWidget(column)
        return self.packer.pack(self.sections, 4, self.row.addWidget, _clear)


class SectionPackerTest(IntraPaintTestCase):
    """Tests `SectionPacker`."""

    def test_budget_decides_the_columns(self) -> None:
        """Sections stack within the budget, and a zero budget gives each its own column."""
        owner = _PackingOwner(10000)
        self.assertTrue(owner.pack())
        self.assertEqual(owner.packer.plan, [tuple(owner.sections)])
        owner.budget = 0
        self.assertTrue(owner.pack())
        self.assertEqual(owner.packer.plan, [(section,) for section in owner.sections])

    def test_unchanged_plan_leaves_the_columns(self) -> None:
        """Packing again with the same plan changes nothing, until `invalidate`."""
        owner = _PackingOwner(10000)
        owner.pack()
        self.assertFalse(owner.pack())
        owner.packer.invalidate()
        self.assertTrue(owner.pack())

    def test_base_measurement_gives_every_section_a_column(self) -> None:
        """Inside `base_measurement` the budget is zero, whatever the owner's is."""
        owner = _PackingOwner(10000)
        with owner.packer.base_measurement():
            self.assertEqual(owner.packer.budget(), 0)
            owner.pack()
        self.assertEqual(len(owner.packer.plan), 3)
        self.assertEqual(owner.packer.budget(), 10000)

    def test_hidden_sections_take_no_column(self) -> None:
        """A hidden section is left out of the plan."""
        owner = _PackingOwner(0)
        owner.sections[1].hide()
        owner.pack()
        self.assertEqual(owner.packer.plan, [(owner.sections[0],), (owner.sections[2],)])

    def test_toggle_replans_whether_or_not_packing(self) -> None:
        """Opening or closing a section asks for a plan before packing, while packing and after `release`, since a
        side panel's plan also depends on the sections' heights."""
        owner = _PackingOwner(10000)
        owner.sections[0].set_expanded(False)
        self.assertEqual(owner.replans, 1)
        owner.pack()
        owner.sections[0].set_expanded(True)
        self.assertEqual(owner.replans, 2)
        released = owner.packer.release()
        self.assertEqual(released, owner.sections)
        self.assertFalse(owner.packer.packing)
        owner.sections[0].set_expanded(False)
        self.assertEqual(owner.replans, 3)
