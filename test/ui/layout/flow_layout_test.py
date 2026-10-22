"""Tests FlowLayout's ownership of the layout items Qt creates for its widgets."""
import sys

import shiboken6
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QWidgetItem

from src.ui.layout.flow_layout import FlowWidget
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


def _live_widget_items() -> int:
    return sum(1 for wrapper in shiboken6.getAllValidWrappers() if isinstance(wrapper, QWidgetItem))


class FlowLayoutTest(IntraPaintTestCase):
    """Tests FlowLayout item lifetimes."""

    def setUp(self) -> None:
        super().setUp()
        self.host = QWidget()
        self.flow = FlowWidget(self.host)
        self.buttons = [QPushButton(f'button {i}') for i in range(4)]
        for button in self.buttons:
            self.flow.flow.addWidget(button)

    def test_removed_widget_leaves_the_layout(self) -> None:
        """A widget unparented or deleted while the layout lives on loses its item."""
        self.buttons[0].setParent(None)
        shiboken6.delete(self.buttons[1])
        self.assertEqual(self.flow.flow.count(), 2)
        self.assertEqual([self.flow.flow.indexOf(button) for button in self.buttons[2:]], [0, 1])

    def test_deleting_the_layout_deletes_its_items(self) -> None:
        """Deleting the layout deletes the items it still holds, so their wrappers don't outlive them."""
        live_items = _live_widget_items()
        shiboken6.delete(self.host)
        self.assertEqual(_live_widget_items(), live_items - len(self.buttons))
