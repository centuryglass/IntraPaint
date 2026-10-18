"""Tests MypaintBrushPanel's tile sizing, categories, brush selection and favorites, and MyPaintBrushToolPanel."""
import math
import os
import sys

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QPushButton, QToolButton, QWidget
from PySide6.QtTest import QTest

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.image.mypaint.mypaint_brush import MyPaintBrush
from src.ui.layout.flow_layout import FlowWidget
from src.ui.layout.panel_fit import Orientation
from src.ui.widget.panel_section import HEADER_HEIGHT
from src.ui.panel.mypaint_brush_panel import (MypaintBrushPanel, BrushList, brush_cell_size, MIN_CELL_SIZE,
                                              MAX_CELL_SIZE, MIN_COLUMNS, MIN_ROWS, FAVORITES_CATEGORY_NAME,
                                              ALL_CATEGORY_NAME, FAV_CONFIG_KEY, BRUSH_DIR, BRUSH_PATH_ROLE,
                                              FavoritesRow, star_rect)
from src.ui.panel.tool_control_panels.mypaint_brush_tool_panel import MyPaintBrushToolPanel
from src.util.shared_constants import PROJECT_DIR
from test.base_test_case import IntraPaintTestCase
from test.ui.panel.tool_panel_test import settle_layouts

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

    def test_minimum_holds_minimum_grid(self) -> None:
        """The minimum size hint fits MIN_ROWS rows of MIN_COLUMNS minimum-size tiles, whatever the brush count."""
        brush_list = BrushList()
        for _ in range(40):
            brush_list.add_brush(PENCIL_PATH, QApplication.style().standardIcon(
                QApplication.style().StandardPixmap.SP_FileIcon))
        hint = brush_list.minimumSizeHint()
        self.assertEqual(hint.height(), (MIN_CELL_SIZE + brush_list.name_height) * MIN_ROWS
                         + 2 * brush_list.frameWidth())
        self.assertGreaterEqual(hint.width(), MIN_CELL_SIZE * MIN_COLUMNS)


class FlowWidgetTest(IntraPaintTestCase):
    """FlowWidget measures its minimum height at the width it is told it will be laid out at."""

    def test_narrower_wrap_width_adds_lines(self) -> None:
        """Chips that fit on one line at a wide wrap width need more height at a narrow one."""
        chips = FlowWidget()
        for name in ('Favorites', 'All', 'classic', 'deevad', 'ramon', 'experimental'):
            chips.flow.addWidget(QPushButton(name, chips))
        chips.set_wrap_width(2000)
        one_line = chips.minimumSizeHint().height()
        chips.set_wrap_width(chips.minimumSizeHint().width())
        self.assertGreater(chips.minimumSizeHint().height(), one_line)


class FavoritesRowTest(IntraPaintTestCase):
    """FavoritesRow shows as many thumbnails as fit its width."""

    def test_shows_fitting_thumbnails(self) -> None:
        """A row one and a half thumbnails wide shows one, and a row wide enough for all shows all."""
        # A shown top-level widget can't shrink below its layout's minimum, so the row goes in a parent:
        parent = QWidget()
        row = FavoritesRow(parent)
        row.set_buttons([QToolButton() for _ in range(5)])
        thumbnail = row.minimumSizeHint().width()
        parent.show()
        row.resize(thumbnail * 3 // 2, row.minimumSizeHint().height())
        self.assertEqual([button.isHidden() for button in row.buttons], [False, True, True, True, True])
        row.resize(row.sizeHint())
        self.assertFalse(any(button.isHidden() for button in row.buttons))
        parent.hide()


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
        """The compact form hides the chips and grid, shows favorite thumbnails, and lets the chip open the picker."""
        self.panel.set_compact(True)
        self.panel.show()
        self.assertFalse(self.panel.grid.isVisible())
        self.assertFalse(self.panel.category_chips.isVisible())
        self.assertGreater(len(self.panel.thumbnails), 1)
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

    def test_side_forms_follow_fit(self) -> None:
        """A side panel too narrow for the grid gets the compact picker, and dynamics open where they fit, collapse
        where only the header fits, and move to the overflow content where nothing does."""
        self.panel.set_fit_space(Orientation.SIDE, QSize(500, 1200))
        self.assertFalse(self.panel.brush_panel.compact)
        self.assertTrue(self.panel.dynamics_section.isVisibleTo(self.panel))
        self.assertFalse(self.panel.dynamics_section.is_collapsed())
        self.panel.set_fit_space(Orientation.SIDE, QSize(120, 1200))
        self.assertTrue(self.panel.brush_panel.compact)
        short = self.panel.fit_base_size(Orientation.SIDE)
        # The base size holds the compact picker, which is all that fits at the base width:
        self.panel.set_fit_space(Orientation.SIDE, QSize(short.width(), short.height() + HEADER_HEIGHT + 12))
        self.assertTrue(self.panel.dynamics_section.isVisibleTo(self.panel))
        self.assertTrue(self.panel.dynamics_section.is_collapsed())
        self.panel.set_fit_space(Orientation.SIDE, QSize(short.width(), short.height()))
        self.assertFalse(self.panel.dynamics_section.isVisibleTo(self.panel))
        self.assertIs(self.panel.dynamics.parentWidget(), self.panel.overflow_content())

    def test_strip_forms_follow_fit(self) -> None:
        """A short strip gets the compact picker and moves dynamics to the overflow content, and a tall, wide one
        shows the grid and a dynamics column."""
        self.panel.set_fit_space(Orientation.STRIP, QSize(900, 100))
        self.assertTrue(self.panel.brush_panel.compact)
        self.assertFalse(self.panel.dynamics_section.isVisibleTo(self.panel))
        self.assertIs(self.panel.dynamics.parentWidget(), self.panel.overflow_content())
        self.panel.set_fit_space(Orientation.STRIP, QSize(1600, 500))
        self.assertFalse(self.panel.brush_panel.compact)
        self.assertTrue(self.panel.dynamics_section.isVisibleTo(self.panel))
        self.assertIsNot(self.panel.dynamics.parentWidget(), self.panel.overflow_content())

    def test_long_dynamics_description_gets_its_whole_height(self) -> None:
        """After switching to a setting with a long description, the description is tall enough for every line at
        its width, in a side panel wider than the section's cap."""
        self.panel.resize(700, 1400)
        self.panel.set_fit_space(Orientation.SIDE, QSize(700, 1400))
        self.panel.show()
        combo = self.panel.dynamics.setting_combo
        descriptions = {combo.itemText(i): len(self.panel.dynamics.description_for(i)) for i in range(combo.count())}
        combo.setCurrentIndex(combo.findText(max(descriptions, key=descriptions.get)))
        settle_layouts(self.panel)
        label = self.panel.dynamics.description_label
        self.assertGreater(label.heightForWidth(label.width()), label.fontMetrics().height() * 2)
        self.assertGreaterEqual(label.height(), label.heightForWidth(label.width()))
        self.panel.hide()

    def test_compact_strip_chip_keeps_the_whole_name(self) -> None:
        """Beside the favorites in a strip, the chip is never narrower than its whole brush name."""
        Cache().set(BRUSH_KEY, os.path.relpath(CHARCOAL_PATH, PROJECT_DIR))
        picker = self.panel.brush_panel
        picker.set_compact(True, beside=True)
        chip = picker.chip
        self.assertGreaterEqual(chip.minimumWidth(),
                                chip.name_label.fontMetrics().horizontalAdvance(chip.name_label.text()))
        picker.set_compact(True, beside=False)
        self.assertLess(chip.minimumWidth(), chip.sizeHint().width())
