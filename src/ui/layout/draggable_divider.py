"""
Provides a widget that can be dragged to resize UI elements.
"""
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QPoint, QSize, QRect, Signal
from PySide6.QtGui import QPainter, QPen, QResizeEvent, QMouseEvent, QPaintEvent, QCursor
from PySide6.QtWidgets import QWidget, QSizePolicy, QBoxLayout, QHBoxLayout, QVBoxLayout, QLayoutItem, QSpacerItem, \
    QLayout

from src.util.layout import extract_layout_item
from src.util.visual.contrast_color import contrast_color

DIVIDER_SIZE = 4


class DraggableDivider(QWidget):
    """DraggableArrow is a widget that can be dragged along an axis to resize UI elements."""

    dragged = Signal(QPoint)

    def __init__(self, orientation=Qt.Orientation.Horizontal) -> None:
        super().__init__()
        self._dragging = False
        self._mode = orientation
        if orientation == Qt.Orientation.Horizontal:
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._last_pos: Optional[QPoint] = None
        self._hidden = False
        self._center_box = QRect(0, 0, 0, 0)
        self.resizeEvent(None)
        self._inactive_cursor = QCursor(Qt.CursorShape.OpenHandCursor)
        self._dragging_cursor = QCursor(Qt.CursorShape.ClosedHandCursor)
        self.setCursor(self._inactive_cursor)

    def set_horizontal_mode(self) -> None:
        """Puts the widget in horizontal mode, where it can be dragged left and right."""
        if self._mode != Qt.Orientation.Horizontal:
            self._mode = Qt.Orientation.Horizontal
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
            self.update()

    def set_vertical_mode(self) -> None:
        """Puts the widget in vertical mode, where it can be dragged up and down."""
        if self._mode != Qt.Orientation.Vertical:
            self._mode = Qt.Orientation.Vertical
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.update()

    def set_hidden(self, hidden: bool) -> None:
        """Sets whether the widget should be shown or hidden."""
        if self._hidden != hidden:
            self._hidden = hidden
            self.update()

    def sizeHint(self):
        """Calculate preferred size based on orientation."""
        if self._mode == Qt.Orientation.Horizontal:
            return QSize(DIVIDER_SIZE, DIVIDER_SIZE * 3)
        return QSize(DIVIDER_SIZE * 3, DIVIDER_SIZE)

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Recalculate arrow placement when widget bounds change."""
        layout = self._get_containing_layout()
        if isinstance(layout, QHBoxLayout) and self._mode != Qt.Orientation.Horizontal:
            self.set_horizontal_mode()
        elif isinstance(layout, QVBoxLayout) and self._mode != Qt.Orientation.Vertical:
            self.set_vertical_mode()

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draws the arrow in the chosen orientation."""
        if self._hidden:
            return
        painter = QPainter(self)
        color = contrast_color(self).lighter() if self._dragging else contrast_color(self)
        size = 4 if self._dragging else 2
        painter.setPen(QPen(color, size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap,
                            Qt.PenJoinStyle.BevelJoin))

        if self._mode == Qt.Orientation.Horizontal:
            p1 = QPoint(self.width() // 2, DIVIDER_SIZE)
            p2 = QPoint(self.width() // 2, self.height() - DIVIDER_SIZE)
        else:
            p1 = QPoint(DIVIDER_SIZE, self.height() // 2)
            p2 = QPoint(self.width() - DIVIDER_SIZE, self.height() // 2)
        painter.drawLine(p1, p2)

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Starts dragging the widget when clicked."""
        assert event is not None
        if self._hidden:
            return
        self._dragging = True
        self._last_pos = event.pos() + self.pos()
        self.setCursor(self._dragging_cursor)
        self.update()

    def _update_layout_stretch(self, pos: QPoint) -> None:
        """Goals:

        - Whenever possible, adjust the size of adjacent items without touching other items.
        - When an adjacent item cannot shrink any further, don't try to reduce its stretch.
        - When an adjacent item cannot grow any further, don't try to increase its stretch.
        - When trying to grow/shrink an adjacent item, it's acceptable to do so by resizing a non-adjacent item on
          the opposite side only when closer items on that side can't be resized.
        - Avoid changing the total sum of all stretch values in the layout.
        - Never decrease a widget's stretch to less than one.
        """
        parent_layout = self._get_containing_layout()
        assert parent_layout is not None
        own_index = parent_layout.indexOf(self)
        if own_index in (0, -1, parent_layout.count() - 1):
            return
        if self._last_pos is None:
            self._last_pos = pos + self.pos()
            return
        prev_items = []
        next_items = []
        prev_stretch = 0
        next_stretch = 0
        total_stretch = 0

        for i in range(parent_layout.count()):
            stretch = parent_layout.stretch(i)
            total_stretch += stretch
            if i == own_index:
                continue
            item = extract_layout_item(parent_layout.itemAt(i))
            item_data = {'item': item, 'stretch': stretch, 'layout_idx': i}
            if i < own_index:
                prev_stretch += stretch
                prev_items.append(item_data)
            elif i > own_index:
                next_stretch += stretch
                next_items.append(item_data)

        is_horizontal = self._mode == Qt.Orientation.Horizontal
        divider_pos = (self.x() + self.width() // 2) if is_horizontal else (self.y() + self.height() // 2)
        drag_pos = (self.x() + pos.x()) if is_horizontal else (self.y() + pos.y())
        last_pos = self._last_pos.x() if is_horizontal else self._last_pos.y()

        parent = self.parent()
        assert isinstance(parent, QWidget)
        parent_size = parent.size()

        start = 0
        end = parent_size.width() if is_horizontal else parent_size.height()
        stretch_change_value = round(total_stretch * (abs(drag_pos - last_pos) / abs(end - start)))
        if stretch_change_value < 1:
            return  # Offset hasn't changed enough to justify changing stretch
        self._last_pos = pos + self.pos()
        if drag_pos > divider_pos:
            grow_items = prev_items
            shrink_items = next_items
            shrink_item_stretch = next_stretch
            grow_idx = len(grow_items) - 1
            shrink_idx = 0
            grow_step = -1
            shrink_step = 1
        else:
            grow_items = next_items
            shrink_items = prev_items
            shrink_item_stretch = prev_stretch
            grow_idx = 0
            shrink_idx = len(shrink_items) - 1
            grow_step = 1
            shrink_step = -1

        def _item_at_min(layout_item: QWidget | QLayoutItem, item_stretch: int) -> bool:
            return item_stretch <= 1 or _item_at_minimum_size(layout_item)[0 if is_horizontal else 1]

        def _item_at_max(layout_item: QWidget | QLayoutItem) -> bool:
            return _item_at_maximum_size(layout_item)[0 if is_horizontal else 1]

        # Make sure at least one of the adjacent items can be resized, prev_items aren't at minimum stretch, and at
        # least one of the grow_items can expand:
        if (_item_at_min(shrink_items[shrink_idx]['item'], shrink_items[shrink_idx]['stretch'])
                and _item_at_max(grow_items[grow_idx]['item']) or (shrink_item_stretch < len(shrink_items))
                or all(_item_at_max(item['item']) for item in grow_items)):
            return

        stretch_change_value = min(stretch_change_value, (shrink_item_stretch - len(shrink_items)))
        moving_stretch = 0

        # Extract stretch from the items that are shrinking:
        shrink_start_idx = shrink_idx
        while 0 <= shrink_idx < len(shrink_items):
            if moving_stretch >= stretch_change_value:
                break
            shrink_item = shrink_items[shrink_idx]['item']
            shrink_item_stretch = shrink_items[shrink_idx]['stretch']
            layout_idx = shrink_items[shrink_idx]['layout_idx']
            is_first_item = shrink_idx == shrink_start_idx
            shrink_idx += shrink_step
            if _item_at_min(shrink_item, shrink_item_stretch):
                continue
            stretch_change = min(stretch_change_value, shrink_item_stretch - 1)
            parent_layout.setStretch(layout_idx, shrink_item_stretch - stretch_change)
            moving_stretch += stretch_change

            # if the first item stretch was reduced, don't bother reducing other items unless the first grow item
            # can expand:
            if is_first_item and _item_at_max(grow_items[grow_idx]['item']):
                break

        if moving_stretch < 1:
            return  # Every shrink item was at minimum size, can't resize further.

        # Re-distribute the moved stretch values to the other side:
        while 0 <= grow_idx < len(grow_items):
            assert moving_stretch > 0
            grow_item = grow_items[grow_idx]['item']
            grow_item_stretch = grow_items[grow_idx]['stretch']
            layout_idx = grow_items[grow_idx]['layout_idx']
            grow_idx += grow_step
            if not _item_at_max(grow_item):
                parent_layout.setStretch(layout_idx, grow_item_stretch + moving_stretch)
                return
        raise RuntimeError(f'Failed to redistribute stretch {moving_stretch} to opposite items')

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Emits the drag position and adjusts layout item stretch values when the mouse moves and the widget is being
           dragged."""
        if event is None:
            return
        if event.buttons() and self._dragging:
            self.dragged.emit(event.pos() + self.geometry().topLeft())
            self._update_layout_stretch(event.pos())

    def mouseReleaseEvent(self, unused_event: Optional[QMouseEvent]) -> None:
        """Exits the dragging state when the mouse is released. """
        if self._dragging:
            self._dragging = False
            self._last_pos = None
            self.setCursor(self._inactive_cursor)
            self.update()

    def _get_containing_layout(self) -> Optional[QBoxLayout]:
        parent = self.parent()
        if parent is None:
            return None
        layout = parent.layout()
        assert isinstance(layout, QBoxLayout) and layout.indexOf(self) != -1, ('DraggableDivider must be'
                                                                               ' within a box layout')
        return layout


def _item_at_minimum_size(item: Optional[QWidget | QLayout | QSpacerItem]) -> Tuple[bool, bool]:
    """Returns at_minimum_width, at_minimum_height"""
    if item is None:
        return True, True
    if isinstance(item, QLayout):
        if item.count() == 0:
            bounds = item.contentsRect()
            return bounds.width() == 0, bounds.height() == 0
        inner_items = [extract_layout_item(item.itemAt(i)) for i in range(item.count())]
        min_tuples = [_item_at_minimum_size(inner_item) for inner_item in inner_items]

        at_minimum_width = not any(size_check[0] is False for size_check in min_tuples)
        at_minimum_height = not any(size_check[1] is False for size_check in min_tuples)
    else:
        def _widget_at_minimum(size: int, fixed_min: int, size_hint_dim: int,
                               dim_size_policy: QSizePolicy.Policy) -> bool:
            if size <= fixed_min:
                return True
            if size > size_hint_dim:
                return False
            return dim_size_policy in (QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum,
                                       QSizePolicy.Policy.MinimumExpanding)
        size_hint = item.minimumSizeHint()
        size_policy = item.sizePolicy()
        at_minimum_width = _widget_at_minimum(item.width(), item.minimumWidth(), size_hint.width(),
                                              size_policy.horizontalPolicy())
        at_minimum_height = _widget_at_minimum(item.height(), item.minimumHeight(), size_hint.height(),
                                               size_policy.verticalPolicy())
    return at_minimum_width, at_minimum_height


def _item_at_maximum_size(item: Optional[QWidget | QLayout | QSpacerItem]) -> Tuple[bool, bool]:
    """Returns at_maximum_width, at_maximum_height"""
    if item is None:
        return True, True
    if isinstance(item, QLayout):
        if item.count() == 0:
            return True, True
        inner_items = [extract_layout_item(item.itemAt(i)) for i in range(item.count())]
        max_tuples = [_item_at_maximum_size(inner_item) for inner_item in inner_items]
        at_maximum_width = not any(size_check[0] is False for size_check in max_tuples)
        at_maximum_height = not any(size_check[1] is False for size_check in max_tuples)
    else:

        def _widget_at_maximum(size: int, fixed_max: int, size_hint_dim: int,
                               dim_size_policy: QSizePolicy.Policy) -> bool:
            if size >= fixed_max:
                return True
            if size < size_hint_dim:
                return False
            return dim_size_policy in (QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum)
        size_hint = item.sizeHint()
        size_policy = item.sizePolicy()
        at_maximum_width = _widget_at_maximum(item.width(), item.maximumWidth(), size_hint.width(),
                                              size_policy.horizontalPolicy())
        at_maximum_height = _widget_at_maximum(item.height(), item.maximumWidth(), size_hint.height(),
                                               size_policy.verticalPolicy())
    return at_maximum_width, at_maximum_height
