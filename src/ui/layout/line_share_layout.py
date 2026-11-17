"""A vertical stack of text boxes that share spare height in whole text lines, by weight.

Each item starts at its minimum height. Spare height goes to the items in whole lines of `line_height`, split by weight
and capped by each item's maximum height, so a text box sized to whole lines keeps showing whole lines. Height left
over after that, under one line or past every item's maximum, stays below the last item.

An item's minimum and maximum heights are its widget's, so a widget whose maximum equals its minimum, such as a
collapsed section, holds its height. The layout's preferred height is its minimum height, so what the boxes hold never
changes how tall they are.
"""
from functools import partial
from typing import Callable, Optional, Sequence

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QWidget, QWidgetItem
from shiboken6 import delete, isValid

QWIDGETSIZE_MAX = 16777215


def share_lines(lines: int, capacities: Sequence[int], weights: Sequence[int]) -> list[int]:
    """Splits `lines` among items by weight, giving no item more than its capacity, and returns each item's share.

    Lines go out one at a time by the Sainte-Lague method, so shares stay within a line of the weights and an item's
    share never drops when `lines` grows. A tie goes to the earlier item. Lines beyond every item's capacity are left
    out.
    """
    shares = [0] * len(capacities)
    for _ in range(lines):
        open_items = [index for index, capacity in enumerate(capacities) if shares[index] < capacity
                      and weights[index] > 0]
        if len(open_items) == 0:
            break
        index = max(open_items, key=lambda i: (weights[i] / (2 * shares[i] + 1), -i))
        shares[index] += 1
    return shares


def _delete_items(items: list[QLayoutItem], *_) -> None:
    """Deletes a destroyed layout's items, which QLayout's destructor leaves to the subclass."""
    for item in items:
        if isValid(item):
            delete(item)
    items.clear()


class LineShareLayout(QLayout):
    """Stacks widgets top to bottom and shares spare height among them in whole lines, by weight.

    `line_height` returns the height of one line. It is called on every layout pass, so it can follow a font.
    """

    def __init__(self, line_height: Callable[[], int], parent: Optional[QWidget] = None, spacing: int = 0) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._weights: list[int] = []
        self._line_height = line_height
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)
        # The callback holds the item list, not the layout, so it doesn't keep the layout alive:
        self.destroyed.connect(partial(_delete_items, self._items))

    def add_widget(self, widget: QWidget, weight: int) -> None:
        """Adds a widget below the others. Spare lines go to widgets in proportion to their weights."""
        self.addChildWidget(widget)
        self._items.append(QWidgetItem(widget))
        self._weights.append(weight)
        self.invalidate()

    def addItem(self, item: QLayoutItem) -> None:  # pylint: disable=invalid-name
        """Adds a layout item below the others, which never takes spare lines."""
        self._items.append(item)
        self._weights.append(0)

    def count(self) -> int:
        """Returns the number of items."""
        return len(self._items)

    def itemAt(self, index: int) -> Optional[QLayoutItem]:  # pylint: disable=invalid-name
        """Returns the item at an index, or None."""
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> Optional[QLayoutItem]:  # pylint: disable=invalid-name
        """Removes and returns the item at an index, or None."""
        if 0 <= index < len(self._items):
            del self._weights[index]
            return self._items.pop(index)
        return None

    def spacing(self) -> int:
        """Returns the space between items."""
        return self._spacing

    def setSpacing(self, spacing: int) -> None:  # pylint: disable=invalid-name
        """Sets the space between items."""
        self._spacing = spacing
        self.invalidate()

    def expandingDirections(self) -> Qt.Orientation:  # pylint: disable=invalid-name
        """Grows vertically while any item can take another line."""
        return Qt.Orientation.Vertical if any(capacity > 0 for capacity in self._capacities()) \
            else Qt.Orientation(0)

    def _shown(self) -> list[tuple[QLayoutItem, int]]:
        return [(item, weight) for item, weight in zip(self._items, self._weights) if not item.isEmpty()]

    def _capacities(self) -> list[int]:
        """Returns how many spare lines each shown item can take."""
        line = max(self._line_height(), 1)
        return [max((min(item.maximumSize().height(), QWIDGETSIZE_MAX) - item.minimumSize().height()) // line, 0)
                if weight > 0 else 0 for item, weight in self._shown()]

    def _stacked(self, heights: list[int]) -> int:
        margins = self.contentsMargins()
        return sum(heights) + self._spacing * max(len(heights) - 1, 0) + margins.top() + margins.bottom()

    def _width(self, sizes: list[QSize]) -> int:
        margins = self.contentsMargins()
        return max((size.width() for size in sizes), default=0) + margins.left() + margins.right()

    def minimumSize(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the widest item's minimum width over the stacked minimum heights."""
        sizes = [item.minimumSize() for item, _ in self._shown()]
        return QSize(self._width(sizes), self._stacked([size.height() for size in sizes]))

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the widest item's preferred width over the stacked minimum heights."""
        shown = self._shown()
        width = self._width([item.sizeHint().expandedTo(item.minimumSize()) for item, _ in shown])
        return QSize(width, self._stacked([item.minimumSize().height() for item, _ in shown]))

    def maximumSize(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the stacked minimum heights plus every line the items can take, at any width."""
        shown = self._shown()
        line = max(self._line_height(), 1)
        height = self._stacked([item.minimumSize().height() for item, _ in shown]) + line * sum(self._capacities())
        return QSize(QWIDGETSIZE_MAX, height)

    def item_heights(self, height: int) -> list[int]:
        """Returns each shown item's height within a layout of `height`."""
        shown = self._shown()
        minimums = [item.minimumSize().height() for item, _ in shown]
        line = max(self._line_height(), 1)
        spare_lines = max(height - self._stacked(minimums), 0) // line
        shares = share_lines(spare_lines, self._capacities(), [weight for _, weight in shown])
        return [minimum + share * line for minimum, share in zip(minimums, shares)]

    def setGeometry(self, rect: QRect) -> None:  # pylint: disable=invalid-name
        """Places the items top to bottom at the heights `item_heights` gives."""
        super().setGeometry(rect)
        area = self.contentsRect()
        top = area.top()
        for (item, _), height in zip(self._shown(), self.item_heights(rect.height())):
            item.setGeometry(QRect(area.left(), top, area.width(), height))
            top += height + self._spacing
