"""Tests ReflowingButtonGroup's switch between a row and a column."""
import sys

from PySide6.QtWidgets import QApplication, QPushButton

from src.ui.layout.reflowing_button_group import ReflowingButtonGroup
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class ReflowingButtonGroupTest(IntraPaintTestCase):
    """Resizes a group of three buttons across the width they need in one row."""

    def setUp(self) -> None:
        super().setUp()
        self.group = ReflowingButtonGroup()
        self.buttons = [QPushButton(text) for text in ('Clear', 'Select All', 'Clear Context Pins')]
        for button in self.buttons:
            self.group.add_button(button)
        self.group.show()

    def tearDown(self) -> None:
        self.group.close()
        super().tearDown()

    def test_row_when_buttons_fit(self) -> None:
        """At or above the row width, the buttons share one row."""
        self.group.resize(self.group.row_width(), 200)
        self.assertTrue(self.group.is_row)

    def test_column_when_buttons_do_not_fit(self) -> None:
        """One pixel short of the row width, the buttons stack."""
        self.group.resize(self.group.row_width() - 1, 200)
        self.assertFalse(self.group.is_row)

    def test_minimum_width_allows_column(self) -> None:
        """The minimum width is narrower than the row, so a parent layout can shrink the group into a column."""
        self.assertLess(self.group.minimumSizeHint().width(), self.group.row_width())

    def test_hiding_a_button_rechecks_layout(self) -> None:
        """Hiding a button narrows the row, so a group too narrow for three buttons can fit two in a row."""
        two_button_width = self.group.row_width() - self.buttons[2].sizeHint().width() - 10
        self.group.resize(two_button_width, 200)
        self.assertFalse(self.group.is_row)
        self.buttons[2].hide()
        self.assertTrue(self.group.is_row)
        self.buttons[2].show()
        self.assertFalse(self.group.is_row)
