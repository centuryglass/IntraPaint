"""Tests MypaintBrushPanel's tile sizing, categories, brush selection and favorites, and MyPaintBrushToolPanel."""
import math
import os
import sys

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.image.mypaint.mypaint_brush import MyPaintBrush
from src.ui.layout.panel_fit import Orientation
from src.ui.panel.mypaint_brush_panel import (MypaintBrushPanel, BrushList, brush_cell_size, MIN_CELL_SIZE,
                                              MAX_CELL_SIZE, FAVORITES_CATEGORY_NAME, ALL_CATEGORY_NAME,
                                              FAV_CONFIG_KEY, BRUSH_DIR, BRUSH_PATH_ROLE, star_rect)
from src.ui.panel.tool_control_panels.mypaint_brush_tool_panel import (MyPaintBrushToolPanel, SIDE_COMPACT_WIDTH,
                                                                       SIDE_WIDE_WIDTH, STRIP_SHORT_HEIGHT,
                                                                       STRIP_TALL_HEIGHT)
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
                cell = brush_cell_size(row_width, area.height(), brush_list.count(), brush_list.name_height)
                self.assertEqual(brush_list.gridSize(), QSize(cell, cell + brush_list.name_height))
                first_row = [i for i in range(brush_list.count())
                             if brush_list.visualItemRect(brush_list.item(i)).top()
                             == brush_list.visualItemRect(brush_list.item(0)).top()]
                self.assertEqual(len(first_row), row_width // cell)

    def test_minimum_is_one_cell(self) -> None:
        """The minimum size hint fits one minimum-size tile, name included, whatever the brush count."""
        brush_list = BrushList()
        for _ in range(40):
            brush_list.add_brush(PENCIL_PATH, QApplication.style().standardIcon(
                QApplication.style().StandardPixmap.SP_FileIcon))
        self.assertEqual(brush_list.minimumSizeHint().height(),
                         MIN_CELL_SIZE + brush_list.name_height + 2 * brush_list.frameWidth())


class MypaintBrushPanelTest(IntraPaintTestCase):
    """MypaintBrushPanel keeps its grid in sync with Cache and the category chips, and edits the favorites."""

    def setUp(self) -> None:
        super().setUp()
        self.panel = MypaintBrushPanel(BRUSH_KEY)

    def _grid_paths(self) -> list[str]:
        return [os.path.abspath(path) for path in self.panel.grid.brush_paths()]

    def test_chips_follow_favorites_and_groups(self) -> None:
        """Favorites come first, then All, then one chip per brush group."""
        names = self.panel.category_names
        self.assertEqual(names[:2], [FAVORITES_CATEGORY_NAME, ALL_CATEGORY_NAME])
        self.assertIn('classic', names)
        self.assertEqual(self.panel.grid.count(), len(AppConfig().get(FAV_CONFIG_KEY)))

    def test_choosing_category_filters_grid(self) -> None:
        """Each category chip fills the grid with only that category's brushes."""
        self.panel.set_category('classic')
        paths = self._grid_paths()
        self.assertGreater(len(paths), 0)
        self.assertTrue(all(os.path.basename(os.path.dirname(path)) == 'classic' for path in paths))
        self.assertTrue(self.panel.category_buttons['classic'].isChecked())
        self.assertFalse(self.panel.category_buttons[FAVORITES_CATEGORY_NAME].isChecked())
        self.panel.set_category(ALL_CATEGORY_NAME)
        self.assertGreater(len(self._grid_paths()), len(paths))

    def test_tiles_show_names(self) -> None:
        """Each tile carries its brush name as display text."""
        self.panel.set_category('classic')
        item = self.panel.grid.find_brush(os.path.abspath(CHARCOAL_PATH))
        self.assertEqual(item.text(), 'charcoal')

    def test_selecting_tile_sets_brush(self) -> None:
        """Selecting a tile stores its brush path relative to the project directory."""
        self.panel.set_category('classic')
        grid = self.panel.grid
        grid.setCurrentItem(grid.find_brush(os.path.abspath(CHARCOAL_PATH)))
        self.assertEqual(Cache().get(BRUSH_KEY), os.path.relpath(CHARCOAL_PATH, PROJECT_DIR))
        self.assertEqual(self.panel.chip.name_label.text(), 'charcoal')
        self.assertEqual(self.panel.chip.category_label.text(), 'classic')

    def test_brush_change_selects_tile_and_chip(self) -> None:
        """A brush set through Cache is selected in the grid when shown, and the chip follows it."""
        self.panel.set_category('classic')
        Cache().set(BRUSH_KEY, os.path.relpath(PENCIL_PATH, PROJECT_DIR))
        selected = [os.path.abspath(item.data(BRUSH_PATH_ROLE)) for item in self.panel.grid.selectedItems()]
        self.assertEqual(selected, [os.path.abspath(PENCIL_PATH)])
        self.assertEqual(self.panel.chip.name_label.text(), 'pencil')
        Cache().set(BRUSH_KEY, os.path.relpath(CHARCOAL_PATH, PROJECT_DIR))
        selected = [os.path.abspath(item.data(BRUSH_PATH_ROLE)) for item in self.panel.grid.selectedItems()]
        self.assertEqual(selected, [os.path.abspath(CHARCOAL_PATH)])

    def test_favorites_add_and_remove(self) -> None:
        """Adding a favorite appends it to the Favorites grid and the config; removing it takes it out of both."""
        count = self.panel.grid.count()
        self.panel.add_favorite(CHARCOAL_PATH)
        self.assertEqual(self.panel.grid.count(), count + 1)
        self.assertEqual(AppConfig().get(FAV_CONFIG_KEY)[-1], 'classic/charcoal')
        self.panel.add_favorite(CHARCOAL_PATH)
        self.assertEqual(self.panel.grid.count(), count + 1)
        self.panel.remove_favorite(CHARCOAL_PATH)
        self.assertEqual(self.panel.grid.count(), count)
        self.assertNotIn('classic/charcoal', AppConfig().get(FAV_CONFIG_KEY))

    def test_last_favorite_removed_drops_chip(self) -> None:
        """Removing the last favorite removes the Favorites chip at once and shows another category."""
        for path in self.panel.library.favorite_paths():
            self.panel.remove_favorite(path)
        self.assertNotIn(FAVORITES_CATEGORY_NAME, self.panel.category_names)
        self.assertEqual(self.panel.category, ALL_CATEGORY_NAME)
        self.assertGreater(self.panel.grid.count(), 0)

    def test_first_favorite_adds_chip(self) -> None:
        """With no favorites there's no Favorites chip, and adding one creates it first in the chip order."""
        AppConfig().set(FAV_CONFIG_KEY, [])
        panel = MypaintBrushPanel(BRUSH_KEY)
        self.assertNotIn(FAVORITES_CATEGORY_NAME, panel.category_names)
        panel.add_favorite(PENCIL_PATH)
        self.assertEqual(panel.category_names[0], FAVORITES_CATEGORY_NAME)

    def test_panels_share_favorites(self) -> None:
        """A favorite added in one panel appears in every other panel."""
        other = MypaintBrushPanel(BRUSH_KEY, library=self.panel.library)
        self.panel.add_favorite(CHARCOAL_PATH)
        self.assertIn(os.path.abspath(CHARCOAL_PATH), [os.path.abspath(p) for p in other.grid.brush_paths()])

    def test_chip_star_toggles_active_favorite(self) -> None:
        """The chip's star reflects and toggles whether the active brush is a favorite."""
        Cache().set(BRUSH_KEY, os.path.relpath(CHARCOAL_PATH, PROJECT_DIR))
        self.assertFalse(self.panel.chip.star.isChecked())
        self.panel.chip.star.click()
        self.assertTrue(self.panel.is_favorite(CHARCOAL_PATH))
        self.assertTrue(self.panel.chip.star.isChecked())
        self.panel.chip.star.click()
        self.assertFalse(self.panel.is_favorite(CHARCOAL_PATH))

    def test_tile_star_click_toggles_favorite(self) -> None:
        """Clicking a tile's star toggles its favorite without selecting the tile."""
        self.panel.set_category('classic')
        self.panel.resize(400, 500)
        self.panel.show()
        grid = self.panel.grid
        grid.doItemsLayout()
        item = grid.find_brush(os.path.abspath(CHARCOAL_PATH))
        point = star_rect(grid.visualItemRect(item)).center()
        QTest.mouseClick(grid.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
        self.assertTrue(self.panel.is_favorite(CHARCOAL_PATH))
        self.assertNotEqual(Cache().get(BRUSH_KEY), os.path.relpath(CHARCOAL_PATH, PROJECT_DIR))
        self.panel.hide()

    def test_compact_form_shows_favorite_thumbnails(self) -> None:
        """The compact form hides the chips and grid and shows up to the requested number of favorites."""
        self.panel.set_compact(True)
        self.panel.set_favorite_count(2)
        self.panel.show()
        self.assertFalse(self.panel.grid.isVisible())
        self.assertEqual(len(self.panel.thumbnails), 2)
        self.assertTrue(self.panel.chip.popup_enabled)
        self.panel.thumbnails[1].click()
        self.assertEqual(os.path.abspath(self.panel.active_brush_path),
                         os.path.abspath(self.panel.thumbnails[1].property('brush_path')))
        self.panel.hide()


class MyPaintBrushToolPanelTest(IntraPaintTestCase):
    """The tool panel hosts the stroke block with Size only, the picker and brush dynamics."""

    def setUp(self) -> None:
        super().setUp()
        self.brush = MyPaintBrush()
        self.brush.load_file(PENCIL_PATH)
        self.panel = MyPaintBrushToolPanel(self.brush)

    def test_block_has_size_only(self) -> None:
        """Opacity and hardness are left to the brush file."""
        self.assertEqual(len(self.panel.stroke_block.fields()), 1)
        self.assertEqual(self.panel.stroke_block.fields()[0].label(), 'Size')

    def test_side_forms_follow_width(self) -> None:
        """The picker is compact in a narrow side panel and dynamics open only in a wide one."""
        for width, compact, opened in ((SIDE_COMPACT_WIDTH - 20, True, False), (SIDE_COMPACT_WIDTH + 40, False, False),
                                       (SIDE_WIDE_WIDTH + 40, False, True)):
            with self.subTest(width=width):
                self.panel.set_fit_space(Orientation.SIDE, QSize(width, 700))
                self.assertEqual(self.panel.brush_panel.compact, compact)
                self.assertEqual(self.panel.dynamics_section.is_expanded(), opened)
                self.assertFalse(self.panel.dynamics_button.isVisibleTo(self.panel))

    def test_strip_forms_follow_height(self) -> None:
        """A short strip is compact, and dynamics move to a button until the strip is tall."""
        self.panel.set_fit_space(Orientation.STRIP, QSize(900, STRIP_SHORT_HEIGHT - 20))
        self.assertTrue(self.panel.brush_panel.compact)
        self.assertTrue(self.panel.dynamics_button.isVisibleTo(self.panel))
        self.assertFalse(self.panel.dynamics_section.isVisibleTo(self.panel))
        self.panel.set_fit_space(Orientation.STRIP, QSize(900, STRIP_TALL_HEIGHT + 40))
        self.assertFalse(self.panel.brush_panel.compact)
        self.assertFalse(self.panel.dynamics_button.isVisibleTo(self.panel))
        self.assertTrue(self.panel.dynamics_section.isVisibleTo(self.panel))

    def test_dynamics_edit_reaches_brush(self) -> None:
        """Changing the base value of the picked setting sets it on the brush."""
        dynamics = self.panel.dynamics
        index = dynamics.setting_combo.findText('Opacity', Qt.MatchFlag.MatchContains)
        self.assertGreaterEqual(index, 0)
        dynamics.setting_combo.setCurrentIndex(index)
        dynamics.value_field.set_value(0.25)
        dynamics.value_field.valueChanged.emit(0.25)
        self.assertAlmostEqual(self.brush.get_value(dynamics.current_setting.id), 0.25, places=4)

    def test_dynamics_refresh_reads_brush(self) -> None:
        """After the brush loads another file, refresh shows the new file's value."""
        dynamics = self.panel.dynamics
        setting_id = dynamics.current_setting.id
        self.brush.set_value(setting_id, 0.5)
        self.panel.refresh_dynamics()
        self.assertAlmostEqual(dynamics.value_field.value(), 0.5, places=4)
