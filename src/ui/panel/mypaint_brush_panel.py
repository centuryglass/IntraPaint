"""Selects between the MyPaint brushes found in resources/brushes and AppConfig.ADDED_MYPAINT_BRUSH_DIR.

Each brush group gets a tab holding a wrapping, scrolling icon list. The icon size follows the list's size, from
MIN_ICON_SIZE to MAX_ICON_SIZE, as brush_cell_size describes. Only the list scrolls: its size hints ask for a few rows,
and it stretches to fill whatever height its parent gives it.

This widget can only be used if a compatible brushlib/libmypaint QT library is available, bundled for x86_64 Linux and
Windows.
"""
import logging
import math
import os
import re
from typing import Optional

from PySide6.QtCore import Qt, QRect, QPoint, QSize
from PySide6.QtGui import QPixmap, QImage, QPainter, QIcon, QResizeEvent
from PySide6.QtWidgets import QWidget, QTabWidget, QMenu, QSizePolicy, QApplication, QListWidget, QListWidgetItem, \
    QListView, QAbstractItemView, QFrame

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.image_utils import temp_image_path
from src.util.visual.text_drawing_utils import max_font_size, create_text_path, draw_text_path

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.mypaint_brush_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


FAVORITES_CATEGORY_NAME = _tr('favorites')
ADD_FAVORITE_LABEL = _tr('Add to Favorites')
REMOVE_FAVORITE_LABEL = _tr('Remove from Favorites')

BRUSH_DIR = f'{PROJECT_DIR}/resources/brushes'
ICON_PATH_FAVORITES = f'{PROJECT_DIR}/resources/icons/tabs/star.svg'
FAV_CONFIG_KEY = 'brush_favorites'

BRUSH_CONF_FILE = 'brushes.conf'
BRUSH_ORDER_FILE = 'order.conf'
BRUSH_EXTENSION = '.myb'
BRUSH_ICON_EXTENSION = '_prev.png'
BRUSH_ICON_SIZE = 128

MIN_ICON_SIZE = 48
MAX_ICON_SIZE = 128
# Space between an icon and the edge of its grid cell:
ICON_PADDING = 3
MIN_CELL_SIZE = MIN_ICON_SIZE + 2 * ICON_PADDING
MAX_CELL_SIZE = MAX_ICON_SIZE + 2 * ICON_PADDING
# Rows and columns of minimum-size icons the brush lists ask for in their size hints:
PREFERRED_ROWS = 2
PREFERRED_COLUMNS = 4

# Item data role holding each brush item's .myb file path:
BRUSH_PATH_ROLE = Qt.ItemDataRole.UserRole

logger = logging.getLogger(__name__)


def brush_cell_size(width: int, height: int, count: int) -> int:
    """Returns the square grid cell size for count brush icons in a list area of the given size.

    - When every icon fits without scrolling at some cell size from MIN_CELL_SIZE to MAX_CELL_SIZE, returns the
      largest such size.
    - Otherwise, rows hold as many cells of at least MIN_CELL_SIZE as fit, sized to fill the width.
    A width below MIN_CELL_SIZE still gets MIN_CELL_SIZE.
    """
    max_columns = max(1, width // MIN_CELL_SIZE)
    largest_fit = 0
    for columns in range(1, max_columns + 1):
        rows = max(1, math.ceil(count / columns))
        largest_fit = max(largest_fit, min(width // columns, height // rows, MAX_CELL_SIZE))
    if largest_fit >= MIN_CELL_SIZE:
        return largest_fit
    return max(MIN_CELL_SIZE, min(width // max_columns, MAX_CELL_SIZE))


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


def _brush_icon(brush_name: str, image_path: str) -> QIcon:
    """Loads a brush's preview icon, or draws one showing its name if the preview image is missing."""
    if not os.path.isfile(image_path):

        def _draw_image() -> QImage:
            image = QImage(QSize(BRUSH_ICON_SIZE, BRUSH_ICON_SIZE), QImage.Format.Format_ARGB32_Premultiplied)
            image_bounds = QRect(QPoint(), image.size())
            text_bounds = image_bounds.adjusted(2, 2, -2, -2)
            palette = QApplication.palette()
            text_color = palette.color(palette.ColorRole.WindowText)
            font = QApplication.font()
            font.setPointSize(max_font_size(brush_name, font, text_bounds.size()))
            painter = QPainter(image)
            painter.fillRect(image_bounds, palette.color(palette.ColorRole.Window))
            painter.setPen(text_color)
            painter.drawRect(image_bounds.adjusted(0, 0, -1, -1))
            draw_text_path(create_text_path(brush_name, font, text_bounds), painter, text_color)
            painter.end()
            return image
        image_path = temp_image_path(brush_name, _draw_image)
    return QIcon(QPixmap(image_path))


class BrushList(QListWidget):
    """A wrapping list of brush icons that scrolls vertically and sizes its icons to fill each row."""

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
        self._update_cell_size()

    def add_brush(self, brush_path: str, icon: QIcon) -> QListWidgetItem:
        """Adds an icon for a brush file, with the brush name as its tooltip."""
        item = QListWidgetItem(icon, '', self)
        item.setData(BRUSH_PATH_ROLE, brush_path)
        item.setToolTip(os.path.basename(brush_path)[:-len(BRUSH_EXTENSION)])
        item.setData(Qt.ItemDataRole.AccessibleTextRole, item.toolTip())
        self._update_cell_size()
        return item

    def remove_brush(self, brush_path: str) -> None:
        """Removes a brush file's icon, if the list holds it."""
        item = self.find_brush(os.path.abspath(brush_path))
        if item is not None:
            self.takeItem(self.row(item))
            self._update_cell_size()

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
        """Returns the area brush_cell_size fills with icons: the list's size inside its frame and scroll bar.

        - The scroll bar's width is always left out, so the cell size is the same whether or not the scroll bar is
          showing. Otherwise showing it could change the cell size and hide it again.
        - One more pixel of width is left out: QListView only fits n cells in a row when the viewport is wider than n
          cells.
        """
        scroll_bar = self.verticalScrollBar()
        scroll_bar_width = 0 if scroll_bar is None else scroll_bar.sizeHint().width()
        frame = 2 * self.frameWidth()
        return QSize(self.width() - frame - scroll_bar_width - 1, self.height() - frame)

    def _update_cell_size(self) -> None:
        area = self.icon_area_size()
        cell_size = brush_cell_size(area.width(), area.height(), self.count())
        if self.gridSize().width() != cell_size:
            self.setGridSize(QSize(cell_size, cell_size))
            icon_size = cell_size - 2 * ICON_PADDING
            self.setIconSize(QSize(icon_size, icon_size))

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Resizes the icons for the new size."""
        self._update_cell_size()
        super().resizeEvent(event)

    def _hint_size(self, columns: int, rows: int) -> QSize:
        scroll_bar = self.verticalScrollBar()
        scroll_bar_width = 0 if scroll_bar is None else scroll_bar.sizeHint().width()
        frame = 2 * self.frameWidth()
        return QSize(MIN_CELL_SIZE * columns + scroll_bar_width + frame, MIN_CELL_SIZE * rows + frame)

    def sizeHint(self) -> QSize:
        """Asks for PREFERRED_ROWS rows of PREFERRED_COLUMNS minimum-size icons, and scrolls to show the rest."""
        return self._hint_size(PREFERRED_COLUMNS, PREFERRED_ROWS)

    def minimumSizeHint(self) -> QSize:
        """Asks for one minimum-size icon and the scroll bar."""
        return self._hint_size(1, 1)


class MypaintBrushPanel(QTabWidget):
    """MypaintBrushPanel selects between the MyPaint brushes, with one tab of brush icons per brush group.

    A favorites tab comes first while AppConfig's FAV_CONFIG_KEY lists any brushes. Each brush list selects the brush
    Cache holds under brush_config_key, and selecting an icon sets that key.
    """

    def __init__(self, brush_config_key: str = 'mypaint_brush', parent: Optional[QWidget] = None) -> None:
        """Loads brushes and optionally adds the widget to a parent.

        Parameters
        ----------
        brush_config_key : str
            Cache key defining the active brush path.
        parent : QWidget, optional
            Parent widget.
        """
        super().__init__(parent)
        self._brush_config_key = brush_config_key
        self._groups: list[str] = []
        self._group_dirs: dict[str, str] = {}
        self._group_orders: dict[str, list[str]] = {}
        self._pages: dict[str, BrushList] = {}
        self._icons: dict[str, QIcon] = {}
        self._read_order_file(os.path.join(BRUSH_DIR, BRUSH_CONF_FILE))
        self._setup_brush_tabs()
        self._setup_favorites_tab()
        self._show_active_brush()
        Cache().connect(self, brush_config_key, lambda _: self._show_active_brush())

    @property
    def brush_lists(self) -> dict[str, BrushList]:
        """The brush list of each tab, by tab name."""
        return dict(self._pages)

    def _setup_brush_tabs(self) -> None:
        """Reads in brush files, organizes them into tabs."""
        brush_dirs = [BRUSH_DIR]
        custom_brush_dir = AppConfig().get(AppConfig.ADDED_MYPAINT_BRUSH_DIR)
        if os.path.isdir(custom_brush_dir):
            brush_dirs.append(custom_brush_dir)
        brush_files: dict[str, list[str]] = {}
        while len(brush_dirs) > 0:
            brush_dir = brush_dirs.pop(0)
            dir_name = os.path.basename(brush_dir)
            if dir_name in self._groups:
                if self._group_dirs[dir_name] != brush_dir:
                    logger.error(f'Duplicate group {dir_name} found in both {self._group_dirs[dir_name]} and '
                                 f'{brush_dir}, the second directory will be ignored.')
                continue
            for brush_dir_file in os.listdir(brush_dir):
                full_path = os.path.join(brush_dir, brush_dir_file)
                if brush_dir_file == BRUSH_ORDER_FILE:
                    self._read_order_file(full_path)
                elif os.path.isdir(full_path):
                    brush_dirs.append(full_path)
                elif full_path.endswith(BRUSH_EXTENSION):
                    if dir_name not in brush_files:
                        brush_files[dir_name] = []
                        self._groups.append(dir_name)
                        self._group_dirs[dir_name] = brush_dir
                    brush_files[dir_name].append(brush_dir_file[:-len(BRUSH_EXTENSION)])
        for group in self._group_orders.keys():
            if group in brush_files:
                del brush_files[group]
        for group, group_brushes in brush_files.items():
            group_brushes.sort()
            self._group_orders[group] = [*group_brushes]
        for group in self._groups:
            group_dir = self._group_dirs[group]
            if not os.path.isdir(group_dir) or len(self._group_orders[group]) == 0:
                continue
            brush_list = self._create_tab(group)
            for brush_name in self._group_orders[group]:
                self._add_brush(brush_list, group, brush_name)

    def _setup_favorites_tab(self) -> None:
        """Reads favorite brushes, adds them in a new tab."""
        favorites = []
        for favorite in AppConfig().get(FAV_CONFIG_KEY):
            if '/' not in favorite:
                continue
            group, brush_name = favorite.split('/')
            if group in self._group_dirs:
                favorites.append((group, brush_name))
        if len(favorites) == 0:
            return
        brush_list = self._create_tab(FAVORITES_CATEGORY_NAME, index=0)
        self.setTabIcon(0, QIcon(ICON_PATH_FAVORITES))
        for group, brush_name in favorites:
            self._add_brush(brush_list, group, brush_name)
        self.setCurrentIndex(0)

    def _create_tab(self, tab_name: str, index: Optional[int] = None) -> BrushList:
        """Adds a new brush category tab, or returns the existing one."""
        if tab_name in self._pages:
            return self._pages[tab_name]
        brush_list = BrushList()
        self._pages[tab_name] = brush_list
        if index is None:
            self.addTab(brush_list, tab_name)
        else:
            self.insertTab(index, brush_list, tab_name)
        brush_list.itemSelectionChanged.connect(lambda: self._selection_change_slot(brush_list))
        brush_list.customContextMenuRequested.connect(lambda pos: self._menu(brush_list, pos))
        return brush_list

    def _add_brush(self, brush_list: BrushList, group: str, brush_name: str) -> None:
        group_dir = self._group_dirs[group]
        brush_path = os.path.join(group_dir, brush_name + BRUSH_EXTENSION)
        if brush_path not in self._icons:
            self._icons[brush_path] = _brush_icon(brush_name,
                                                  os.path.join(group_dir, brush_name + BRUSH_ICON_EXTENSION))
        brush_list.add_brush(brush_path, self._icons[brush_path])

    def _show_active_brush(self) -> None:
        """Selects the active brush's icon in every list that holds it, and clears selection in the others."""
        active_brush = _resolved_brush_path(Cache().get(self._brush_config_key))
        for brush_list in self._pages.values():
            item = brush_list.find_brush(active_brush)
            if item is None:
                brush_list.clearSelection()
            elif not item.isSelected():
                brush_list.setCurrentItem(item)

    def _selection_change_slot(self, brush_list: BrushList) -> None:
        selected = brush_list.selectedItems()
        if len(selected) == 0:
            return
        brush_path = selected[0].data(BRUSH_PATH_ROLE)
        if _resolved_brush_path(Cache().get(self._brush_config_key)) != os.path.abspath(brush_path):
            Cache().set(self._brush_config_key, _saved_brush_path(brush_path))

    def _menu(self, brush_list: BrushList, pos: QPoint) -> None:
        """Offers to add the brush under the cursor to favorites, or to remove it from them."""
        item = brush_list.itemAt(pos)
        if item is None:
            return
        brush_path = item.data(BRUSH_PATH_ROLE)
        is_favorite = brush_list is self._pages.get(FAVORITES_CATEGORY_NAME)
        menu = QMenu(self)
        menu.setTitle(item.toolTip())
        action = menu.addAction(REMOVE_FAVORITE_LABEL if is_favorite else ADD_FAVORITE_LABEL)
        if menu.exec(brush_list.viewport().mapToGlobal(pos)) == action:
            if is_favorite:
                self.remove_favorite(brush_path)
            else:
                self.add_favorite(brush_path)

    def add_favorite(self, brush_path: str) -> None:
        """Adds a brush to the end of the favorites tab, creating the tab if needed, and saves the favorites."""
        favorite_list = AppConfig().get(FAV_CONFIG_KEY)
        saved_name = _favorite_name(brush_path)
        if saved_name in favorite_list:
            return
        AppConfig().set(FAV_CONFIG_KEY, [*favorite_list, saved_name])
        if FAVORITES_CATEGORY_NAME not in self._pages:
            self._setup_favorites_tab()
        else:
            group, brush_name = saved_name.split('/')
            self._add_brush(self._pages[FAVORITES_CATEGORY_NAME], group, brush_name)
        self._show_active_brush()

    def remove_favorite(self, brush_path: str) -> None:
        """Removes a brush from the favorites tab and saves the favorites. The tab stays until the panel is rebuilt."""
        favorites = self._pages.get(FAVORITES_CATEGORY_NAME)
        if favorites is None:
            return
        favorites.remove_brush(brush_path)
        AppConfig().set(FAV_CONFIG_KEY, [_favorite_name(path) for path in favorites.brush_paths()])

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


def _favorite_name(brush_path: str) -> str:
    """Returns the name a brush is saved under in the favorites list: its group directory and brush name."""
    group_name = os.path.basename(os.path.dirname(brush_path))
    return f'{group_name}/{os.path.basename(brush_path)[:-len(BRUSH_EXTENSION)]}'
