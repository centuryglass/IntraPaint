"""Tests src.util.layout.add_layout, and the PySide behavior it works around."""
import sys

from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.util.layout import add_layout
from test.base_test_case import IntraPaintTestCase, layout_item_wrapper_count

app = QApplication.instance() or QApplication(sys.argv)


class AddLayoutTest(IntraPaintTestCase):
    """Tests adding child layouts without wrapping their items."""

    def setUp(self) -> None:
        super().setUp()
        self.host = QWidget()
        self.outer = QVBoxLayout(self.host)

    def _fill(self, layout: QHBoxLayout) -> None:
        for _ in range(3):
            layout.addWidget(QLabel('label'))

    def test_filled_child_is_refused(self) -> None:
        """A child layout that already holds items raises ValueError when the parent has a widget, and isn't added."""
        row = QHBoxLayout()
        self._fill(row)
        with self.assertRaises(ValueError):
            add_layout(self.outer, row)
        self.assertEqual(self.outer.indexOf(row), -1)

    def test_filled_child_of_a_layout_without_a_widget_wraps_no_items(self) -> None:
        """A layout with no widget yet takes a filled child, and setting it on a widget wraps no items."""
        wrappers = layout_item_wrapper_count()
        column = QVBoxLayout()
        row = QHBoxLayout()
        self._fill(row)
        add_layout(column, row)
        self.assertEqual(layout_item_wrapper_count(), wrappers)
        body = QWidget(self.host)
        body.setLayout(column)
        self.assertEqual(column.indexOf(row), 0)
        self.assertEqual(layout_item_wrapper_count(), wrappers)

    def test_child_filled_after_adding_wraps_no_items(self) -> None:
        """A child layout added empty and filled afterwards leaves no item wrappers."""
        wrappers = layout_item_wrapper_count()
        row = QHBoxLayout()
        add_layout(self.outer, row, 1)
        self._fill(row)
        self.assertEqual(self.outer.indexOf(row), 0)
        self.assertEqual(self.outer.stretch(0), 1)
        self.assertEqual(layout_item_wrapper_count(), wrappers)

    def test_pyside_wraps_a_filled_childs_items(self) -> None:
        """PySide's addLayout wraps each item already in the child, which is why add_layout refuses filled children.

        PySide 6.12.0 stops wrapping them (PYSIDE-3469). If this fails after a PySide upgrade, `add_layout` can accept
        filled children.
        """
        wrappers = layout_item_wrapper_count()
        row = QHBoxLayout()
        self._fill(row)
        self.outer.addLayout(row)
        self.assertEqual(layout_item_wrapper_count(), wrappers + 3)
        for label in self.host.findChildren(QLabel):
            row.removeWidget(label)  # Invalidates each item's wrapper, so none outlives its item.
        self.assertEqual(layout_item_wrapper_count(), wrappers)
