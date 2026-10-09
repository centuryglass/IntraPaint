"""Tests MypaintBrushPanel's icon sizing, brush selection and favorites, and how MyPaintBrushToolPanel sizes it."""
import math
import os
import sys

from PySide6.QtCore import QSize, QRect, QPoint
from PySide6.QtWidgets import QApplication, QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.ui.panel.mypaint_brush_panel import (MypaintBrushPanel, BrushList, brush_cell_size, MIN_CELL_SIZE,
                                              MAX_CELL_SIZE, FAVORITES_CATEGORY_NAME, FAV_CONFIG_KEY, BRUSH_DIR,
                                              BRUSH_PATH_ROLE)
from src.ui.panel.tool_control_panels.mypaint_brush_tool_panel import MyPaintBrushToolPanel
from src.util.shared_constants import PROJECT_DIR
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

BRUSH_KEY = 'mypaint_brush'
PENCIL_PATH = os.path.join(BRUSH_DIR, 'classic', 'pencil.myb')
CHARCOAL_PATH = os.path.join(BRUSH_DIR, 'classic', 'charcoal.myb')


class BrushCellSizeTest(IntraPaintTestCase):
    """brush_cell_size shows every icon as large as it can, or fills each row when the icons need to scroll."""

    def test_all_icons_fit_at_largest_size(self) -> None:
        """When the icons fit without scrolling, they get the largest size that fits, up to MAX_CELL_SIZE."""
        for width, height, count in ((400, 1200, 20), (1600, 110, 20), (250, 1200, 21), (2000, 2000, 3)):
            with self.subTest(width=width, height=height, count=count):
                cell = brush_cell_size(width, height, count)
                self.assertLessEqual(cell, MAX_CELL_SIZE)
                self.assertLessEqual(math.ceil(count / (width // cell)) * cell, height)
                for larger_cell in range(cell + 1, min(width, MAX_CELL_SIZE) + 1):
                    self.assertGreater(math.ceil(count / (width // larger_cell)) * larger_cell, height)

    def test_scrolling_rows_are_filled(self) -> None:
        """When the icons need to scroll, cells stay within limits and leave less than one pixel per column."""
        for width in range(MIN_CELL_SIZE, 1200):
            with self.subTest(width=width):
                cell = brush_cell_size(width, MIN_CELL_SIZE, 1000)
                self.assertGreaterEqual(cell, MIN_CELL_SIZE)
                self.assertLessEqual(cell, MAX_CELL_SIZE)
                columns = width // cell
                self.assertLess(width - columns * cell, columns)

    def test_too_narrow_uses_minimum(self) -> None:
        """Widths below one minimum cell still get a minimum cell."""
        self.assertEqual(brush_cell_size(10, 10, 5), MIN_CELL_SIZE)


class BrushListTest(IntraPaintTestCase):
    """BrushList lays out one row of icons per brush_cell_size column count."""

    def test_row_matches_cell_size(self) -> None:
        """The first row holds as many icons as cells of the brush_cell_size size fit in the icon area's width."""
        brush_list = BrushList()
        for _ in range(30):
            brush_list.add_brush(PENCIL_PATH, QApplication.style().standardIcon(
                QApplication.style().StandardPixmap.SP_FileIcon))
        for width in range(110, 600):
            with self.subTest(width=width):
                brush_list.resize(width, 300)
                brush_list.show()
                brush_list.doItemsLayout()
                area = brush_list.icon_area_size()
                row_width = area.width()
                cell = brush_cell_size(row_width, area.height(), brush_list.count())
                self.assertEqual(brush_list.gridSize(), QSize(cell, cell))
                first_row = [i for i in range(brush_list.count())
                             if brush_list.visualItemRect(brush_list.item(i)).top()
                             == brush_list.visualItemRect(brush_list.item(0)).top()]
                self.assertEqual(len(first_row), row_width // cell)

    def test_minimum_is_one_cell(self) -> None:
        """The minimum size hint fits one minimum-size icon and the scroll bar, whatever the brush count."""
        brush_list = BrushList()
        for _ in range(40):
            brush_list.add_brush(PENCIL_PATH, QApplication.style().standardIcon(
                QApplication.style().StandardPixmap.SP_FileIcon))
        self.assertEqual(brush_list.minimumSizeHint().height(), MIN_CELL_SIZE + 2 * brush_list.frameWidth())


class MypaintBrushPanelTest(IntraPaintTestCase):
    """MypaintBrushPanel keeps every list's selection in sync with Cache, and edits the favorites."""

    def setUp(self) -> None:
        super().setUp()
        self.panel = MypaintBrushPanel(BRUSH_KEY)
        self.lists = self.panel.brush_lists

    def _selected_paths(self, tab_name: str) -> list[str]:
        return [os.path.abspath(item.data(BRUSH_PATH_ROLE)) for item in self.lists[tab_name].selectedItems()]

    def test_tabs_follow_groups_and_favorites(self) -> None:
        """Favorites come first, followed by one tab per brush group."""
        self.assertEqual(self.panel.tabText(0), FAVORITES_CATEGORY_NAME)
        self.assertIn('classic', self.lists)
        self.assertEqual(self.lists[FAVORITES_CATEGORY_NAME].count(), len(AppConfig().get(FAV_CONFIG_KEY)))

    def test_selecting_icon_sets_brush(self) -> None:
        """Selecting an icon stores its brush path relative to the project directory."""
        classic = self.lists['classic']
        classic.setCurrentItem(classic.find_brush(os.path.abspath(CHARCOAL_PATH)))
        self.assertEqual(Cache().get(BRUSH_KEY), os.path.relpath(CHARCOAL_PATH, PROJECT_DIR))

    def test_brush_change_selects_in_every_list(self) -> None:
        """A brush set through Cache is selected in its group tab and in favorites, and nowhere else."""
        Cache().set(BRUSH_KEY, os.path.relpath(PENCIL_PATH, PROJECT_DIR))
        pencil = os.path.abspath(PENCIL_PATH)
        self.assertEqual(self._selected_paths('classic'), [pencil])
        self.assertEqual(self._selected_paths(FAVORITES_CATEGORY_NAME), [pencil])
        self.assertEqual(self._selected_paths('deevad'), [])
        Cache().set(BRUSH_KEY, os.path.relpath(CHARCOAL_PATH, PROJECT_DIR))
        self.assertEqual(self._selected_paths('classic'), [os.path.abspath(CHARCOAL_PATH)])
        self.assertEqual(self._selected_paths(FAVORITES_CATEGORY_NAME), [])

    def test_favorites_add_and_remove(self) -> None:
        """Adding a favorite appends it to the tab and the config; removing it takes it out of both."""
        favorites = self.lists[FAVORITES_CATEGORY_NAME]
        count = favorites.count()
        self.panel.add_favorite(CHARCOAL_PATH)
        self.assertEqual(favorites.count(), count + 1)
        self.assertEqual(AppConfig().get(FAV_CONFIG_KEY)[-1], 'classic/charcoal')
        self.panel.add_favorite(CHARCOAL_PATH)
        self.assertEqual(favorites.count(), count + 1)
        self.panel.remove_favorite(CHARCOAL_PATH)
        self.assertEqual(favorites.count(), count)
        self.assertNotIn('classic/charcoal', AppConfig().get(FAV_CONFIG_KEY))

    def test_favorites_tab_created_on_first_favorite(self) -> None:
        """With no favorites there's no favorites tab, and adding one creates it first in the tab order."""
        AppConfig().set(FAV_CONFIG_KEY, [])
        panel = MypaintBrushPanel(BRUSH_KEY)
        self.assertNotIn(FAVORITES_CATEGORY_NAME, panel.brush_lists)
        panel.add_favorite(PENCIL_PATH)
        self.assertEqual(panel.tabText(0), FAVORITES_CATEGORY_NAME)
        self.assertEqual(panel.brush_lists[FAVORITES_CATEGORY_NAME].count(), 1)


class MyPaintBrushToolPanelTest(IntraPaintTestCase):
    """The brush list takes the tool panel's spare height, so only the list needs to scroll."""

    def test_brush_list_takes_extra_height(self) -> None:
        """Growing the panel past its minimum height grows the brush list by the same amount."""
        host = QWidget()
        panel = MyPaintBrushToolPanel()
        panel.setParent(host)
        brush_list = panel.brush_panel.currentWidget()
        host.show()
        heights = []
        minimum = panel.minimumSizeHint()
        for extra_height in (0, 300):
            panel.setGeometry(QRect(QPoint(), QSize(minimum.width() + 100, minimum.height() + extra_height)))
            panel.layout().activate()
            heights.append(brush_list.height())
        self.assertGreaterEqual(heights[0], brush_list.minimumSizeHint().height())
        self.assertEqual(heights[1] - heights[0], 300)
        host.hide()
