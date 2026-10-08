"""Tests TabBar's tab list, active tab, open state, tab bar widgets and moves between bars."""
import sys
from unittest.mock import Mock

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication, QWidget, QLabel

from src.ui.layout.draggable_tabs.tab import Tab
from src.ui.layout.draggable_tabs.tab_bar import TabBar
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


def finish_open(bar: TabBar) -> None:
    """Completes a pending open without waiting on the open-delay timer."""
    bar._finish_tab_open()  # pylint: disable=protected-access


def drag_event(source: QWidget, position: QPointF) -> Mock:
    """Returns a stand-in for the drag and drop events TabBar reads, carrying a source widget and position."""
    event = Mock()
    event.source.return_value = source
    event.position.return_value = position
    return event


class TabBarTest(IntraPaintTestCase):
    """Builds tabs with content widgets on shown horizontal tab bars."""

    def setUp(self) -> None:
        super().setUp()
        self.bar = TabBar(Qt.Orientation.Horizontal, True)
        self.other_bar = TabBar(Qt.Orientation.Horizontal, True)
        for bar in (self.bar, self.other_bar):
            bar.resize(600, 40)
            bar.show()

    def tearDown(self) -> None:
        for bar in (self.bar, self.other_bar):
            # pylint: disable-next=protected-access
            bar._tab_open_timer.stop()
            bar.close()
        super().tearDown()

    @staticmethod
    def _tab(name: str, widget_count: int = 0) -> Tab:
        tab = Tab(name, QLabel(f'{name} content'))
        for i in range(widget_count):
            tab.add_tab_bar_widget(QLabel(f'{name} widget {i}'))
        return tab

    def test_first_tab_becomes_active_and_starts_opening(self) -> None:
        """The first tab added becomes active, and the bar opens once the open delay passes."""
        will_open = Mock()
        toggled = Mock()
        self.bar.tab_bar_will_open.connect(will_open)
        self.bar.toggled.connect(toggled)
        first = self._tab('first')
        self.bar.add_tab(first)
        self.assertIs(self.bar.active_tab, first)
        will_open.assert_called_once()
        self.assertFalse(self.bar.is_open)
        finish_open(self.bar)
        self.assertTrue(self.bar.is_open)
        toggled.assert_called_once_with(True)

    def test_later_tabs_do_not_change_active_tab(self) -> None:
        """Adding more tabs leaves the first one active."""
        first, second = self._tab('first'), self._tab('second')
        self.bar.add_tab(first)
        self.bar.add_tab(second)
        self.assertEqual(self.bar.tabs, [first, second])
        self.assertIs(self.bar.active_tab, first)

    def test_empty_bar_cannot_open(self) -> None:
        """is_open stays False without an active tab."""
        self.bar.is_open = True
        self.assertFalse(self.bar.is_open)

    def test_activating_a_foreign_tab_raises(self) -> None:
        """Only tabs on the bar can be active."""
        with self.assertRaises(ValueError):
            self.bar.active_tab = self._tab('stray')

    def test_add_tab_at_index(self) -> None:
        """add_tab inserts at the given index."""
        tabs = [self._tab(name) for name in ('a', 'b', 'c')]
        for tab in tabs:
            self.bar.add_tab(tab)
        inserted = self._tab('inserted')
        self.bar.add_tab(inserted, 1)
        self.assertEqual(self.bar.tabs, [tabs[0], inserted, tabs[1], tabs[2]])

    def test_move_widget_index_is_insert_before(self) -> None:
        """move_widget's index names the slot before which the tab lands, counted before removal."""
        a, b, c = (self._tab(name) for name in ('a', 'b', 'c'))
        for tab in (a, b, c):
            self.bar.add_tab(tab)
        self.bar.move_widget(a, 2)
        self.assertEqual(self.bar.tabs, [b, a, c])
        self.bar.move_widget(a, 3)
        self.assertEqual(self.bar.tabs, [b, c, a])
        self.bar.move_widget(a, 0)
        self.assertEqual(self.bar.tabs, [a, b, c])

    def test_layout_order_follows_tab_order(self) -> None:
        """Moving a tab moves it in the bar's layout too."""
        a, b, c = (self._tab(name) for name in ('a', 'b', 'c'))
        for tab in (a, b, c):
            self.bar.add_tab(tab)
        self.bar.move_widget(c, 0)
        layout = self.bar.layout()
        indices = [layout.indexOf(tab) for tab in (c, a, b)]
        self.assertEqual(indices, sorted(indices))

    def test_tab_moves_between_bars(self) -> None:
        """Adding a tab to another bar removes it from the first, along with its tab bar widgets."""
        removed = Mock()
        added = Mock()
        self.bar.tab_removed.connect(removed)
        self.other_bar.tab_added.connect(added)
        first, moving = self._tab('first'), self._tab('moving', widget_count=2)
        self.bar.add_tab(first)
        self.bar.add_tab(moving)
        self.other_bar.add_tab(moving)
        self.assertEqual(self.bar.tabs, [first])
        self.assertEqual(self.other_bar.tabs, [moving])
        removed.assert_called_once_with(moving)
        added.assert_called_once_with(moving)
        for widget in moving.tab_bar_widgets:
            self.assertIs(widget.parent(), self.other_bar)

    def test_moving_the_active_tab_away_activates_the_next(self) -> None:
        """When the active tab leaves, the first remaining tab becomes active and the bar closes."""
        first, second = self._tab('first'), self._tab('second')
        self.bar.add_tab(first)
        self.bar.add_tab(second)
        finish_open(self.bar)
        self.other_bar.add_tab(first)
        self.assertIs(self.bar.active_tab, second)
        self.assertFalse(self.bar.is_open)
        self.assertIs(self.other_bar.active_tab, first)

    def test_removing_the_last_tab_clears_active_tab(self) -> None:
        """An emptied bar has no active tab."""
        tab = self._tab('only')
        self.bar.add_tab(tab)
        self.bar.remove_tab(tab)
        self.assertIsNone(self.bar.active_tab)
        self.assertEqual(self.bar.tabs, [])
        self.assertIsNone(tab.parent())

    def test_active_tab_widgets_hide_while_open(self) -> None:
        """An open bar hides its active tab's tab bar widgets and shows every other tab's."""
        active, other = self._tab('active', widget_count=1), self._tab('other', widget_count=1)
        self.bar.add_tab(active)
        self.bar.add_tab(other)
        finish_open(self.bar)
        self.assertTrue(active.tab_bar_widgets[0].isHidden())
        self.assertFalse(other.tab_bar_widgets[0].isHidden())
        self.bar.active_tab = other
        self.assertFalse(active.tab_bar_widgets[0].isHidden())
        self.assertTrue(other.tab_bar_widgets[0].isHidden())
        self.bar.is_open = False
        self.assertFalse(other.tab_bar_widgets[0].isHidden())

    def test_tab_bar_widgets_follow_tab_order(self) -> None:
        """Tab bar widgets sit after the spacer, grouped in tab order."""
        a, b = self._tab('a', widget_count=2), self._tab('b', widget_count=1)
        self.bar.add_tab(a)
        self.bar.add_tab(b)
        self.bar.move_widget(b, 0)
        layout = self.bar.layout()
        indices = [layout.indexOf(widget) for widget in b.tab_bar_widgets + a.tab_bar_widgets]
        self.assertEqual(indices, sorted(indices))
        self.assertGreater(indices[0], max(layout.indexOf(tab) for tab in (a, b)))

    def test_widget_added_to_tab_later_joins_bar(self) -> None:
        """Tab bar widgets added after the tab joins a bar appear on that bar, and leave when removed."""
        tab = self._tab('tab')
        self.bar.add_tab(tab)
        widget = QLabel('late')
        tab.add_tab_bar_widget(widget)
        self.assertIs(widget.parent(), self.bar)
        tab.remove_tab_bar_widget(widget)
        self.assertIsNone(widget.parent())

    def test_click_activates_tab(self) -> None:
        """A tab's clicked signal makes it active."""
        first, second = self._tab('first'), self._tab('second')
        self.bar.add_tab(first)
        self.bar.add_tab(second)
        second.clicked.emit(second)
        self.assertIs(self.bar.active_tab, second)

    def test_double_click_toggles_active_tab(self) -> None:
        """Double-clicking the active tab closes an open bar, and double-clicking it again starts opening it."""
        tab = self._tab('tab')
        self.bar.add_tab(tab)
        finish_open(self.bar)
        tab.double_clicked.emit(tab)
        self.assertFalse(self.bar.is_open)
        will_open = Mock()
        self.bar.tab_bar_will_open.connect(will_open)
        tab.double_clicked.emit(tab)
        will_open.assert_called_once()

    def test_content_replacement_is_forwarded_for_active_tab_only(self) -> None:
        """Replacing the active tab's content emits active_tab_content_replaced; other tabs don't."""
        active, other = self._tab('active'), self._tab('other')
        self.bar.add_tab(active)
        self.bar.add_tab(other)
        replaced = Mock()
        self.bar.active_tab_content_replaced.connect(replaced)
        other.content_widget = QLabel('other new')
        replaced.assert_not_called()
        new_content = QLabel('active new')
        active.content_widget = new_content
        replaced.assert_called_once_with(new_content)

    def test_orientation_change_reaches_tabs(self) -> None:
        """set_orientation passes the new orientation to every tab."""
        tab = self._tab('tab')
        self.bar.add_tab(tab)
        self.bar.set_orientation(Qt.Orientation.Vertical)
        self.assertEqual(tab.orientation, Qt.Orientation.Vertical)
        self.assertEqual(self.bar.layout().indexOf(tab), 1)

    def test_drop_tab_from_another_bar(self) -> None:
        """Dropping a tab past the end of a bar's tabs appends it there."""
        a, b = self._tab('a'), self._tab('b')
        self.bar.add_tab(a)
        self.bar.add_tab(b)
        moving = self._tab('moving')
        self.other_bar.add_tab(moving)
        self.bar.layout().activate()
        drop_pos = QPointF(b.geometry().right() + 1, b.geometry().center().y())
        self.bar.dragEnterEvent(drag_event(moving, drop_pos))
        self.bar.dropEvent(drag_event(moving, drop_pos))
        self.assertEqual(self.bar.tabs, [a, b, moving])
        self.assertEqual(self.other_bar.tabs, [])

    def test_drop_before_first_tab(self) -> None:
        """Dropping a tab left of the first tab's midpoint inserts it first."""
        a, b = self._tab('a'), self._tab('b')
        self.bar.add_tab(a)
        self.bar.add_tab(b)
        self.bar.layout().activate()
        drop_pos = QPointF(a.geometry().left() + 1, a.geometry().center().y())
        self.bar.dragEnterEvent(drag_event(b, drop_pos))
        self.bar.dropEvent(drag_event(b, drop_pos))
        self.assertEqual(self.bar.tabs, [b, a])

    def test_drag_leave_cancels_drop(self) -> None:
        """A drop after the drag left the bar changes nothing."""
        a = self._tab('a')
        self.bar.add_tab(a)
        moving = self._tab('moving')
        self.other_bar.add_tab(moving)
        self.bar.dragEnterEvent(drag_event(moving, QPointF(0, 0)))
        self.bar.dragLeaveEvent(None)
        self.bar.dropEvent(drag_event(moving, QPointF(0, 0)))
        self.assertEqual(self.other_bar.tabs, [moving])
