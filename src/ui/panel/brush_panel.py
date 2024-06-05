"""
Selects between the default MyPaint brushes found in resources/brushes. This widget can only be used if a compatible
brushlib/libmypaint QT library is available, currently only true for x86_64 Linux.
"""
import os
import re
from typing import Optional, Any

from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPaintEvent, QMouseEvent, QResizeEvent
from PyQt5.QtWidgets import QWidget, QTabWidget, QGridLayout, QScrollArea, QSizePolicy, QMenu

from src.config.application_config import AppConfig
from src.image.canvas.mypaint.mp_brush import MPBrush
from src.ui.util.geometry_utils import get_scaled_placement
from src.ui.util.screen_size import screen_size


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
        self._groups: list[str] = []
        self._group_orders: dict[str, list[str]] = {}
        self._layouts: dict[str, QGridLayout] = {}
        self._pages: dict[str, QWidget] = {}
        self._config = config
        self._read_order_file(os.path.join(BrushPanel.BRUSH_DIR, BrushPanel.BRUSH_CONF_FILE))
        self._setup_brush_tabs()
        self._setup_favorites_tab()

    def sizeHint(self) -> QSize:
        screen = screen_size(self)
        if screen is None:
            return super().sizeHint()
        return QSize(screen.width() // 5, screen.height() // 5)

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
            group_layout = self._layouts[group]
            for x, y, brush in _GridIter(self._group_orders[group]):
                brush_path = os.path.join(group_dir, brush + BrushPanel.BRUSH_EXTENSION)
                image_path = os.path.join(group_dir, brush + BrushPanel.BRUSH_ICON_EXTENSION)
                brush_icon = _IconButton(self._brush, image_path, brush_path, self._config, False)

                brush_icon.favorite_change.connect(self._add_favorite)
                group_layout.addWidget(brush_icon, y, x)

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
            for x, y, brush in _GridIter(favorite_brushes):
                self._layouts[BrushPanel.FAV_KEY].addWidget(brush, y, x)
            self.setCurrentIndex(0)

    def _create_tab(self, tab_name: str, index: Optional[int] = None) -> None:
        """Adds a new brush category tab."""
        if tab_name in self._layouts:
            return
        tab = QScrollArea(self)
        tab.setWidgetResizable(True)
        tab.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        content = QWidget(tab)
        content.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding))

        tab.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding))
        tab.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        tab.setWidget(content)
        layout = QGridLayout()
        layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        content.setLayout(layout)
        self._pages[tab_name] = content
        self._layouts[tab_name] = layout
        if index is None:
            self.addTab(tab, tab_name)
        else:
            self.insertTab(index, tab, tab_name)

    def _get_favorite_brush_widgets(self) -> list[QWidget]:
        """Loads favorite brushes from config."""
        fav_list = []
        layout = self._layouts[BrushPanel.FAV_KEY]
        for row in range(layout.rowCount()):
            for col in range(layout.columnCount()):
                item = layout.itemAtPosition(row, col)
                if item is not None:
                    brush = item.widget()
                    if brush is not None:
                        fav_list.append(brush)
        return [brush for brush in fav_list if brush is not None]

    def _save_favorite_brushes(self, fav_list: list[QWidget]) -> None:
        """Saves favorite brushes to config whenever a favorite is added or removed."""
        self._config.set(BrushPanel.FAV_CONFIG_KEY, [brush.saved_name() for brush in fav_list])

    def _add_favorite(self, icon_button: QWidget) -> None:
        if icon_button.saved_name() in self._config.get(BrushPanel.FAV_CONFIG_KEY):
            return
        if BrushPanel.FAV_KEY not in self._layouts:
            self._create_tab(BrushPanel.FAV_KEY, index=0)

        fav_list = self._get_favorite_brush_widgets()
        fav_list.append(icon_button.copy(True))
        for x, y, brush in _GridIter(fav_list, len(fav_list) - 1):
            self._layouts[BrushPanel.FAV_KEY].addWidget(brush, y, x)
            brush.favorite_change.connect(self._remove_favorite)
        self._save_favorite_brushes(fav_list)
        self.update()

    def _remove_favorite(self, icon_button: QWidget) -> None:
        fav_list = self._get_favorite_brush_widgets()
        fav_list.remove(icon_button)
        self._layouts[BrushPanel.FAV_KEY].removeWidget(icon_button)
        icon_button.setParent(None)
        for brush in fav_list:
            self._layouts[BrushPanel.FAV_KEY].removeWidget(brush)
        for x, y, brush in _GridIter(fav_list):
            self._layouts[BrushPanel.FAV_KEY].addWidget(brush, y, x)
        self._save_favorite_brushes(fav_list)
        self.update()

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
        size_policy = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        size_policy.setWidthForHeight(True)
        self.setSizePolicy(size_policy)
        self.setMinimumSize(self._image.width() // 2, self._image.height() // 2)
        self.setMaximumSize(self._image.width(), self._image.height())
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.resizeEvent(None)

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
        width = self._image.width()
        height = self._image.height()
        screen = screen_size(self)
        if screen is not None:
            width = min(width, screen.width() // 50)
            height = min(height, screen.height() // 50)
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


class _GridIter:
    """Iterates through brush grid positions and list items."""
    WIDTH = 5

    def __init__(self, item_list: list[Any], i: int = 0) -> None:
        """Sets the iterated list and initial list index."""
        self._list = item_list
        self._i = i
        self._x = 0
        self._y = 0

    def __iter__(self) -> Any:
        self._x = self._i % _GridIter.WIDTH
        self._y = self._i // _GridIter.WIDTH
        return self

    def __next__(self) -> tuple[int, int, Any]:
        """returns the next column, row, list item."""
        x = self._x
        y = self._y
        i = x + y * _GridIter.WIDTH
        if i >= len(self._list):
            raise StopIteration
        self._x += 1
        if self._x >= _GridIter.WIDTH:
            self._y += 1
            self._x = 0
        return x, y, self._list[i]
