"""Tests how DraggableDivider drags move layout stretch between its neighbours."""
import sys
from typing import Optional

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QVBoxLayout, QBoxLayout

from src.ui.layout.draggable_divider import DraggableDivider
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

PARENT_LENGTH = 400


def _send_mouse(widget: QWidget, event_type: QEvent.Type, pos: QPoint,
                buttons: Optional[Qt.MouseButton] = None) -> None:
    if buttons is None:
        buttons = Qt.MouseButton.NoButton if event_type == QEvent.Type.MouseButtonRelease \
            else Qt.MouseButton.LeftButton
    event = QMouseEvent(event_type, QPointF(pos), QPointF(widget.mapToGlobal(pos)), Qt.MouseButton.LeftButton,
                        buttons, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(widget, event)


class DraggableDividerTest(IntraPaintTestCase):
    """Drags a divider placed between widgets in a shown box layout."""

    def setUp(self) -> None:
        super().setUp()
        self.parent = QWidget()
        self.parent.resize(PARENT_LENGTH, PARENT_LENGTH)
        self.items: list[QWidget] = []
        self.divider = DraggableDivider()

    def tearDown(self) -> None:
        self.parent.close()
        super().tearDown()

    def _build(self, stretches: list[int], divider_index: int, vertical: bool = False) -> QBoxLayout:
        """Lays out one plain widget per stretch value, with the divider inserted before divider_index."""
        layout: QBoxLayout = QVBoxLayout(self.parent) if vertical else QHBoxLayout(self.parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        for i, stretch in enumerate(stretches):
            if i == divider_index:
                layout.addWidget(self.divider)
            item = QWidget()
            self.items.append(item)
            layout.addWidget(item, stretch=stretch)
        self.parent.show()
        layout.activate()
        return layout

    def _stretches(self, layout: QBoxLayout) -> list[int]:
        return [layout.stretch(layout.indexOf(item)) for item in self.items]

    def _drag(self, offset: int, steps: int = 1) -> None:
        """Presses at the divider center and drags along its axis by offset, in steps."""
        horizontal = isinstance(self.divider.parent().layout(), QHBoxLayout)
        start = QPoint(self.divider.width() // 2, self.divider.height() // 2)
        _send_mouse(self.divider, QEvent.Type.MouseButtonPress, start)
        for step in range(1, steps + 1):
            delta = offset * step // steps
            pos = start + (QPoint(delta, 0) if horizontal else QPoint(0, delta))
            _send_mouse(self.divider, QEvent.Type.MouseMove, pos)
        _send_mouse(self.divider, QEvent.Type.MouseButtonRelease, pos)

    def test_orientation_follows_layout(self) -> None:
        """A divider in a vertical layout switches to vertical mode, with a matching size hint."""
        self._build([10, 10], 1, vertical=True)
        hint = self.divider.sizeHint()
        self.assertGreater(hint.width(), hint.height())

    def test_drag_right_moves_stretch_left(self) -> None:
        """Dragging a tenth of the parent's width moves a tenth of the total stretch to the item before."""
        layout = self._build([10, 10], 1)
        self._drag(PARENT_LENGTH // 10)
        self.assertEqual(self._stretches(layout), [12, 8])

    def test_drag_left_moves_stretch_right(self) -> None:
        """Dragging the other way grows the item after the divider."""
        layout = self._build([10, 10], 1)
        self._drag(-PARENT_LENGTH // 10)
        self.assertEqual(self._stretches(layout), [8, 12])

    def test_drag_down_in_vertical_layout(self) -> None:
        """Vertical dividers measure drags along the y-axis."""
        layout = self._build([10, 10], 1, vertical=True)
        self._drag(PARENT_LENGTH // 10)
        self.assertEqual(self._stretches(layout), [12, 8])

    def test_small_drags_accumulate(self) -> None:
        """Moves under one stretch unit change nothing alone, but count from the last change."""
        layout = self._build([10, 10], 1)
        self._drag(8, steps=1)
        self.assertEqual(self._stretches(layout), [10, 10])
        self._drag(40, steps=5)
        self.assertEqual(self._stretches(layout), [12, 8])

    def test_total_stretch_is_kept(self) -> None:
        """Repeated drags in both directions keep the stretch sum."""
        layout = self._build([5, 20, 15], 1)
        for offset in (100, -60, 30, -200):
            self._drag(offset)
            self.assertEqual(sum(self._stretches(layout)), 40)

    def test_stretch_never_drops_below_one(self) -> None:
        """A drag much longer than the item clamps the shrinking item at one."""
        layout = self._build([10, 10], 1)
        self._drag(PARENT_LENGTH)
        self.assertEqual(self._stretches(layout), [19, 1])
        self._drag(PARENT_LENGTH)
        self.assertEqual(self._stretches(layout), [19, 1])

    def test_far_items_shrink_when_near_item_is_at_minimum(self) -> None:
        """When the adjacent item can't shrink, stretch comes from the next item on that side."""
        layout = self._build([10, 1, 9], 1)
        self._drag(PARENT_LENGTH // 10)
        self.assertEqual(self._stretches(layout), [12, 1, 7])

    def test_item_at_minimum_size_does_not_shrink(self) -> None:
        """An item held at its minimum width gives up no stretch."""
        layout = self._build([10, 10], 1)
        self.items[1].setMinimumWidth(self.items[1].width())
        self._drag(PARENT_LENGTH // 10)
        self.assertEqual(self._stretches(layout), [10, 10])

    def test_item_at_maximum_size_does_not_grow(self) -> None:
        """An item held at its maximum width takes no stretch."""
        layout = self._build([10, 10], 1)
        self.items[0].setMaximumWidth(self.items[0].width())
        self._drag(PARENT_LENGTH // 10)
        self.assertEqual(self._stretches(layout), [10, 10])

    def test_item_at_maximum_height_does_not_grow(self) -> None:
        """In a vertical layout, an item held at its maximum height takes no stretch."""
        layout = self._build([10, 10], 1, vertical=True)
        self.items[0].setMaximumHeight(self.items[0].height())
        self._drag(PARENT_LENGTH // 10)
        self.assertEqual(self._stretches(layout), [10, 10])

    def test_divider_at_layout_edge_does_nothing(self) -> None:
        """A divider with no item on one side changes no stretch."""
        layout = self._build([10, 10], 0)
        self._drag(PARENT_LENGTH // 10)
        self.assertEqual(self._stretches(layout), [10, 10])

    def test_hidden_divider_ignores_drags(self) -> None:
        """set_hidden(True) turns off dragging."""
        layout = self._build([10, 10], 1)
        self.divider.set_hidden(True)
        self._drag(PARENT_LENGTH // 10)
        self.assertEqual(self._stretches(layout), [10, 10])

    def test_dragged_signal_reports_parent_position(self) -> None:
        """The dragged signal carries the cursor position in the parent's coordinates."""
        self._build([10, 10], 1)
        positions: list[QPoint] = []
        self.divider.dragged.connect(positions.append)
        self._drag(20)
        start_x = self.divider.x() + self.divider.width() // 2
        self.assertEqual(positions[-1].x(), start_x + 20)

    def test_move_without_press_does_nothing(self) -> None:
        """Mouse moves after release don't drag."""
        layout = self._build([10, 10], 1)
        _send_mouse(self.divider, QEvent.Type.MouseMove, QPoint(100, 0))
        self.assertEqual(self._stretches(layout), [10, 10])
