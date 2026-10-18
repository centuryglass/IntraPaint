"""Selects between the MyPaint brushes found in resources/brushes and AppConfig.ADDED_MYPAINT_BRUSH_DIR.

`MypaintBrushPanel` shows the active brush as a chip, category chips that wrap instead of scrolling, and a grid of
named tiles with a favorite star on each. A compact form replaces the chips and grid with a row of favorite thumbnails,
and the chip opens the full picker in a popover. `BrushLibrary` reads the brush files once and can be shared between
panels. The favorites list lives in AppConfig under FAV_CONFIG_KEY, so every panel follows changes made in any other.

This widget can only be used if a compatible brushlib/libmypaint QT library is available, bundled for x86_64 Linux and
Windows.
"""
import logging
import math
import os
import re
from typing import Optional

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QIcon, QImage, QMouseEvent, QPainter, QPainterPath, QPalette, QPen, QPixmap,
                           QResizeEvent)
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QApplication, QFrame, QHBoxLayout, QLabel,
                               QLayout, QLayoutItem, QListView, QListWidget, QListWidgetItem, QMenu, QPushButton,
                               QSizePolicy, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QToolButton,
                               QVBoxLayout, QWidget)

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.ui.widget.panel_header import PanelPopover
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.image_utils import temp_image_path
from src.util.visual.text_drawing_utils import max_font_size, create_text_path, draw_text_path

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.mypaint_brush_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


FAVORITES_CATEGORY_NAME = _tr('Favorites')
ALL_CATEGORY_NAME = _tr('All')
ADD_FAVORITE_LABEL = _tr('Add to Favorites')
REMOVE_FAVORITE_LABEL = _tr('Remove from Favorites')
FAVORITE_TOOLTIP = _tr('Toggle favorite')

BRUSH_DIR = f'{PROJECT_DIR}/resources/brushes'
FAV_CONFIG_KEY = 'brush_favorites'

BRUSH_CONF_FILE = 'brushes.conf'
BRUSH_ORDER_FILE = 'order.conf'
BRUSH_EXTENSION = '.myb'
BRUSH_ICON_EXTENSION = '_prev.png'
BRUSH_ICON_SIZE = 128

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
STAR_SIZE = 16
STAR_MARGIN = 5
CHIP_ICON_SIZE = 36
THUMBNAIL_SIZE = 40
COMPACT_FAVORITE_COUNT = 4
# The smallest sizes at which the full picker is laid out; smaller areas should use the compact form:
FULL_MIN_WIDTH = 240
FULL_MIN_HEIGHT = 190
POPOVER_SIZE = QSize(400, 430)

# Item data roles holding each brush tile's .myb file path and whether it is a favorite:
BRUSH_PATH_ROLE = Qt.ItemDataRole.UserRole
FAVORITE_ROLE = Qt.ItemDataRole.UserRole + 1

logger = logging.getLogger(__name__)


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


def _saved_brush_path(brush_path: str) -> str:
    """Returns a brush path as Cache stores it: relative to PROJECT_DIR when the brush is under it."""
    if brush_path.startswith(PROJECT_DIR):
        return brush_path[len(PROJECT_DIR) + 1:]
    return brush_path


def _resolved_brush_path(saved_path: Optional[str]) -> Optional[str]:
    """Returns the absolute path of a brush path from Cache, or None if it isn't a file."""
    if saved_path is None or saved_path == '':
        return None
    for path in (saved_path, os.path.join(PROJECT_DIR, saved_path)):
        if os.path.isfile(path):
            return os.path.abspath(path)
    return None


def _favorite_name(brush_path: str) -> str:
    """Returns the name a brush is saved under in the favorites list: its group directory and brush name."""
    return f'{brush_category(brush_path)}/{brush_name(brush_path)}'


def _brush_icon(name: str, image_path: str) -> QIcon:
    """Loads a brush's preview icon, or draws one showing its name if the preview image is missing."""
    if not os.path.isfile(image_path):

        def _draw_image() -> QImage:
            image = QImage(QSize(BRUSH_ICON_SIZE, BRUSH_ICON_SIZE), QImage.Format.Format_ARGB32_Premultiplied)
            image_bounds = QRect(QPoint(), image.size())
            text_bounds = image_bounds.adjusted(2, 2, -2, -2)
            palette = QApplication.palette()
            text_color = palette.color(palette.ColorRole.WindowText)
            font = QApplication.font()
            font.setPointSize(max_font_size(name, font, text_bounds.size()))
            painter = QPainter(image)
            painter.fillRect(image_bounds, palette.color(palette.ColorRole.Window))
            painter.setPen(text_color)
            painter.drawRect(image_bounds.adjusted(0, 0, -1, -1))
            draw_text_path(create_text_path(name, font, text_bounds), painter, text_color)
            painter.end()
            return image
        image_path = temp_image_path(name, _draw_image)
    return QIcon(QPixmap(image_path))


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


class BrushLibrary:
    """The brush files under resources/brushes and AppConfig.ADDED_MYPAINT_BRUSH_DIR, grouped by directory."""

    def __init__(self) -> None:
        self._groups: list[str] = []
        self._group_dirs: dict[str, str] = {}
        self._group_orders: dict[str, list[str]] = {}
        self._icons: dict[str, QIcon] = {}
        self._read_order_file(os.path.join(BRUSH_DIR, BRUSH_CONF_FILE))
        self._read_brush_dirs()

    @property
    def categories(self) -> list[str]:
        """The names of the groups that hold at least one brush, in display order."""
        return [group for group in self._groups if len(self.brush_paths(group)) > 0]

    def brush_paths(self, group: str) -> list[str]:
        """Returns the paths of a group's brush files in display order, skipping missing files."""
        group_dir = self._group_dirs.get(group)
        if group_dir is None or not os.path.isdir(group_dir):
            return []
        paths = [os.path.join(group_dir, name + BRUSH_EXTENSION) for name in self._group_orders.get(group, [])]
        return [path for path in paths if os.path.isfile(path)]

    def favorite_paths(self) -> list[str]:
        """Returns the paths of the brushes in AppConfig's favorites list, in list order, skipping unknown ones."""
        paths = []
        for favorite in AppConfig().get(FAV_CONFIG_KEY):
            if '/' not in favorite:
                continue
            group, name = favorite.split('/', 1)
            if group not in self._group_dirs:
                continue
            path = os.path.join(self._group_dirs[group], name + BRUSH_EXTENSION)
            if os.path.isfile(path):
                paths.append(path)
        return paths

    def icon(self, brush_path: str) -> QIcon:
        """Returns a brush's preview icon."""
        if brush_path not in self._icons:
            self._icons[brush_path] = _brush_icon(brush_name(brush_path),
                                                  os.path.join(os.path.dirname(brush_path),
                                                               brush_name(brush_path) + BRUSH_ICON_EXTENSION))
        return self._icons[brush_path]

    def _read_brush_dirs(self) -> None:
        """Reads in brush files, organizing them into groups."""
        brush_dirs = [BRUSH_DIR]
        custom_brush_dir = AppConfig().get(AppConfig.ADDED_MYPAINT_BRUSH_DIR)
        if os.path.isdir(custom_brush_dir):
            brush_dirs.append(custom_brush_dir)
        brush_files: dict[str, list[str]] = {}
        seen_dirs: dict[str, str] = {}
        while len(brush_dirs) > 0:
            brush_dir = brush_dirs.pop(0)
            dir_name = os.path.basename(brush_dir)
            if dir_name in seen_dirs:
                if seen_dirs[dir_name] != brush_dir:
                    logger.error(f'Duplicate group {dir_name} found in both {seen_dirs[dir_name]} and '
                                 f'{brush_dir}, the second directory will be ignored.')
                continue
            seen_dirs[dir_name] = brush_dir
            for brush_dir_file in os.listdir(brush_dir):
                full_path = os.path.join(brush_dir, brush_dir_file)
                if brush_dir_file == BRUSH_ORDER_FILE:
                    self._read_order_file(full_path)
                elif os.path.isdir(full_path):
                    brush_dirs.append(full_path)
                elif full_path.endswith(BRUSH_EXTENSION):
                    if dir_name not in brush_files:
                        brush_files[dir_name] = []
                        if dir_name not in self._groups:
                            self._groups.append(dir_name)
                        self._group_dirs[dir_name] = brush_dir
                    brush_files[dir_name].append(brush_dir_file[:-len(BRUSH_EXTENSION)])
        for group in self._group_orders:
            brush_files.pop(group, None)
        for group, group_brushes in brush_files.items():
            group_brushes.sort()
            self._group_orders[group] = [*group_brushes]

    def _read_order_file(self, file_path: str) -> bool:
        if not os.path.exists(file_path):
            return False
        dir_path = os.path.dirname(file_path)
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = [ln.strip() for ln in file.readlines()]
        for line in lines:
            group_match = re.search(r'^Group: ([^#]+)', line)
            if group_match:
                group = group_match.group(1)
                self._groups.append(group)
                self._group_dirs[group] = os.path.join(dir_path, group)
                self._group_orders[group] = []
                continue
            if '/' not in line:
                continue
            group, brush = line.split('/')
            if group not in self._group_orders:
                self._groups.append(group)
                self._group_dirs[group] = os.path.join(dir_path, group)
                self._group_orders[group] = []
            self._group_orders[group].append(brush)
        return True


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

    def sizeHint(self) -> QSize:
        """Asks for PREFERRED_ROWS rows of PREFERRED_COLUMNS minimum-size tiles, and scrolls to show the rest."""
        return self._hint_size(PREFERRED_COLUMNS, PREFERRED_ROWS)

    def minimumSizeHint(self) -> QSize:
        """Asks for one minimum-size tile and the scroll bar."""
        return self._hint_size(1, 1)


class CurrentBrushChip(QFrame):
    """Shows the active brush's preview, name and category, with a star that toggles its favorite.

    While `popup_enabled` is set, the chip shows a drop-down arrow and emits `clicked` when pressed.
    """

    clicked = Signal()
    favoriteToggled = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._popup_enabled = False
        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(CHIP_ICON_SIZE, CHIP_ICON_SIZE)
        self._name_label = QLabel(self)
        name_font = self._name_label.font()
        name_font.setBold(True)
        self._name_label.setFont(name_font)
        self._category_label = QLabel(self)
        self._category_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        for label in (self._name_label, self._category_label):
            label.setMinimumWidth(1)
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._star = StarButton(self)
        self._arrow = QLabel('▾', self)
        self._arrow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._arrow.hide()
        text_column = QVBoxLayout()
        text_column.setSpacing(0)
        text_column.addWidget(self._name_label)
        text_column.addWidget(self._category_label)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.addWidget(self._icon_label)
        layout.addLayout(text_column, stretch=1)
        layout.addWidget(self._star)
        layout.addWidget(self._arrow)
        self._star.clicked.connect(self.favoriteToggled)

    @property
    def name_label(self) -> QLabel:
        """The brush name."""
        return self._name_label

    @property
    def category_label(self) -> QLabel:
        """The name of the brush's group."""
        return self._category_label

    @property
    def star(self) -> StarButton:
        """The favorite toggle."""
        return self._star

    @property
    def popup_enabled(self) -> bool:
        """Whether pressing the chip should open the picker."""
        return self._popup_enabled

    def set_popup_enabled(self, enabled: bool) -> None:
        """Shows the drop-down arrow and a pointing-hand cursor, or hides them."""
        self._popup_enabled = enabled
        self._arrow.setVisible(enabled)
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)

    def set_brush(self, brush_path: Optional[str], icon: Optional[QIcon], favorite: bool) -> None:
        """Shows a brush, or an empty chip if `brush_path` is None."""
        if brush_path is None or icon is None:
            self._icon_label.clear()
            self._name_label.setText('')
            self._category_label.setText('')
            self._star.setEnabled(False)
            self._star.setChecked(False)
            return
        self._icon_label.setPixmap(icon.pixmap(CHIP_ICON_SIZE, CHIP_ICON_SIZE))
        self._name_label.setText(brush_name(brush_path))
        self._category_label.setText(brush_category(brush_path))
        self._star.setEnabled(True)
        self._star.setChecked(favorite)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # pylint: disable=invalid-name
        """Emits `clicked` while the popup is enabled."""
        if self._popup_enabled and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class MypaintBrushPanel(QWidget):
    """MypaintBrushPanel selects between the MyPaint brushes with a chip, category chips and a grid of tiles.

    - The category chips are Favorites while AppConfig's FAV_CONFIG_KEY lists any brushes, All, and one per brush group.
    - Selecting a tile sets the brush Cache holds under brush_config_key, and the panel follows changes to that key.
    - `set_compact` swaps the chips and grid for a row of favorite thumbnails. The chip then opens the full picker in a
      popover that closes when a brush is picked.
    """

    brush_picked = Signal()

    def __init__(self, brush_config_key: str = 'mypaint_brush', parent: Optional[QWidget] = None,
                 library: Optional[BrushLibrary] = None, compact: bool = False) -> None:
        """Loads brushes and optionally adds the widget to a parent.

        Parameters
        ----------
        brush_config_key : str
            Cache key defining the active brush path.
        parent : QWidget, optional
            Parent widget.
        library : BrushLibrary, optional
            Brush files to show. Panels can share one library. By default, the panel reads its own.
        compact : bool, default=False
            Whether to start in the compact form.
        """
        super().__init__(parent)
        self._brush_config_key = brush_config_key
        self._library = library if library is not None else BrushLibrary()
        self._compact = compact
        self._favorite_count = COMPACT_FAVORITE_COUNT
        self._category: Optional[str] = None
        self._category_buttons: dict[str, QPushButton] = {}
        self._thumbnails: list[QToolButton] = []
        self._popover: Optional[PanelPopover] = None

        self._chip = CurrentBrushChip(self)
        self._chip.favoriteToggled.connect(self._toggle_active_favorite)
        self._chip.clicked.connect(self._show_popover)

        self._category_widget = QWidget(self)
        self._category_layout = FlowLayout(self._category_widget)
        self._grid = BrushList(self)
        self._grid.itemSelectionChanged.connect(self._selection_change_slot)
        self._grid.customContextMenuRequested.connect(self._menu)
        self._grid.favoriteToggled.connect(self.toggle_favorite)

        self._favorites_row = QWidget(self)
        self._favorites_layout = QHBoxLayout(self._favorites_row)
        self._favorites_layout.setContentsMargins(0, 0, 0, 0)
        self._favorites_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._chip)
        layout.addWidget(self._category_widget)
        layout.addWidget(self._grid, stretch=1)
        layout.addWidget(self._favorites_row)

        self._rebuild_categories()
        self._apply_form()
        self._rebuild_thumbnails()
        Cache().connect(self, brush_config_key, lambda _: self._show_active_brush())
        AppConfig().connect(self, FAV_CONFIG_KEY, lambda _: self._favorites_changed())

    # -----------------------------------------------------------------------------------------------------------------
    # Parts
    # -----------------------------------------------------------------------------------------------------------------

    @property
    def library(self) -> BrushLibrary:
        """The brush files shown."""
        return self._library

    @property
    def chip(self) -> CurrentBrushChip:
        """The active brush chip."""
        return self._chip

    @property
    def grid(self) -> BrushList:
        """The grid of brush tiles for the chosen category."""
        return self._grid

    @property
    def category(self) -> Optional[str]:
        """The name of the chosen category chip."""
        return self._category

    @property
    def category_names(self) -> list[str]:
        """The names of the category chips, in display order."""
        return list(self._category_buttons)

    @property
    def category_buttons(self) -> dict[str, QPushButton]:
        """The category chips by name."""
        return dict(self._category_buttons)

    @property
    def thumbnails(self) -> list[QToolButton]:
        """The favorite thumbnails shown in the compact form."""
        return list(self._thumbnails)

    @property
    def compact(self) -> bool:
        """Whether the compact form is showing."""
        return self._compact

    @property
    def popover(self) -> Optional[PanelPopover]:
        """The popover holding the full picker, once it has been opened."""
        return self._popover

    @property
    def active_brush_path(self) -> Optional[str]:
        """The absolute path of the active brush, or None if Cache holds none that exists."""
        return _resolved_brush_path(Cache().get(self._brush_config_key))

    def set_compact(self, compact: bool) -> None:
        """Switches between the full picker and the chip with a row of favorites."""
        if compact != self._compact:
            self._compact = compact
            self._apply_form()

    def set_favorite_count(self, count: int) -> None:
        """Changes how many favorite thumbnails the compact form shows."""
        if count != self._favorite_count:
            self._favorite_count = count
            self._rebuild_thumbnails()
            self.updateGeometry()

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the layout's minimum, raised to FULL_MIN_WIDTH by FULL_MIN_HEIGHT in the full form so a host sees
        when the compact form would fit better."""
        hint = super().minimumSizeHint()
        return hint if self._compact else hint.expandedTo(QSize(FULL_MIN_WIDTH, FULL_MIN_HEIGHT))

    def _apply_form(self) -> None:
        self._category_widget.setVisible(not self._compact)
        self._grid.setVisible(not self._compact)
        self._favorites_row.setVisible(self._compact and len(self._thumbnails) > 0)
        self._chip.set_popup_enabled(self._compact)
        self.layout().setStretchFactor(self._grid, 0 if self._compact else 1)
        self.setSizePolicy(QSizePolicy.Policy.Preferred,
                           QSizePolicy.Policy.Maximum if self._compact else QSizePolicy.Policy.Expanding)
        self.updateGeometry()

    # -----------------------------------------------------------------------------------------------------------------
    # Categories and tiles
    # -----------------------------------------------------------------------------------------------------------------

    def _category_names(self) -> list[str]:
        names = [ALL_CATEGORY_NAME, *self._library.categories]
        if len(self._library.favorite_paths()) > 0:
            names.insert(0, FAVORITES_CATEGORY_NAME)
        return names

    def _rebuild_categories(self) -> None:
        names = self._category_names()
        if self._category not in names:
            self._category = names[0]
        for button in self._category_buttons.values():
            self._category_layout.removeWidget(button)
            button.setParent(None)
            button.deleteLater()
        self._category_buttons = {}
        for name in names:
            button = QPushButton(name, self._category_widget)
            button.setCheckable(True)
            button.setChecked(name == self._category)
            button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda _checked=False, chosen=name: self.set_category(chosen))
            self._category_layout.addWidget(button)
            self._category_buttons[name] = button
        self._category_widget.updateGeometry()
        self._fill_grid()

    def set_category(self, category: str) -> None:
        """Shows the brushes of a category chip."""
        if category not in self._category_buttons:
            return
        self._category = category
        for name, button in self._category_buttons.items():
            button.setChecked(name == category)
        self._fill_grid()

    def _category_paths(self) -> list[str]:
        if self._category == FAVORITES_CATEGORY_NAME:
            return self._library.favorite_paths()
        if self._category == ALL_CATEGORY_NAME or self._category is None:
            return [path for group in self._library.categories for path in self._library.brush_paths(group)]
        return self._library.brush_paths(self._category)

    def _fill_grid(self) -> None:
        self._grid.blockSignals(True)
        self._grid.clear()
        self._grid.set_favorites(set(self._library.favorite_paths()))
        for path in self._category_paths():
            self._grid.add_brush(path, self._library.icon(path))
        self._grid.blockSignals(False)
        self._show_active_brush()

    def _show_active_brush(self) -> None:
        """Selects the active brush's tile if the grid holds it, and updates the chip and thumbnails."""
        active_brush = self.active_brush_path
        item = self._grid.find_brush(active_brush)
        self._grid.blockSignals(True)
        try:
            if item is None:
                self._grid.clearSelection()
            elif not item.isSelected():
                self._grid.setCurrentItem(item)
        finally:
            self._grid.blockSignals(False)
        favorites = {os.path.abspath(path) for path in self._library.favorite_paths()}
        self._chip.set_brush(active_brush, None if active_brush is None else self._library.icon(active_brush),
                             active_brush in favorites)
        for button in self._thumbnails:
            button.setChecked(os.path.abspath(button.property('brush_path')) == active_brush)

    def _selection_change_slot(self) -> None:
        selected = self._grid.selectedItems()
        if len(selected) == 0:
            return
        self._choose_brush(selected[0].data(BRUSH_PATH_ROLE))

    def _choose_brush(self, brush_path: str) -> None:
        if _resolved_brush_path(Cache().get(self._brush_config_key)) != os.path.abspath(brush_path):
            Cache().set(self._brush_config_key, _saved_brush_path(brush_path))
            self.brush_picked.emit()

    # -----------------------------------------------------------------------------------------------------------------
    # Favorites
    # -----------------------------------------------------------------------------------------------------------------

    def _menu(self, pos: QPoint) -> None:
        """Offers to add the brush under the cursor to favorites, or to remove it from them."""
        item = self._grid.itemAt(pos)
        if item is None:
            return
        brush_path = item.data(BRUSH_PATH_ROLE)
        is_favorite = bool(item.data(FAVORITE_ROLE))
        menu = QMenu(self)
        menu.setTitle(item.toolTip())
        action = menu.addAction(REMOVE_FAVORITE_LABEL if is_favorite else ADD_FAVORITE_LABEL)
        if menu.exec(self._grid.viewport().mapToGlobal(pos)) == action:
            self.toggle_favorite(brush_path)

    def is_favorite(self, brush_path: str) -> bool:
        """Returns whether a brush is in the favorites list."""
        return _favorite_name(brush_path) in AppConfig().get(FAV_CONFIG_KEY)

    def toggle_favorite(self, brush_path: str) -> None:
        """Adds a brush to the favorites if it isn't one, and removes it otherwise."""
        if self.is_favorite(brush_path):
            self.remove_favorite(brush_path)
        else:
            self.add_favorite(brush_path)

    def add_favorite(self, brush_path: str) -> None:
        """Adds a brush to the end of the favorites and saves them. Every panel follows the change."""
        favorite_list = AppConfig().get(FAV_CONFIG_KEY)
        saved_name = _favorite_name(brush_path)
        if saved_name not in favorite_list:
            AppConfig().set(FAV_CONFIG_KEY, [*favorite_list, saved_name])

    def remove_favorite(self, brush_path: str) -> None:
        """Removes a brush from the favorites and saves them. The Favorites chip goes when the last one does."""
        saved_name = _favorite_name(brush_path)
        favorite_list = AppConfig().get(FAV_CONFIG_KEY)
        if saved_name in favorite_list:
            AppConfig().set(FAV_CONFIG_KEY, [name for name in favorite_list if name != saved_name])

    def _toggle_active_favorite(self) -> None:
        active_brush = self.active_brush_path
        if active_brush is not None:
            self.toggle_favorite(active_brush)

    def _favorites_changed(self) -> None:
        """Updates the chips, tiles, chip star and thumbnails after the favorites list changed."""
        self._rebuild_categories()
        self._rebuild_thumbnails()

    def _rebuild_thumbnails(self) -> None:
        for button in self._thumbnails:
            self._favorites_layout.removeWidget(button)
            button.setParent(None)
            button.deleteLater()
        self._thumbnails = []
        for path in self._library.favorite_paths()[:self._favorite_count]:
            button = QToolButton(self._favorites_row)
            button.setIcon(self._library.icon(path))
            button.setIconSize(QSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE))
            button.setCheckable(True)
            button.setToolTip(brush_name(path))
            button.setAccessibleName(brush_name(path))
            button.setProperty('brush_path', path)
            button.clicked.connect(lambda _checked=False, chosen=path: self._thumbnail_clicked(chosen))
            self._favorites_layout.addWidget(button)
            self._thumbnails.append(button)
        self._favorites_row.setVisible(self._compact and len(self._thumbnails) > 0)
        self._show_active_brush()

    def _thumbnail_clicked(self, brush_path: str) -> None:
        self._choose_brush(brush_path)
        self._show_active_brush()

    # -----------------------------------------------------------------------------------------------------------------
    # Popover
    # -----------------------------------------------------------------------------------------------------------------

    def _show_popover(self) -> None:
        """Opens the full picker under the chip."""
        if self._popover is None:
            self._popover = PanelPopover(self)
            picker = MypaintBrushPanel(self._brush_config_key, library=self._library)
            picker.setFixedSize(POPOVER_SIZE)
            picker.brush_picked.connect(self._popover.hide)
            self._popover.set_content(picker)
        self._popover.adjustSize()
        corner = self._chip.mapToGlobal(self._chip.rect().bottomLeft())
        self._popover.move(corner.x(), corner.y() + 2)
        self._popover.show()
