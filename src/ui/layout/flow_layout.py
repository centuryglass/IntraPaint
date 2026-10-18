"""A layout that wraps its widgets onto more lines, and a widget that measures its height at a given width."""
from typing import Optional

from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QLayout, QLayoutItem, QSizePolicy, QWidget


class FlowLayout(QLayout):
    """Lays out widgets left to right, starting a new line when the next one doesn't fit."""

    def __init__(self, parent: Optional[QWidget] = None, spacing: int = 4) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item: QLayoutItem) -> None:  # pylint: disable=invalid-name
        """Adds a layout item after the others."""
        self._items.append(item)

    def count(self) -> int:
        """Returns the number of items."""
        return len(self._items)

    def itemAt(self, index: int) -> Optional[QLayoutItem]:  # pylint: disable=invalid-name
        """Returns the item at an index, or None."""
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> Optional[QLayoutItem]:  # pylint: disable=invalid-name
        """Removes and returns the item at an index."""
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def hasHeightForWidth(self) -> bool:  # pylint: disable=invalid-name
        """Returns true, since the height depends on how many lines fit."""
        return True

    def heightForWidth(self, width: int) -> int:  # pylint: disable=invalid-name
        """Returns the height needed at a width."""
        return self._do_layout(QRect(0, 0, width, 0), False)

    def setGeometry(self, rect: QRect) -> None:  # pylint: disable=invalid-name
        """Places the items inside a rectangle."""
        super().setGeometry(rect)
        self._do_layout(rect, True)

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the minimum size."""
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the size of the largest item plus margins."""
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _do_layout(self, rect: QRect, apply: bool) -> int:
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y, line_height = area.x(), area.y(), 0
        for item in self._items:
            if item.widget() is not None and item.widget().isHidden():
                continue
            hint = item.sizeHint()
            if x > area.x() and x + hint.width() > area.right() + 1:
                x = area.x()
                y += line_height + self._spacing
                line_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._spacing
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


class FlowWidget(QWidget):
    """Widgets that wrap onto more lines instead of scrolling, in a `FlowLayout`.

    Its minimum height is that of its lines at `wrap_width`. A parent layout's minimum size can't depend on a child's
    width, so the owner sets the width it will be laid out at before anything measures them. A resize wraps
    at the new width.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._flow = FlowLayout(self)
        self._wrap_width = 0
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    @property
    def flow(self) -> 'FlowLayout':
        """The layout holding the widgets."""
        return self._flow

    @property
    def wrap_width(self) -> int:
        """The width the minimum height is measured at."""
        return self._wrap_width

    def set_wrap_width(self, width: int) -> None:
        """Changes the width the minimum height is measured at."""
        if width != self._wrap_width:
            self._wrap_width = width
            self.updateGeometry()

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the widest widget's width, and the height of the lines at `wrap_width`."""
        widest = self._flow.minimumSize().width()
        return QSize(widest, self._flow.heightForWidth(max(widest, self._wrap_width)))

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the minimum size, since the widgets wrap to any width."""
        return self.minimumSizeHint()

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:  # pylint: disable=invalid-name
        """Measures the minimum height at the new width."""
        super().resizeEvent(event)
        self.set_wrap_width(self.width())
