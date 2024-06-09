"""
Selects between the default MyPaint brushes found in resources/brushes. This widget can only be used if a compatible
brushlib/libmypaint QT library is available, currently only true for x86_64 Linux.
"""
import os
import re
from typing import Optional, List, Dict

from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPaintEvent, QMouseEvent, QResizeEvent
from PyQt5.QtWidgets import QWidget, QTabWidget, QMenu

from src.config.application_config import AppConfig
from src.image.mypaint.mp_brush import MPBrush
from src.ui.util.geometry_utils import get_scaled_placement
from src.ui.util.screen_size import get_screen_size
from src.ui.widget.grid_container import GridContainer

MIN_COLUMNS = 2
MAX_COLUMNS = 10


class BrushPanel(QTabWidget):
    """BrushPanel selects between the default MyPaint brushes found in resources/brushes."""

    FAV_KEY = 'favorites'
    FAV_CONFIG_KEY = 'brush_favorites'

    BRUSH_DIR = './resources/brushes'
    BRUSH_CONF_FILE = 'brushes.conf'
    BRUSH_ORDER_FILE = 'order.conf'
    BRUSH_EXTENSION = '.myb'
    BRUSH_ICON_EXTENSION = '_prev.png'

    def __init__(self, config: AppConfig, brush: MPBrush, parent: Optional[QWidget] = None) -> None:
        """Loads brushes and optionally adds the widget to a parent.

        Parameters
        ----------
        config : AppConfig
            Shared config object, used to save and load favorite brushes.
        brush : MPBrush
            Brush object connected to the MyPaint canvas.
        parent : QWidget, optional
            Parent widget.
        """
        super().__init__(parent)
        self._brush = brush
        self._groups: List[str] = []
        self._group_orders: Dict[str, List[str]] = {}
        self._pages: Dict[str, GridContainer] = {}
        self._config = config
        self._read_order_file(os.path.join(BrushPanel.BRUSH_DIR, BrushPanel.BRUSH_CONF_FILE))
        self._setup_brush_tabs()
        self._setup_favorites_tab()

    def _setup_brush_tabs(self) -> None:
        """Reads in brush files, organizes them into tabs."""
        for group in os.listdir(BrushPanel.BRUSH_DIR):
            group_dir = os.path.join(BrushPanel.BRUSH_DIR, group)
            if group in self._group_orders or not os.path.isdir(group_dir):
                continue
            if self._read_order_file(os.path.join(group_dir, BrushPanel.BRUSH_ORDER_FILE)):
                continue
            # No order.conf: just read in file order
            self._groups.append(group)
            self._group_orders[group] = []
            for file in os.listdir(group_dir):
                if not file.endswith(BrushPanel.BRUSH_EXTENSION):
                    continue
                brush_name = file[:-4]
                self._group_orders[group].append(brush_name)
        for group in self._groups:
            group_dir = os.path.join(BrushPanel.BRUSH_DIR, group)
            if not os.path.isdir(group_dir):
                continue
            self._create_tab(group)
            for brush_name in self._group_orders[group]:
                brush_path = os.path.join(group_dir, brush_name + BrushPanel.BRUSH_EXTENSION)
                image_path = os.path.join(group_dir, brush_name + BrushPanel.BRUSH_ICON_EXTENSION)
                brush_icon = _IconButton(self._brush, image_path, brush_path, self._config, False)
                brush_icon.favorite_change.connect(self._add_favorite)
                self._pages[group].add_widget(brush_icon)

    def _setup_favorites_tab(self) -> None:
        """Reads favorite brushes, adds them in a new tab."""
        favorite_list = self._config.get(BrushPanel.FAV_CONFIG_KEY)
        favorite_brushes = []
        for favorite in favorite_list:
            if '/' not in favorite:
                continue
            group, brush = favorite.split('/')
            brush_path = os.path.join(BrushPanel.BRUSH_DIR, group, brush + BrushPanel.BRUSH_EXTENSION)
            image_path = os.path.join(BrushPanel.BRUSH_DIR, group, brush + BrushPanel.BRUSH_ICON_EXTENSION)
            brush_icon = _IconButton(self._brush, image_path, brush_path, self._config, True)
            brush_icon.favorite_change.connect(self._remove_favorite)
            favorite_brushes.append(brush_icon)
        if len(favorite_brushes) > 0:
            self._create_tab(BrushPanel.FAV_KEY, index=0)
            for brush_widget in favorite_brushes:
                self._pages[BrushPanel.FAV_KEY].add_widget(brush_widget)
            self.setCurrentIndex(0)

    def _create_tab(self, tab_name: str, index: Optional[int] = None) -> None:
        """Adds a new brush category tab."""
        if tab_name in self._pages:
            return
        content = GridContainer()
        self._pages[tab_name] = content
        if index is None:
            self.addTab(content, tab_name)
        else:
            self.insertTab(index, content, tab_name)

    def _save_favorite_brushes(self) -> None:
        """Saves favorite brushes to config whenever a favorite is added or removed."""
        if BrushPanel.FAV_KEY not in self._pages:
            fav_list = []
        else:
            fav_list = self._pages[BrushPanel.FAV_KEY].findChildren(_IconButton)
        self._config.set(BrushPanel.FAV_CONFIG_KEY, [brush.saved_name() for brush in fav_list])

    def _add_favorite(self, icon_button: QWidget) -> None:
        if icon_button.saved_name() in self._config.get(BrushPanel.FAV_CONFIG_KEY):
            return
        if BrushPanel.FAV_KEY not in self._layouts:
            self._create_tab(BrushPanel.FAV_KEY, index=0)

        brush_copy = icon_button.copy(True)
        self._pages[BrushPanel.FAV_KEY].add_widget(brush_copy)
        brush_copy.favorite_change.connect(self._remove_favorite)
        self._save_favorite_brushes()
        self.resizeEvent(None)

    def _remove_favorite(self, icon_button: QWidget) -> None:
        self._pages[BrushPanel.FAV_KEY].remove_widget(icon_button)
        icon_button.favorite_change.disconnect(self._remove_favorite)
        icon_button.setParent(None)
        self._save_favorite_brushes()
        self.resizeEvent(None)

    def _read_order_file(self, file_path: str) -> bool:
        if not os.path.exists(file_path):
            return False
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = [ln.strip() for ln in file.readlines()]
        for line in lines:
            group_match = re.search(r'^Group: ([^#]+)', line)
            if group_match:
                group = group_match.group(1)
                self._groups.append(group)
                self._group_orders[group] = []
                continue
            if '/' not in line:
                continue
            group, brush = line.split('/')
            if group not in self._group_orders:
                self._groups.append(group)
                self._group_orders[group] = []
            self._group_orders[group].append(brush)
        return True


class _IconButton(QWidget):
    """Button widget used to select a single brush."""

    favorite_change = pyqtSignal(QWidget)

    def __init__(self, brush: MPBrush, image_path: str, brush_path: str, config: AppConfig,
                 favorite: bool = False) -> None:
        """Initialize using paths to the brush file and icon."""
        super().__init__()
        self._brush = brush
        self._favorite = favorite
        self._brush_name = os.path.basename(brush_path)[:-4]
        self._brush_path = brush_path
        self._image_path = image_path
        self._image_rect: Optional[QRect] = None
        self._image = QPixmap(image_path)
        self._config = config
        inverted = QImage(image_path)
        inverted.invertPixels(QImage.InvertRgba)
        self._image_inverted = QPixmap.fromImage(inverted)
        self.setMinimumSize(self._image.width() // 2, self._image.height() // 2)
        self.setMaximumSize(self._image.width(), self._image.height())
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.resizeEvent(None)

        palette = self.palette()
        palette.setColor(self.backgroundRole(), Qt.red)
        self.setPalette(palette)
        self.setAutoFillBackground(True)

    def saved_name(self) -> str:
        """Returns the name used to save this brush to favorites."""
        group_name = os.path.basename(os.path.dirname(self._brush_path))
        return f'{group_name}/{self._brush_name}'

    def copy(self, favorite: bool = False) -> QWidget:
        """Creates a new IconButton with the same brush file and icon."""
        return _IconButton(self._brush, self._image_path, self._brush_path, self._config, favorite=favorite)

    def is_selected(self) -> bool:
        """Checks whether this brush is the selected brush."""
        active_brush = self._brush.path
        return active_brush is not None and active_brush == self._brush_path

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Recalculates icon bounds when the widget size changes."""
        self._image_rect = get_scaled_placement(QRect(0, 0, self.width(), self.height()), self._image.size())

    def sizeHint(self):
        """Define suggested button size based on screen size."""
        width = self._image.width()
        height = self._image.height()
        screen = get_screen_size(self)
        if screen is not None:
            width = min(width, screen.width() // 30)
            height = min(height, screen.height() // 30)
            if width < height:
                height = int(width * self._image.height() / self._image.width())
            else:
                width = int(height * self._image.width() / self._image.height())
        return QSize(width, height)

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Paints the icon image in the widget bounds, preserving aspect ratio."""
        if self._image_rect is None:
            return
        painter = QPainter(self)
        painter.fillRect(self._image_rect, Qt.GlobalColor.red)
        if self.is_selected():
            painter.drawPixmap(self._image_rect, self._image_inverted)
        else:
            painter.drawPixmap(self._image_rect, self._image)

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Load the associated brush when left-clicked."""
        if event is not None and event.button() == Qt.MouseButton.LeftButton and not self.is_selected() \
                and self._image_rect is not None and self._image_rect.contains(event.pos()):
            self._brush.load_file(self._brush_path, True)
            self._config.set(AppConfig.MYPAINT_BRUSH, self._brush_path)
            parent = self.parent()
            if isinstance(parent, QWidget):
                parent.update()

    def _menu(self, pos: QPoint) -> None:
        """Adds a menu option to add this brush to favorites or remove it from favorites."""
        menu = QMenu()
        menu.setTitle(self._brush_name)
        fav_option = menu.addAction('Remove from Favorites' if self._favorite else 'Add to Favorites')
        if fav_option is None:
            raise RuntimeError('Unable to set up brush option menu')
        fav_option.triggered.connect(lambda: self.favorite_change.emit(self))
        menu.exec_(self.mapToGlobal(pos))
