"""
Selects between the default MyPaint brushes found in resources/brushes. This widget can only be used if a compatible
brushlib/libmypaint QT library is available, currently only true for x86_64 Linux.
"""
import logging
import os
import re
from typing import Optional, cast

from PySide6.QtCore import Qt, QRect, QPoint, Signal, QSize
from PySide6.QtGui import QPixmap, QImage, QPainter, QPaintEvent, QMouseEvent, QResizeEvent, QIcon
from PySide6.QtWidgets import QWidget, QTabWidget, QMenu, QSizePolicy, QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.ui.layout.grid_container import GridContainer
from src.util.visual.display_size import get_window_size
from src.util.visual.geometry_utils import get_scaled_placement
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.image_utils import temp_image_path
from src.util.visual.text_drawing_utils import max_font_size, create_text_path, draw_text_path

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.mypaint_brush_panel'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


FAVORITES_CATEGORY_NAME = _tr('favorites')

BRUSH_DIR = f'{PROJECT_DIR}/resources/brushes'
ICON_PATH_FAVORITES = f'{PROJECT_DIR}/resources/icons/tabs/star.svg'
FAV_CONFIG_KEY = 'brush_favorites'

BRUSH_CONF_FILE = 'brushes.conf'
BRUSH_ORDER_FILE = 'order.conf'
BRUSH_EXTENSION = '.myb'
BRUSH_ICON_EXTENSION = '_prev.png'
BRUSH_ICON_SIZE = 128

logger = logging.getLogger(__name__)


class MypaintBrushPanel(QTabWidget):
    """MypaintBrushPanel selects between the default MyPaint brushes found in resources/brushes."""

    def __init__(self, brush_config_key: str = 'mypaint_brush', parent: Optional[QWidget] = None) -> None:
        """Loads brushes and optionally adds the widget to a parent.

        Parameters
        ----------
        brush_config_key : str
            Config key defining the active brush path.
        parent : QWidget, optional
            Parent widget.
        """
        super().__init__(parent)
        self._brush_config_key = brush_config_key
        self._groups: list[str] = []
        self._group_dirs: dict[str, str] = {}
        self._group_orders: dict[str, list[str]] = {}
        self._pages: dict[str, GridContainer] = {}
        self._read_order_file(os.path.join(BRUSH_DIR, BRUSH_CONF_FILE))
        self._setup_brush_tabs()
        self._setup_favorites_tab()

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
                    if brush_dir not in brush_files:
                        brush_files[dir_name] = []
                        self._groups.append(dir_name)
                        self._group_dirs[dir_name] = brush_dir
                    brush_files[dir_name].append(brush_dir_file[:-len(BRUSH_EXTENSION)])
        for group in self._group_orders.keys():
            if group in brush_files:
                del brush_files[group]
        for group, group_brushes in brush_files.items():
            group_brushes.sort()
            self._group_orders[group] = group_brushes
        for group in self._groups:
            group_dir = self._group_dirs[group]
            if not os.path.isdir(group_dir) or len(self._group_orders[group]) == 0:
                continue
            self._create_tab(group)
            for brush_name in self._group_orders[group]:
                brush_path = os.path.join(group_dir, brush_name + BRUSH_EXTENSION)
                image_path = os.path.join(group_dir, brush_name + BRUSH_ICON_EXTENSION)
                brush_icon = _IconButton(self._brush_config_key, image_path, brush_path, False)
                brush_icon.favorite_change.connect(self._add_favorite)
                self._pages[group].add_widget(brush_icon)

    def _setup_favorites_tab(self) -> None:
        """Reads favorite brushes, adds them in a new tab."""
        favorite_list = AppConfig().get(FAV_CONFIG_KEY)
        favorite_brushes = []
        for favorite in favorite_list:
            if '/' not in favorite:
                continue
            group, brush = favorite.split('/')
            brush_path = os.path.join(self._group_dirs[group], brush + BRUSH_EXTENSION)
            image_path = os.path.join(self._group_dirs[group], brush + BRUSH_ICON_EXTENSION)
            brush_icon = _IconButton(self._brush_config_key, image_path, brush_path, True)
            brush_icon.favorite_change.connect(self._remove_favorite)
            favorite_brushes.append(brush_icon)
        if len(favorite_brushes) > 0:
            self._create_tab(FAVORITES_CATEGORY_NAME, index=0)
            self.setTabIcon(0, QIcon(ICON_PATH_FAVORITES))
            for brush_widget in favorite_brushes:
                self._pages[FAVORITES_CATEGORY_NAME].add_widget(brush_widget)
            self.setCurrentIndex(0)

    def _create_tab(self, tab_name: str, index: Optional[int] = None) -> None:
        """Adds a new brush category tab."""
        if tab_name in self._pages:
            return
        content = GridContainer()
        content.fill_horizontal = True
        self._pages[tab_name] = content
        if index is None:
            self.addTab(content, tab_name)
        else:
            self.insertTab(index, content, tab_name)
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _save_favorite_brushes(self) -> None:
        """Saves favorite brushes to config whenever a favorite is added or removed."""
        if FAVORITES_CATEGORY_NAME not in self._pages:
            fav_list = []
        else:
            fav_list = self._pages[FAVORITES_CATEGORY_NAME].findChildren(_IconButton)
        AppConfig().set(FAV_CONFIG_KEY, [brush.saved_name() for brush in fav_list])

    def _add_favorite(self, icon_button: '_IconButton') -> None:
        favorite_list = AppConfig().get(FAV_CONFIG_KEY)
        assert isinstance(favorite_list, list)
        if icon_button.saved_name() in favorite_list:
            return
        if FAVORITES_CATEGORY_NAME not in self._pages:
            favorite_list.append(icon_button.saved_name())
            AppConfig().set(FAV_CONFIG_KEY, favorite_list)
            self._setup_favorites_tab()
        else:
            brush_copy = cast(_IconButton, icon_button.copy(True))
            self._pages[FAVORITES_CATEGORY_NAME].add_widget(brush_copy)
            brush_copy.favorite_change.connect(self._remove_favorite)
            self._save_favorite_brushes()
        self.update()

    def _remove_favorite(self, icon_button: '_IconButton') -> None:
        self._pages[FAVORITES_CATEGORY_NAME].remove_widget(icon_button)
        icon_button.favorite_change.disconnect(self._remove_favorite)
        icon_button.setParent(None)
        self._save_favorite_brushes()
        self.update()

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


class _IconButton(QWidget):
    """Button widget used to select a single brush."""

    favorite_change = Signal(QWidget)

    def __init__(self, brush_config_key, image_path: str, brush_path: str, favorite: bool = False) -> None:
        """Initialize using paths to the brush file and icon."""
        super().__init__()
        self._brush_config_key = brush_config_key
        self._favorite = favorite
        self._brush_name = os.path.basename(brush_path)[:-4]
        self._brush_path = brush_path
        if not os.path.isfile(image_path):

            def _draw_image() -> QImage:

                image = QImage(QSize(BRUSH_ICON_SIZE, BRUSH_ICON_SIZE), QImage.Format.Format_ARGB32_Premultiplied)
                image_bounds = QRect(QPoint(), image.size())
                text_bounds = image_bounds.adjusted(2, 2, -2, -2)
                palette = self.palette()
                bg_color = palette.color(self.backgroundRole())
                text_color = palette.color(self.foregroundRole())
                font = self.font()
                pt_size = max_font_size(self._brush_name, font, text_bounds.size())
                font.setPointSize(pt_size)
                painter = QPainter(image)
                painter.fillRect(image_bounds, bg_color)
                painter.setPen(text_color)
                painter.drawRect(image_bounds.adjusted(0, 0, -1, -1))
                text_path = create_text_path(self._brush_name, font, text_bounds)
                draw_text_path(text_path, painter, text_color)
                painter.end()
                return image
            image_path = temp_image_path(self._brush_name, _draw_image)
            assert os.path.isfile(image_path)
        self._image_path = image_path

        self._image_rect: Optional[QRect] = None
        self._image = QIcon(QPixmap(image_path))
        inverted = QImage(image_path)
        inverted.invertPixels(QImage.InvertMode.InvertRgb)
        self._image_inverted = QIcon(QPixmap.fromImage(inverted))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setToolTip(self._brush_name)
        self.customContextMenuRequested.connect(self._menu)
        self.resizeEvent(None)

    def _get_pixmap(self) -> QPixmap:
        window_size = get_window_size()
        min_dim = min(window_size.width(), window_size.height())
        icon = self._image if not self.is_selected() else self._image_inverted
        if min_dim > 1600:
            size = 128
        elif min_dim > 1000:
            size = 64
        else:
            size = 48
        return icon.pixmap(size)

    def saved_name(self) -> str:
        """Returns the name used to save this brush to favorites."""
        group_name = os.path.basename(os.path.dirname(self._brush_path))
        return f'{group_name}/{self._brush_name}'

    def copy(self, favorite: bool = False) -> QWidget:
        """Creates a new IconButton with the same brush file and icon."""
        return _IconButton(self._brush_config_key, self._image_path, self._brush_path, favorite=favorite)

    def is_selected(self) -> bool:
        """Checks whether this brush is the selected brush."""
        active_brush: Optional[str] = f'{PROJECT_DIR}/{Cache().get(self._brush_config_key)}'
        if active_brush is not None and not os.path.isfile(active_brush):
            active_brush = None
        return active_brush is not None and os.path.abspath(active_brush) == os.path.abspath(self._brush_path)

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Recalculates icon bounds when the widget size changes."""
        size = self.sizeHint()
        self._image_rect = get_scaled_placement(self.size(), size)

    def sizeHint(self):
        """Define suggested button size based on pixmap size."""
        return self._get_pixmap().size()

    def minimumSizeHint(self):
        """Define suggested button size based on pixmap size."""
        return self._get_pixmap().size()

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Paints the icon image in the widget bounds, preserving aspect ratio."""
        if self._image_rect is None:
            return
        painter = QPainter(self)
        pixmap = self._get_pixmap()
        painter.drawPixmap(self._image_rect, pixmap, QRect(QPoint(), pixmap.size()))

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Load the associated brush when left-clicked."""
        if event is not None and event.button() == Qt.MouseButton.LeftButton and not self.is_selected() \
                and self._image_rect is not None and self._image_rect.contains(event.pos()):
            brush_path = self._brush_path
            if brush_path.startswith(PROJECT_DIR):
                brush_path = brush_path[len(PROJECT_DIR) + 1:]
            Cache().set(self._brush_config_key, brush_path)
            parent = self.parent()
            if parent is not None:
                brush_icon_buttons = parent.findChildren(_IconButton)
                for brush in brush_icon_buttons:
                    brush.update()

    def _menu(self, pos: QPoint) -> None:
        """Adds a menu option to add this brush to favorites or remove it from favorites."""
        menu = QMenu()
        menu.setTitle(self._brush_name)
        fav_option = menu.addAction('Remove from Favorites' if self._favorite else 'Add to Favorites')
        if fav_option is None:
            raise RuntimeError('Unable to set up brush option menu')
        fav_option.triggered.connect(lambda: self.favorite_change.emit(self))
        menu.exec(self.mapToGlobal(pos))
