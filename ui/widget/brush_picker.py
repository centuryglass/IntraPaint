"""
Selects between the default mypaint brushes found in resources/brushes. This widget can only be used if a compatible
brushlib/libmypaint QT library is available, currently only true for x86_64 Linux.
"""
import os
import re
from PyQt5.QtWidgets import QWidget, QTabWidget, QGridLayout, QScrollArea, QSizePolicy, QMenu
from PyQt5.QtGui import QPixmap, QImage, QPainter
from PyQt5.QtCore import Qt, QRect, pyqtSignal
from brushlib import MPBrushLib as brushlib
from ui.util.get_scaled_placement import get_scaled_placement

class BrushPicker(QTabWidget):
    """BrushPicker elects between the default mypaint brushes found in resources/brushes."""

    FAV_KEY = 'favorites'
    FAV_CONFIG_KEY = 'brush_favorites'

    BRUSH_DIR = './resources/brushes'
    BRUSH_CONF_FILE = 'brushes.conf'
    BRUSH_ORDER_FILE = 'order.conf'
    BRUSH_EXTENSION = '.myb'
    BRUSH_ICON_EXTENSION = '_prev.png'

    def __init__(self, config, parent=None):
        """Loads brushes and optionally adds the widget to a parent.

        Parameters
        ----------
        config : data_model.Config
            Shared config object, used to save and load favorite brushes.
        parent : QWidget, optional
            Optional parent widget.
        """
        super().__init__(parent)
        self._groups = []
        self._group_orders = {}
        self._layouts = {}
        self._pages = {}
        self._config = config
        self._read_order_file(os.path.join(BrushPicker.BRUSH_DIR, BrushPicker.BRUSH_CONF_FILE))
        # scan for added groups:
        for group in os.listdir(BrushPicker.BRUSH_DIR):
            group_dir = os.path.join(BrushPicker.BRUSH_DIR, group)
            if group in self._group_orders or not os.path.isdir(group_dir):
                continue
            if self._read_order_file(os.path.join(group_dir, BrushPicker.BRUSH_ORDER_FILE)):
                continue
            # No order.conf: just read in file order
            self._groups.append(group)
            self._group_orders[group] = []
            for file in os.listdir(group_dir):
                if not file.endswith(BrushPicker.BRUSH_EXTENSION):
                    continue
                brush_name = file[:-4]
                self._group_orders[group].append(brush_name)
        for group in self._groups:
            group_dir = os.path.join(BrushPicker.BRUSH_DIR, group)
            if not os.path.isdir(group_dir):
                continue
            self._create_tab(group)
            group_layout = self._layouts[group]
            for x, y, brush in _GridIter(self._group_orders[group]):
                brush_path = os.path.join(group_dir, brush + BrushPicker.BRUSH_EXTENSION)
                image_path = os.path.join(group_dir, brush + BrushPicker.BRUSH_ICON_EXTENSION)
                brush_icon = _IconButton(image_path, brush_path, self._config, False)

                brush_icon.favorite_change.connect(self._add_favorite)
                group_layout.addWidget(brush_icon, y, x)
        favorite_list = config.get(BrushPicker.FAV_CONFIG_KEY)
        favorite_brushes = []
        for favorite in favorite_list:
            if '/' not in favorite:
                continue
            group, brush = favorite.split('/')
            brush_path = os.path.join(BrushPicker.BRUSH_DIR, group, brush + BrushPicker.BRUSH_EXTENSION)
            image_path = os.path.join(BrushPicker.BRUSH_DIR, group, brush + BrushPicker.BRUSH_ICON_EXTENSION)
            brush_icon = _IconButton(image_path, brush_path, self._config, True)
            brush_icon.favorite_change.connect(self._remove_favorite)
            favorite_brushes.append(brush_icon)
        if len(favorite_brushes) > 0:
            self._create_tab(BrushPicker.FAV_KEY, index=0)
            for x, y, brush in _GridIter(favorite_brushes):
                self._layouts[BrushPicker.FAV_KEY].addWidget(brush, y, x)


    def _create_tab(self, tab_name, index=None):
        """Adds a new brush category tab."""
        if tab_name in self._layouts:
            return
        tab = QScrollArea(self)
        tab.setWidgetResizable(True)
        content = QWidget(tab)
        tab.setWidget(content)
        layout = QGridLayout()
        content.setLayout(layout)
        self._pages[tab_name] = content
        self._layouts[tab_name] = layout
        if index is None:
            self.addTab(tab, tab_name)
        else:
            self.insertTab(index, tab, tab_name)


    def _get_favorite_brush_widgets(self):
        """Loads favorite brushes from config."""
        fav_list = []
        layout = self._layouts[BrushPicker.FAV_KEY]
        for row in range(layout.rowCount()):
            for col in range(layout.columnCount()):
                item = layout.itemAtPosition(row, col)
                if item is not None and item.widget() is not None:
                    fav_list.append(item.widget())
        return fav_list


    def _save_favorite_brushes(self, fav_list):
        """Saves favorite brushes to config whenever a favorite is added or removed."""
        self._config.set(BrushPicker.FAV_CONFIG_KEY, [brush.saved_name() for brush in fav_list])


    def _add_favorite(self, icon_button):
        if icon_button.saved_name() in self._config.get(BrushPicker.FAV_CONFIG_KEY):
            return
        if BrushPicker.FAV_KEY not in self._layouts:
            self._create_tab(BrushPicker.FAV_KEY, index=0)

        fav_list = self._get_favorite_brush_widgets()
        fav_list.append(icon_button.copy(True))
        for x, y, brush in _GridIter(fav_list, len(fav_list) - 1):
            self._layouts[BrushPicker.FAV_KEY].addWidget(brush, y, x)
            brush.favorite_change.connect(self._remove_favorite)
        self._save_favorite_brushes(fav_list)
        self.update()


    def _remove_favorite(self, icon_button):
        fav_list = self._get_favorite_brush_widgets()
        fav_list.remove(icon_button)
        self._layouts[BrushPicker.FAV_KEY].removeWidget(icon_button)
        icon_button.setParent(None)
        for brush in fav_list:
            self._layouts[BrushPicker.FAV_KEY].removeWidget(brush)
        for x, y, brush in _GridIter(fav_list):
            self._layouts[BrushPicker.FAV_KEY].addWidget(brush, y, x)
        self._save_favorite_brushes(fav_list)
        self.update()


    def _read_order_file(self, file_path):
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

    def __init__(self, imagepath, brushpath, config, favorite=False):
        """Initialize using paths to the brush file and icon."""
        super().__init__()
        self._favorite = favorite
        self._brushname = os.path.basename(brushpath)[:-4]
        self._brushpath = brushpath
        self._imagepath = imagepath
        self._image_rect = None
        self._image = QPixmap(imagepath)
        self._config = config
        inverted = QImage(imagepath)
        inverted.invertPixels(QImage.InvertRgba)
        self._image_inverted = QPixmap.fromImage(inverted)
        size_policy = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        size_policy.setWidthForHeight(True)
        self.setSizePolicy(size_policy)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.resizeEvent(None)

    def saved_name(self):
        """Returns the name used to save this brush to favorites."""
        group_name = os.path.basename(os.path.dirname(self._brushpath))
        return f'{group_name}/{self._brushname}'

    def copy(self, favorite=False):
        """Creates a new IconButton with the same brush file and icon."""
        return _IconButton(self._imagepath, self._brushpath, self._config, favorite=favorite)

    def sizeHint(self):
        """Set ideal size based on the brush icon size."""
        return self._image.size()

    def is_selected(self):
        """Checks whether this brush is the selected brush."""
        active_brush = brushlib.get_active_brush()
        return active_brush is not None and active_brush == self._brushpath

    def resizeEvent(self, unused_event):
        """Recalculates icon bounds when the widget size changes."""
        self._image_rect = get_scaled_placement(QRect(0, 0, self.width(), self.height()), self._image.size())

    def paintEvent(self, unused_event):
        """Paints the icon image in the widget bounds, preserving aspect ratio."""
        painter = QPainter(self)
        painter.fillRect(self._image_rect, Qt.red)
        if self.is_selected():
            painter.drawPixmap(self._image_rect, self._image_inverted)
        else:
            painter.drawPixmap(self._image_rect, self._image)

    def mousePressEvent(self, event):
        """Load the associated brush when left-clicked."""
        if event.button() == Qt.LeftButton and not self.is_selected() and self._image_rect.contains(event.pos()):
            brushlib.load_brush(self._brushpath)
            self.parent().update()

    def _menu(self, pos):
        """Adds a menu option to add this brush to favorites or remove it from favorites."""
        menu = QMenu()
        menu.setTitle(self._brushname)
        fav_option = menu.addAction('Remove from Favorites' if self._favorite else 'Add to Favorites')
        fav_option.triggered.connect(lambda: self.favorite_change.emit(self))
        menu.exec_(self.mapToGlobal(pos))


class _GridIter():
    """Iterates through brush grid positions and list items."""
    WIDTH = 5

    def __init__(self, item_list, i=0):
        """Sets the iterated list and initial list index."""
        self._list = item_list
        self._i = i
        self._x = 0
        self._y = 0

    def __iter__(self):
        self._x = self._i % _GridIter.WIDTH
        self._y = self._i // _GridIter.WIDTH
        return self

    def __next__(self):
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
