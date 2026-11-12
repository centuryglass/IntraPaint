"""Selects between the MyPaint brushes found in resources/brushes and AppConfig.ADDED_MYPAINT_BRUSH_DIR.

`MypaintBrushPanel` shows a grid of named tiles with a favorite star on each (`src.ui.panel.mypaint_brush_grid`),
under a header bar naming the active brush. Categories are a combo box in the header bar, or a list beside the grid.
An owner with a section header can host the header bar there. A compact form replaces the grid with the active brush
chip and a row of favorite thumbnails, and the chip opens the full picker in a popover. The owner picks the forms.
`BrushLibrary` reads the brush files once and can be shared between panels. The favorites list lives in AppConfig under
FAV_CONFIG_KEY, so every panel follows changes made in any other.

This widget can only be used if a compatible brushlib/libmypaint QT library is available, bundled for x86_64 Linux and
Windows.
"""
import logging
import os
import re
import weakref
from typing import Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QImage, QMouseEvent, QPainter, QPalette, QPixmap, QResizeEvent
from PySide6.QtWidgets import (QApplication, QBoxLayout, QComboBox, QFrame, QHBoxLayout, QLabel, QListWidgetItem, QMenu,
                               QSizePolicy, QToolButton, QVBoxLayout, QWidget)
from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.ui.panel.mypaint_brush_grid import (BRUSH_EXTENSION, BRUSH_PATH_ROLE, FAVORITE_ROLE, BrushList, CategoryList,
                                             StarButton, brush_category, brush_name)
from src.ui.widget.elided_label import ElidedLabel
from src.ui.widget.panel_header import PanelPopover
from src.ui.widget.panel_section import PanelSection
from src.util.layout import add_layout
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
NO_BRUSH_LABEL = _tr('No brush')
CATEGORY_TOOLTIP = _tr('Brush category')

BRUSH_DIR = f'{PROJECT_DIR}/resources/brushes'
FAV_CONFIG_KEY = 'brush_favorites'

BRUSH_CONF_FILE = 'brushes.conf'
BRUSH_ORDER_FILE = 'order.conf'
BRUSH_ICON_EXTENSION = '_prev.png'
BRUSH_ICON_SIZE = 128

CHIP_ICON_SIZE = 36
CHIP_MIN_WIDTH = 150
THUMBNAIL_SIZE = 40
THUMBNAIL_SPACING = 4
MAX_FAVORITE_THUMBNAILS = 8
POPOVER_SIZE = QSize(400, 430)

logger = logging.getLogger(__name__)


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


class FavoritesRow(QWidget):
    """A row of favorite brush thumbnails that shows as many as fit its width.

    Its minimum width is one thumbnail, so it never widens its parent past that. Its size hint holds every thumbnail.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._buttons: list[QToolButton] = []
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(THUMBNAIL_SPACING)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    @property
    def buttons(self) -> list[QToolButton]:
        """Every thumbnail, shown or not, in order."""
        return list(self._buttons)

    def set_buttons(self, buttons: list[QToolButton]) -> None:
        """Replaces the thumbnails, deleting the old ones."""
        for button in self._buttons:
            self._layout.removeWidget(button)
            button.setParent(None)
            button.deleteLater()
        self._buttons = buttons
        for button in buttons:
            self._layout.addWidget(button)
        self._show_fitting()
        self.updateGeometry()

    def _button_size(self) -> QSize:
        return self._buttons[0].sizeHint() if len(self._buttons) > 0 else QSize()

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns one thumbnail's size, or nothing while there are none."""
        return self._button_size()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the size of every thumbnail in one row."""
        size = self._button_size()
        count = len(self._buttons)
        return QSize(size.width() * count + THUMBNAIL_SPACING * max(count - 1, 0), size.height())

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:  # pylint: disable=invalid-name
        """Shows the thumbnails that fit the new width."""
        super().resizeEvent(event)
        self._show_fitting()

    def _show_fitting(self) -> None:
        width = self._button_size().width() + THUMBNAIL_SPACING
        fitting = max(1, (self.width() + THUMBNAIL_SPACING) // width) if width > THUMBNAIL_SPACING else 0
        for index, button in enumerate(self._buttons):
            button.setVisible(index < fitting)


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


class BrushHeaderBar(QWidget):
    """The active brush's name and favorite star, and the category combo box at the right.

    The name elides first, so the star and combo box stay whole.
    """

    favoriteToggled = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._name_label = ElidedLabel(parent=self)
        self._star = StarButton(self)
        self._star.clicked.connect(self.favoriteToggled)
        self._combo = QComboBox(self)
        self._combo.setToolTip(CATEGORY_TOOLTIP)
        self._combo.setAccessibleName(CATEGORY_TOOLTIP)
        self._combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._name_label)
        layout.addWidget(self._star)
        layout.addStretch(1)
        layout.addWidget(self._combo)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    @property
    def name_label(self) -> ElidedLabel:
        """The brush name."""
        return self._name_label

    @property
    def star(self) -> StarButton:
        """The favorite toggle."""
        return self._star

    @property
    def combo(self) -> QComboBox:
        """The category combo box."""
        return self._combo

    def set_brush(self, brush_path: Optional[str], favorite: bool) -> None:
        """Shows a brush's name and favorite state, or "No brush" if `brush_path` is None."""
        self._name_label.set_full_text(NO_BRUSH_LABEL if brush_path is None else brush_name(brush_path))
        self._star.setEnabled(brush_path is not None)
        self._star.setChecked(brush_path is not None and favorite)
        self.updateGeometry()


class CurrentBrushChip(QFrame):
    """Shows the active brush's preview, name and category, with a star that toggles its favorite.

    - While `popup_enabled` is set, the chip shows a drop-down arrow and emits `clicked` when pressed.
    - Its size hint fits the whole name and category. Its minimum width is CHIP_MIN_WIDTH, or its size hint while
      `keep_names_whole` is set.
    """

    clicked = Signal()
    favoriteToggled = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(CHIP_MIN_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._popup_enabled = False
        self._keep_names_whole = False
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
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.addWidget(self._icon_label)
        text_column = QVBoxLayout()
        text_column.setSpacing(0)
        add_layout(layout, text_column, 1)
        text_column.addWidget(self._name_label)
        text_column.addWidget(self._category_label)
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

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the layout's size hint widened by the name and category text, which the labels leave out so the
        chip can shrink below it."""
        hint = super().sizeHint()
        text_width = max(label.fontMetrics().horizontalAdvance(label.text())
                         for label in (self._name_label, self._category_label))
        return QSize(max(hint.width() + text_width, CHIP_MIN_WIDTH), hint.height())

    def set_keep_names_whole(self, keep_whole: bool) -> None:
        """Sets whether the chip's minimum width fits its whole name and category."""
        self._keep_names_whole = keep_whole
        self._update_minimum_width()

    def _update_minimum_width(self) -> None:
        self.setMinimumWidth(self.sizeHint().width() if self._keep_names_whole else CHIP_MIN_WIDTH)

    def set_popup_enabled(self, enabled: bool) -> None:
        """Shows the drop-down arrow and a pointing-hand cursor, or hides them."""
        self._popup_enabled = enabled
        self._arrow.setVisible(enabled)
        self._update_minimum_width()
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)

    def set_brush(self, brush_path: Optional[str], icon: Optional[QIcon], favorite: bool) -> None:
        """Shows a brush, or an empty chip if `brush_path` is None."""
        if brush_path is None or icon is None:
            self._icon_label.clear()
            self._icon_label.hide()
            self._name_label.setText(NO_BRUSH_LABEL)
            self._category_label.setText('')
            self._star.setEnabled(False)
            self._star.setChecked(False)
            self._update_minimum_width()
            return
        self._icon_label.setPixmap(icon.pixmap(CHIP_ICON_SIZE, CHIP_ICON_SIZE))
        self._icon_label.show()
        self._name_label.setText(brush_name(brush_path))
        self._category_label.setText(brush_category(brush_path))
        self._star.setEnabled(True)
        self._star.setChecked(favorite)
        self._update_minimum_width()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # pylint: disable=invalid-name
        """Emits `clicked` while the popup is enabled."""
        if self._popup_enabled and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class MypaintBrushPanel(QWidget):
    """MypaintBrushPanel selects between the MyPaint brushes with a grid of tiles, under a header bar with the active
    brush and the category combo box.

    - The categories are Favorites while AppConfig's FAV_CONFIG_KEY lists any brushes, All, and one per brush group.
    - Selecting a tile sets the brush Cache holds under brush_config_key, and the panel follows changes to that key.
    - `set_category_list` swaps the category combo box for a list beside the grid.
    - `set_header_host` moves the header bar into a section's header, or back to the top of the panel.
    - `set_compact` swaps the header bar and grid for the active brush chip and a row of favorite thumbnails, beside
      the chip or under it. The chip then opens the full picker in a popover that closes when a brush is picked.
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
        self._beside = False
        self._category_list_shown = False
        # The section hosting the header bar is usually an ancestor, so it is held weakly to avoid a reference cycle:
        self._header_host_ref: Optional[weakref.ref[PanelSection]] = None
        self._category: Optional[str] = None
        self._category_names_shown: list[str] = []
        self._popover: Optional[PanelPopover] = None

        self._chip = CurrentBrushChip(self)
        self._chip.favoriteToggled.connect(self._toggle_active_favorite)
        self._chip.clicked.connect(self._show_popover)
        self._favorites_row = FavoritesRow(self)
        self._header_bar = BrushHeaderBar(self)
        self._header_bar.favoriteToggled.connect(self._toggle_active_favorite)
        self._header_bar.combo.activated.connect(self._combo_activated)
        layout = self._layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._header_bar)
        self._top_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        self._top_layout.setContentsMargins(0, 0, 0, 0)
        add_layout(layout, self._top_layout)
        self._top_layout.addWidget(self._chip)
        self._top_layout.addWidget(self._favorites_row)

        # The grid row is a widget, since `fresh_minimum_size` doesn't refresh a nested layout's cached minimum size:
        self._grid_row = QWidget(self)
        self._category_list = CategoryList(self._grid_row)
        self._category_list.itemClicked.connect(self._category_list_clicked)
        self._grid = BrushList(self._grid_row)
        self._grid.itemSelectionChanged.connect(self._selection_change_slot)
        self._grid.customContextMenuRequested.connect(self._menu)
        self._grid.favoriteToggled.connect(self.toggle_favorite)
        grid_row_layout = QHBoxLayout(self._grid_row)
        grid_row_layout.setContentsMargins(0, 0, 0, 0)
        grid_row_layout.addWidget(self._category_list)
        grid_row_layout.addWidget(self._grid, stretch=1)
        layout.addWidget(self._grid_row, stretch=1)

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
        """The active brush chip, shown in the compact form."""
        return self._chip

    @property
    def header_bar(self) -> BrushHeaderBar:
        """The active brush's name and star and the category combo box, shown in the full form."""
        return self._header_bar

    @property
    def grid(self) -> BrushList:
        """The grid of brush tiles for the chosen category."""
        return self._grid

    @property
    def category_combo(self) -> QComboBox:
        """The category combo box in the header bar."""
        return self._header_bar.combo

    @property
    def category_list(self) -> CategoryList:
        """The category list beside the grid."""
        return self._category_list

    @property
    def category(self) -> Optional[str]:
        """The name of the chosen category."""
        return self._category

    @property
    def category_names(self) -> list[str]:
        """The names of the categories, in display order."""
        return list(self._category_names_shown)

    @property
    def favorites_row(self) -> FavoritesRow:
        """The favorite thumbnails shown in the compact form."""
        return self._favorites_row

    @property
    def thumbnails(self) -> list[QToolButton]:
        """Every favorite thumbnail, shown or not."""
        return self._favorites_row.buttons

    @property
    def compact(self) -> bool:
        """Whether the compact form is showing."""
        return self._compact

    @property
    def category_list_shown(self) -> bool:
        """Whether the categories are a list beside the grid. Otherwise they are the header bar's combo box."""
        return self._category_list_shown

    @property
    def popover(self) -> Optional[PanelPopover]:
        """The popover holding the full picker, once it has been opened."""
        return self._popover

    @property
    def active_brush_path(self) -> Optional[str]:
        """The absolute path of the active brush, or None if Cache holds none that exists."""
        return _resolved_brush_path(Cache().get(self._brush_config_key))

    def set_compact(self, compact: bool, beside: bool = False) -> None:
        """Switches between the full picker and the chip with a row of favorites, which goes beside the chip if
        `beside` is set and under it otherwise."""
        if compact != self._compact or beside != self._beside:
            self._compact = compact
            self._beside = beside
            self._apply_form()

    def set_category_list(self, shown: bool) -> None:
        """Shows the categories as a list beside the grid, or as the header bar's combo box."""
        if shown != self._category_list_shown:
            self._category_list_shown = shown
            self._apply_form()

    def set_header_host(self, section: Optional[PanelSection]) -> None:
        """Moves the header bar after a section's title, or back to the top of the panel with None. While the panel is
        compact the header bar stays in the panel, hidden."""
        host = None if self._compact else section
        current = self._header_host()
        if host is current:
            return
        if current is not None:
            current.set_title_widget(None)
        self._header_host_ref = None if host is None else weakref.ref(host)
        if host is None:
            self._header_bar.setParent(self)
            self._layout.insertWidget(0, self._header_bar)
        else:
            self._layout.removeWidget(self._header_bar)
            host.set_title_widget(self._header_bar)
        self._apply_form()

    def _header_host(self) -> Optional[PanelSection]:
        return None if self._header_host_ref is None else self._header_host_ref()

    def _apply_form(self) -> None:
        full = not self._compact
        if self._compact and self._header_host() is not None:
            self.set_header_host(None)
            return
        if self._header_host() is None:
            self._header_bar.setVisible(full)
        self._header_bar.combo.setVisible(not self._category_list_shown)
        self._category_list.setVisible(self._category_list_shown)
        self._grid_row.setVisible(full)
        self._chip.setVisible(self._compact)
        self._favorites_row.setVisible(self._compact and len(self.thumbnails) > 0)
        self._chip.set_popup_enabled(self._compact)
        beside = self._compact and self._beside
        self._top_layout.setDirection(QBoxLayout.Direction.LeftToRight if beside else QBoxLayout.Direction.TopToBottom)
        # Beside the chip, the favorites take the row's spare width, and drop off before the name is cut short:
        self._top_layout.setStretchFactor(self._favorites_row, 1 if beside else 0)
        self._chip.set_keep_names_whole(beside)
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
        self._category_names_shown = names
        combo = self._header_bar.combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(names)
        combo.blockSignals(False)
        self._category_list.set_names(names)
        self._show_category()
        self._fill_grid()

    def _show_category(self) -> None:
        """Marks the chosen category in the combo box and the list."""
        index = self._category_names_shown.index(self._category) if self._category in self._category_names_shown \
            else -1
        combo = self._header_bar.combo
        combo.blockSignals(True)
        combo.setCurrentIndex(index)
        combo.blockSignals(False)
        self._category_list.blockSignals(True)
        self._category_list.setCurrentRow(index)
        self._category_list.blockSignals(False)

    def _category_list_clicked(self, item: QListWidgetItem) -> None:
        self.set_category(item.text())

    def _combo_activated(self, index: int) -> None:
        if 0 <= index < len(self._category_names_shown):
            self.set_category(self._category_names_shown[index])

    def set_category(self, category: str) -> None:
        """Shows the brushes of a category."""
        if category not in self._category_names_shown:
            return
        self._category = category
        self._show_category()
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
        self._header_bar.set_brush(active_brush, active_brush in favorites)
        for button in self.thumbnails:
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
        """Updates the categories, tiles, stars and thumbnails after the favorites list changed."""
        self._rebuild_categories()
        self._rebuild_thumbnails()

    def _rebuild_thumbnails(self) -> None:
        buttons = []
        for path in self._library.favorite_paths()[:MAX_FAVORITE_THUMBNAILS]:
            button = QToolButton(self._favorites_row)
            button.setIcon(self._library.icon(path))
            button.setIconSize(QSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE))
            button.setCheckable(True)
            button.setToolTip(brush_name(path))
            button.setAccessibleName(brush_name(path))
            button.setProperty('brush_path', path)
            button.clicked.connect(lambda _checked=False, chosen=path: self._thumbnail_clicked(chosen))
            buttons.append(button)
        self._favorites_row.set_buttons(buttons)
        self._favorites_row.setVisible(self._compact and len(buttons) > 0)
        self._show_active_brush()

    def _thumbnail_clicked(self, brush_path: str) -> None:
        self._choose_brush(brush_path)
        self._show_active_brush()

    # -----------------------------------------------------------------------------------------------------------------
    # Popover
    # -----------------------------------------------------------------------------------------------------------------

    def _show_popover(self) -> None:
        """Opens the full picker by the chip: under it, or above it when the screen has more room there."""
        if self._popover is None:
            self._popover = PanelPopover(self)
            picker = MypaintBrushPanel(self._brush_config_key, library=self._library)
            picker.setFixedWidth(POPOVER_SIZE.width())
            picker.brush_picked.connect(self._popover.hide)
            self._popover.set_content(picker)
        margins = self._popover.layout().contentsMargins()
        self._popover.popup_below(self._chip, align_left=True,
                                  height=POPOVER_SIZE.height() + margins.top() + margins.bottom())
