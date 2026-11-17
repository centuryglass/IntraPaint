"""The brush picker's tile grid and category list, with the favorite star drawn on tiles and buttons.

`BrushList` sizes its tiles with `brush_cell_size`, so a panel can predict how many fit. `MypaintBrushPanel`
(`src.ui.panel.mypaint_brush_panel`) puts them together.
"""
import math
import os
from typing import Optional

from PySide6.QtCore import QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QMouseEvent, QPainter, QPainterPath, QPalette, QPen, QResizeEvent
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QApplication, QFrame, QListView, QListWidget,
                               QListWidgetItem, QSizePolicy, QStyle, QStyledItemDelegate, QStyleOptionViewItem,
                               QWidget)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.mypaint_brush_grid'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


FAVORITE_TOOLTIP = _tr('Toggle favorite')

BRUSH_EXTENSION = '.myb'

MIN_ICON_SIZE = 48
# Tiles stop growing here, so a wide panel adds columns:
MAX_ICON_SIZE = 104
# Space between an icon and the edge of its grid cell:
ICON_PADDING = 3
MIN_CELL_SIZE = MIN_ICON_SIZE + 2 * ICON_PADDING
MAX_CELL_SIZE = MAX_ICON_SIZE + 2 * ICON_PADDING
# Rows and columns of minimum-size tiles the brush grid asks for in its size hints:
PREFERRED_ROWS = 2
PREFERRED_COLUMNS = 4
MIN_ROWS = 1
MIN_COLUMNS = 3
# Padding around each name in the category list:
CATEGORY_LIST_PADDING = 8
STAR_SIZE = 16
STAR_MARGIN = 5

# Item data roles holding each brush tile's .myb file path and whether it is a favorite:
BRUSH_PATH_ROLE = Qt.ItemDataRole.UserRole
FAVORITE_ROLE = Qt.ItemDataRole.UserRole + 1


def brush_cell_size(width: int, height: int, count: int, extra_height: int = 0) -> int:
    """Returns the cell width for count brush tiles in a list area of the given size.

    A tile is a square icon cell with `extra_height` more pixels under it for the name.
    - When every tile fits without scrolling at some cell size from MIN_CELL_SIZE to MAX_CELL_SIZE, returns the
      largest such size.
    - Otherwise, rows hold as many cells of at least MIN_CELL_SIZE as fit, sized to fill the width.
    A width below MIN_CELL_SIZE still gets MIN_CELL_SIZE.
    """
    max_columns = max(1, width // MIN_CELL_SIZE)
    largest_fit = 0
    for columns in range(1, max_columns + 1):
        rows = max(1, math.ceil(count / columns))
        largest_fit = max(largest_fit, min(width // columns, height // rows - extra_height, MAX_CELL_SIZE))
    if largest_fit >= MIN_CELL_SIZE:
        return largest_fit
    return max(MIN_CELL_SIZE, min(width // max_columns, MAX_CELL_SIZE))


def brush_name(brush_path: str) -> str:
    """Returns a brush file's name without its directory or extension."""
    return os.path.basename(brush_path)[:-len(BRUSH_EXTENSION)]


def brush_category(brush_path: str) -> str:
    """Returns the name of the directory holding a brush file."""
    return os.path.basename(os.path.dirname(brush_path))


def star_path(bounds: QRectF) -> QPainterPath:
    """Returns a five-pointed star inscribed in `bounds`."""
    center = bounds.center()
    outer = min(bounds.width(), bounds.height()) / 2
    inner = outer * 0.45
    path = QPainterPath()
    for point in range(10):
        angle = -math.pi / 2 + point * math.pi / 5
        radius = outer if point % 2 == 0 else inner
        x, y = center.x() + radius * math.cos(angle), center.y() + radius * math.sin(angle)
        if point == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.closeSubpath()
    return path


def paint_star(painter: QPainter, bounds: QRectF, palette: QPalette, filled: bool) -> None:
    """Draws a filled star in the highlight color, or a hollow one in the text color."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = palette.color(QPalette.ColorRole.Highlight if filled else QPalette.ColorRole.Text)
    painter.setPen(QPen(color, 1.2))
    painter.setBrush(color if filled else Qt.BrushStyle.NoBrush)
    painter.drawPath(star_path(bounds))
    painter.restore()


class StarButton(QAbstractButton):
    """A checkable star that marks a brush as a favorite."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(FAVORITE_TOOLTIP)
        self.setAccessibleName(FAVORITE_TOOLTIP)
        self.setFixedSize(STAR_SIZE + 8, STAR_SIZE + 8)

    def paintEvent(self, _event) -> None:  # pylint: disable=invalid-name
        """Draws the star, filled while checked."""
        painter = QPainter(self)
        paint_star(painter, QRectF(self.rect()).adjusted(4, 4, -4, -4), self.palette(), self.isChecked())
        painter.end()


def star_rect(cell: QRect) -> QRect:
    """Returns where a tile's favorite star sits inside its grid cell."""
    return QRect(cell.right() - STAR_SIZE - STAR_MARGIN, cell.top() + STAR_MARGIN, STAR_SIZE, STAR_SIZE)


class _TileDelegate(QStyledItemDelegate):
    """Paints a brush tile: the preview icon, the brush name under it, and a favorite star in the corner."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        """Draws one tile."""
        palette = option.palette
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        cell = option.rect
        tile = cell.adjusted(1, 1, -1, -1)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if selected or hovered:
            painter.setPen(QPen(palette.color(QPalette.ColorRole.Highlight if selected else QPalette.ColorRole.Mid),
                                2 if selected else 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(tile).adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
        icon_size = cell.width() - 2 * ICON_PADDING
        icon_rect = QRect(cell.left() + ICON_PADDING, cell.top() + ICON_PADDING, icon_size, icon_size)
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(icon, QIcon):
            icon.paint(painter, icon_rect)
        name = str(index.data(Qt.ItemDataRole.DisplayRole) or '')
        text_rect = QRect(cell.left() + 2, icon_rect.bottom() + 1, cell.width() - 4,
                          cell.bottom() - icon_rect.bottom() - 1)
        painter.setPen(palette.color(QPalette.ColorRole.Text))
        painter.setFont(option.font)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                         painter.fontMetrics().elidedText(name, Qt.TextElideMode.ElideRight, text_rect.width()))
        favorite = bool(index.data(FAVORITE_ROLE))
        if favorite or selected or hovered:
            star_bounds = QRectF(star_rect(cell))
            paint_star(painter, star_bounds, palette, favorite)
        painter.restore()


class BrushList(QListWidget):
    """A wrapping grid of named brush tiles that scrolls vertically and sizes its tiles to fill each row.

    A click on a tile's star emits `favoriteToggled` and leaves the selection alone.
    """

    favoriteToggled = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setMouseTracking(True)
        self.setItemDelegate(_TileDelegate(self))
        self._favorites: set[str] = set()
        self._minimum_columns = MIN_COLUMNS
        self._minimum_rows = MIN_ROWS
        self._update_cell_size()

    @property
    def name_height(self) -> int:
        """The height under each icon that holds the brush name."""
        return self.fontMetrics().height() + 4

    def add_brush(self, brush_path: str, icon: QIcon) -> QListWidgetItem:
        """Adds a tile for a brush file, showing the brush name."""
        item = QListWidgetItem(icon, brush_name(brush_path), self)
        item.setData(BRUSH_PATH_ROLE, brush_path)
        item.setData(FAVORITE_ROLE, os.path.abspath(brush_path) in self._favorites)
        item.setToolTip(brush_name(brush_path))
        item.setData(Qt.ItemDataRole.AccessibleTextRole, item.toolTip())
        self._update_cell_size()
        return item

    def remove_brush(self, brush_path: str) -> None:
        """Removes a brush file's tile, if the list holds it."""
        item = self.find_brush(os.path.abspath(brush_path))
        if item is not None:
            self.takeItem(self.row(item))
            self._update_cell_size()

    def set_favorites(self, favorite_paths: set[str]) -> None:
        """Changes which tiles show a filled star."""
        self._favorites = {os.path.abspath(path) for path in favorite_paths}
        for i in range(self.count()):
            item = self.item(i)
            item.setData(FAVORITE_ROLE, os.path.abspath(item.data(BRUSH_PATH_ROLE)) in self._favorites)
        self.viewport().update()

    def brush_paths(self) -> list[str]:
        """Returns the brush file paths of every item, in display order."""
        return [self.item(i).data(BRUSH_PATH_ROLE) for i in range(self.count())]

    def find_brush(self, brush_path: Optional[str]) -> Optional[QListWidgetItem]:
        """Returns the item for a brush file, or None if the list doesn't hold it."""
        if brush_path is None:
            return None
        for i in range(self.count()):
            item = self.item(i)
            if os.path.abspath(item.data(BRUSH_PATH_ROLE)) == brush_path:
                return item
        return None

    def icon_area_size(self) -> QSize:
        """Returns the area brush_cell_size fills with tiles: the list's size inside its frame and scroll bar.

        - The scroll bar's width is always left out, so the cell size is the same whether or not the scroll bar is
          showing. Otherwise showing it could change the cell size and hide it again.
        - One more pixel of width is left out: QListView only fits n cells in a row when the viewport is wider than n
          cells.
        """
        scroll_bar = self.verticalScrollBar()
        scroll_bar_width = 0 if scroll_bar is None else scroll_bar.sizeHint().width()
        frame = 2 * self.frameWidth()
        return QSize(self.width() - frame - scroll_bar_width - 1, self.height() - frame)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # pylint: disable=invalid-name
        """Toggles the favorite when a tile's star is clicked, and otherwise selects as usual."""
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            if item is not None and star_rect(self.visualItemRect(item)).contains(event.position().toPoint()):
                self.favoriteToggled.emit(item.data(BRUSH_PATH_ROLE))
                event.accept()
                return
        super().mousePressEvent(event)

    def _update_cell_size(self) -> None:
        area = self.icon_area_size()
        extra = self.name_height
        cell_size = brush_cell_size(area.width(), area.height(), self.count(), extra)
        if self.gridSize().width() != cell_size or self.gridSize().height() != cell_size + extra:
            self.setGridSize(QSize(cell_size, cell_size + extra))
            icon_size = cell_size - 2 * ICON_PADDING
            self.setIconSize(QSize(icon_size, icon_size))

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Resizes the tiles for the new size."""
        self._update_cell_size()
        super().resizeEvent(event)

    def _hint_size(self, columns: int, rows: int) -> QSize:
        scroll_bar = self.verticalScrollBar()
        scroll_bar_width = 0 if scroll_bar is None else scroll_bar.sizeHint().width()
        frame = 2 * self.frameWidth()
        return QSize(MIN_CELL_SIZE * columns + scroll_bar_width + frame,
                     (MIN_CELL_SIZE + self.name_height) * rows + frame)

    @property
    def minimum_columns(self) -> int:
        """The columns of minimum-size tiles the minimum size hint holds."""
        return self._minimum_columns

    @property
    def minimum_rows(self) -> int:
        """The rows of minimum-size tiles the minimum size hint holds."""
        return self._minimum_rows

    def set_minimum_tiles(self, columns: int, rows: int) -> None:
        """Sets how many columns and rows of minimum-size tiles the minimum size hint holds."""
        if (columns, rows) != (self._minimum_columns, self._minimum_rows):
            self._minimum_columns = columns
            self._minimum_rows = rows
            self.updateGeometry()

    def sizeHint(self) -> QSize:
        """Asks for PREFERRED_ROWS rows of PREFERRED_COLUMNS minimum-size tiles, or the minimum if that is larger, and
        scrolls to show the rest."""
        return self._hint_size(max(PREFERRED_COLUMNS, self._minimum_columns), max(PREFERRED_ROWS, self._minimum_rows))

    def minimumSizeHint(self) -> QSize:
        """Asks for the `set_minimum_tiles` rows and columns of minimum-size tiles, MIN_ROWS of MIN_COLUMNS by default,
        and the scroll bar."""
        return self._hint_size(self._minimum_columns, self._minimum_rows)


class CategoryList(QListWidget):
    """A single-choice list of category names, as wide as its longest name, that scrolls vertically."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def set_names(self, names: list[str]) -> None:
        """Replaces the names, keeping no selection."""
        self.clear()
        self.addItems(names)
        self.updateGeometry()

    def _width(self) -> int:
        scroll_bar = self.verticalScrollBar()
        scroll_bar_width = 0 if scroll_bar is None else scroll_bar.sizeHint().width()
        names = [self.item(i).text() for i in range(self.count())]
        text_width = max((self.fontMetrics().horizontalAdvance(name) for name in names), default=0)
        return text_width + 2 * CATEGORY_LIST_PADDING + scroll_bar_width + 2 * self.frameWidth()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns room for every name in one column, without scrolling."""
        rows = max(self.count(), 1)
        return QSize(self._width(), self.sizeHintForRow(0) * rows + 2 * self.frameWidth() if self.count() > 0
                     else self.fontMetrics().height() * rows)

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns room for the longest name on one line, and two rows."""
        row = self.sizeHintForRow(0) if self.count() > 0 else self.fontMetrics().height()
        return QSize(self._width(), row * 2 + 2 * self.frameWidth())
