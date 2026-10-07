"""Tests TabBox content display, border state and stretch hand-off when it opens and closes."""
import sys

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout

from src.ui.layout.bordered_widget import BorderedWidget
from src.ui.layout.draggable_tabs.tab import Tab
from src.ui.layout.draggable_tabs.tab_box import TabBox, INITIAL_STRETCH
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

PARENT_STRETCH_SUM = 100


def finish_open(box: TabBox) -> None:
    """Completes a pending open without waiting on the tab bar's open-delay timer."""
    box._tab_bar._finish_tab_open()  # pylint: disable=protected-access


class TabBoxTest(IntraPaintTestCase):
    """Places a horizontal TabBox above a stretched main widget, like MainWindow's top box."""

    def setUp(self) -> None:
        super().setUp()
        self.parent = QWidget()
        self.parent.resize(400, 400)
        self.layout = QVBoxLayout(self.parent)
        self.box = TabBox(Qt.Orientation.Horizontal, True)
        self.main = QWidget()
        self.layout.addWidget(self.box, stretch=1)
        self.layout.addWidget(self.main, stretch=PARENT_STRETCH_SUM)
        self.parent.show()

    def tearDown(self) -> None:
        self.box._tab_bar._tab_open_timer.stop()  # pylint: disable=protected-access
        self.parent.close()
        super().tearDown()

    def _stretches(self) -> tuple[int, int]:
        return self.layout.stretch(0), self.layout.stretch(1)

    @staticmethod
    def _tab(name: str) -> Tab:
        return Tab(name, QLabel(f'{name} content'))

    def test_open_box_shows_active_content(self) -> None:
        """An open box holds and shows its active tab's content widget."""
        tab = self._tab('tab')
        self.box.add_widget(tab)
        finish_open(self.box)
        self.assertTrue(self.box.is_open)
        self.assertIs(self.box.active_tab_content, tab.content_widget)
        self.assertIs(tab.content_widget.parentWidget(), self.box)
        self.assertFalse(tab.content_widget.isHidden())

    def test_closed_box_hides_content(self) -> None:
        """Closing hides the content widget, and the size hint shrinks to the tab bar's."""
        tab = self._tab('tab')
        self.box.add_widget(tab)
        finish_open(self.box)
        self.box.is_open = False
        self.assertTrue(tab.content_widget.isHidden())
        self.assertEqual(self.box.sizeHint(), self.box._tab_bar.sizeHint())  # pylint: disable=protected-access

    def test_switching_tabs_swaps_content(self) -> None:
        """Activating another tab replaces the displayed content widget."""
        first, second = self._tab('first'), self._tab('second')
        self.box.add_widget(first)
        self.box.add_widget(second)
        finish_open(self.box)
        second.clicked.emit(second)
        self.assertIs(self.box.active_tab_content, second.content_widget)
        self.assertTrue(first.content_widget.isHidden())
        self.assertFalse(second.content_widget.isHidden())

    def test_contains_and_remove(self) -> None:
        """contains_widget tracks add_widget and remove_widget."""
        tab = self._tab('tab')
        self.box.add_widget(tab)
        self.assertTrue(self.box.contains_widget(tab))
        self.assertEqual(self.box.count, 1)
        self.box.remove_widget(tab)
        self.assertFalse(self.box.contains_widget(tab))
        self.assertEqual(self.box.count, 0)

    def test_border_is_faded_only_while_empty(self) -> None:
        """An empty box draws a half-transparent border, and a box with tabs draws it opaque."""
        self.assertAlmostEqual(self.box.frame_color.alphaF(), 0.5, places=2)
        tab = self._tab('tab')
        self.box.add_widget(tab)
        self.assertEqual(self.box.frame_color.alphaF(), 1.0)
        self.box.remove_widget(tab)
        self.assertAlmostEqual(self.box.frame_color.alphaF(), 0.5, places=2)

    def test_minimum_active_size_includes_closed_content(self) -> None:
        """A closed box's minimum active size adds its content's minimum height to the bar's."""
        tab = self._tab('tab')
        tab.content_widget.setMinimumSize(QSize(50, 80))
        self.box.add_widget(tab)
        self.box.is_open = False
        self.assertGreaterEqual(self.box.minimum_active_size.height(), 80 + self.box.minimumSizeHint().height())

    def test_closing_gives_stretch_to_neighbours(self) -> None:
        """A box that closes keeps a stretch of one and gives the rest to stretched neighbours."""
        self.layout.setStretch(0, 20)
        self.layout.setStretch(1, 80)
        self.box.add_widget(self._tab('tab'))
        finish_open(self.box)
        self.box.is_open = False
        self.assertEqual(self._stretches(), (1, 99))

    def test_reopening_restores_stretch(self) -> None:
        """Reopening takes back the stretch the box had when it closed."""
        self.layout.setStretch(0, 20)
        self.layout.setStretch(1, 80)
        self.box.add_widget(self._tab('tab'))
        finish_open(self.box)
        self.box.is_open = False
        self.box.is_open = True
        finish_open(self.box)
        self.assertEqual(self._stretches(), (20, 80))

    def test_first_open_claims_initial_stretch(self) -> None:
        """A box that has never closed opens to the initial stretch, and repeated toggles keep it there."""
        self.box.add_widget(self._tab('tab'))
        finish_open(self.box)
        self.assertEqual(self._stretches(), (INITIAL_STRETCH, PARENT_STRETCH_SUM + 1 - INITIAL_STRETCH))
        for _ in range(3):
            self.box.is_open = False
            self.box.is_open = True
            finish_open(self.box)
        self.assertEqual(self._stretches(), (INITIAL_STRETCH, PARENT_STRETCH_SUM + 1 - INITIAL_STRETCH))

    def test_other_tab_boxes_keep_their_stretch(self) -> None:
        """Stretch hand-off skips other bordered widgets, so tab boxes never trade stretch with each other."""
        other = BorderedWidget()
        self.layout.addWidget(other, stretch=30)
        other.show()
        self.layout.setStretch(0, 20)
        self.layout.setStretch(1, 50)
        self.box.add_widget(self._tab('tab'))
        finish_open(self.box)
        self.box.is_open = False
        self.assertEqual(self.layout.stretch(2), 30)
        self.assertEqual(self._stretches(), (1, 69))

    def test_hidden_items_keep_their_stretch(self) -> None:
        """Stretch hand-off skips hidden items, so a hidden widget can't collect stretch it can't use."""
        hidden = QWidget()
        self.layout.addWidget(hidden, stretch=30)
        hidden.hide()
        self.layout.setStretch(0, 20)
        self.layout.setStretch(1, 50)
        self.box.add_widget(self._tab('tab'))
        finish_open(self.box)
        self.box.is_open = False
        self.assertEqual(self.layout.stretch(2), 30)
        self.assertEqual(self._stretches(), (1, 69))
