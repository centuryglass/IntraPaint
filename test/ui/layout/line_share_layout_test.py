"""Tests sharing spare lines between stacked text boxes."""
import sys

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QWidget

from src.ui.layout.line_share_layout import LineShareLayout, share_lines
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

LINE = 10


class ShareLinesTest(IntraPaintTestCase):
    """Tests `share_lines`."""

    def test_shares_follow_the_weights_within_a_line(self) -> None:
        """Every count of lines splits two to one, as closely as whole lines allow."""
        for lines in range(30):
            with self.subTest(lines=lines):
                first, second = share_lines(lines, [100, 100], [2, 1])
                self.assertEqual(first + second, lines)
                self.assertLessEqual(abs(first - 2 * lines / 3), 1)

    def test_shares_never_drop_as_lines_grow(self) -> None:
        """One more line never takes a line from either item."""
        previous = [0, 0]
        for lines in range(40):
            shares = share_lines(lines, [16, 8], [2, 1])
            self.assertTrue(all(share >= old for share, old in zip(shares, previous)), (lines, shares))
            previous = shares

    def test_a_capped_item_passes_its_lines_on(self) -> None:
        """Lines past an item's capacity go to the others, and lines past every capacity are left out."""
        self.assertEqual(share_lines(12, [2, 100], [2, 1]), [2, 10])
        self.assertEqual(share_lines(50, [16, 8], [2, 1]), [16, 8])

    def test_unweighted_items_take_no_lines(self) -> None:
        """An item with no weight keeps its minimum."""
        self.assertEqual(share_lines(6, [10, 10], [1, 0]), [6, 0])


class LineShareLayoutTest(IntraPaintTestCase):
    """Tests `LineShareLayout` geometry."""

    def setUp(self) -> None:
        super().setUp()
        self.host = QWidget()
        self.layout = LineShareLayout(lambda: LINE, self.host, spacing=4)
        self.first = QWidget()
        self.first.setMinimumHeight(40)
        self.first.setMaximumHeight(200)
        self.second = QWidget()
        self.second.setMinimumHeight(20)
        self.second.setMaximumHeight(100)
        self.layout.add_widget(self.first, 2)
        self.layout.add_widget(self.second, 1)

    def test_preferred_height_is_the_minimum_height(self) -> None:
        """The layout never asks for more than its minimum, so spare height alone sizes its items."""
        self.assertEqual(self.layout.minimumSize().height(), 64)
        self.assertEqual(self.layout.sizeHint().height(), 64)
        self.assertEqual(self.layout.maximumSize().height(), 304)

    def test_spare_height_goes_out_in_whole_lines(self) -> None:
        """Items grow by whole lines, two to one, directly under each other, and the part of a line left over stays
        below the last item."""
        self.layout.setGeometry(QRect(0, 0, 100, 64 + 3 * LINE + 7))
        self.assertEqual((self.first.height(), self.second.height()), (60, 30))
        self.assertEqual(self.second.y(), self.first.geometry().bottom() + 1 + 4)

    def test_items_stop_at_their_maximum_heights(self) -> None:
        """Height past every item's maximum stays below the last item."""
        self.layout.setGeometry(QRect(0, 0, 100, 1000))
        self.assertEqual((self.first.height(), self.second.height()), (200, 100))
        self.assertEqual(self.second.y(), 204)

    def test_hidden_items_take_no_room(self) -> None:
        """A hidden item adds no height or spacing, and the shown one takes every spare line."""
        self.second.hide()
        self.assertEqual(self.layout.minimumSize().height(), 40)
        self.layout.setGeometry(QRect(0, 0, 100, 75))
        self.assertEqual(self.first.height(), 70)
