"""Tests ColorSwatchGrid, and the saved and recent colors in the color panel."""
from unittest.mock import patch

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QDrag, QDropEvent

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller import color_controller
from src.ui.panel.color_panel import ColorControlPanel
from src.ui.widget.color_picker.color_swatch_grid import ColorSwatchGrid, SWATCH_SIZE, SWATCH_SPACING
from test.base_test_case import IntraPaintTestCase
from src.ui.widget.color_picker.palette_widget import CustomColorPaletteWidget
from test.ui.widget.color_picker_test_utils import press, move, release, SignalRecorder

COLORS = ['#ffff0000', '#8000ff00', '#ff0000ff', '#ff123456', '#ffabcdef']


def _center(grid: ColorSwatchGrid, index: int) -> QPointF:
    return QPointF(grid.swatch_rect(index).center())


def _click(widget, point: QPointF) -> None:
    press(widget, point)
    release(widget, point)


def _drop(grid: ColorSwatchGrid, color: QColor, point: QPointF) -> None:
    mime_data = QMimeData()
    mime_data.setColorData(color)
    event = QDropEvent(point, Qt.DropAction.CopyAction, mime_data, Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier)
    grid.dropEvent(event)


def _names(colors: list[QColor]) -> list[str]:
    return [color.name(QColor.NameFormat.HexArgb) for color in colors]


class ColorSwatchGridTest(IntraPaintTestCase):
    """Tests ColorSwatchGrid."""

    def setUp(self) -> None:
        super().setUp()
        self.grid = ColorSwatchGrid()
        self.grid.set_colors([QColor(color) for color in COLORS])
        self.clicked = SignalRecorder(self.grid.color_clicked)

    def test_swatches_wrap_to_width(self) -> None:
        """Swatches fill each row before wrapping, and the height grows with the row count."""
        step = SWATCH_SIZE + SWATCH_SPACING
        self.grid.resize(step * 2, 100)
        self.assertEqual(self.grid.columns(), 2)
        self.assertEqual(self.grid.swatch_rect(3).topLeft(), QPoint(step, step))
        self.assertEqual(self.grid.heightForWidth(step * 2), step * 3 - SWATCH_SPACING)
        self.assertEqual(self.grid.heightForWidth(step * 5), SWATCH_SIZE)

    def test_empty_grid_keeps_one_row(self) -> None:
        """An empty grid keeps one row of height."""
        self.grid.set_colors([])
        self.assertEqual(self.grid.heightForWidth(200), SWATCH_SIZE)

    def test_click_emits_color(self) -> None:
        """Clicking a swatch emits its color on release; clicking the gaps emits nothing."""
        self.grid.resize(300, 100)
        press(self.grid, _center(self.grid, 1))
        self.assertEqual(self.clicked.colors, [])
        release(self.grid, _center(self.grid, 1))
        gap = QPointF(SWATCH_SIZE + SWATCH_SPACING / 2, SWATCH_SIZE / 2)
        _click(self.grid, gap)
        self.assertEqual(_names(self.clicked.colors), ['#8000ff00'])

    def test_drag_carries_color_without_clicking(self) -> None:
        """Dragging a swatch starts a drag holding its color, and the release doesn't click it."""
        self.grid.resize(300, 100)
        dragged: list[QColor] = []

        def _exec(drag: QDrag, *_args) -> Qt.DropAction:
            dragged.append(QColor(drag.mimeData().colorData()))
            return Qt.DropAction.CopyAction

        with patch.object(QDrag, 'exec', _exec):
            press(self.grid, _center(self.grid, 2))
            move(self.grid, _center(self.grid, 4))
            release(self.grid, _center(self.grid, 4))
        self.assertEqual(_names(dragged), ['#ff0000ff'])
        self.assertEqual(self.clicked.colors, [])

    def test_drop_emits_insertion_index(self) -> None:
        """A dropped color is emitted with the index of the gap nearest the drop point."""
        self.grid.resize(300, 100)
        self.grid.setAcceptDrops(True)
        dropped = []
        self.grid.color_dropped.connect(lambda color, index: dropped.append((color.name(), index)))
        step = SWATCH_SIZE + SWATCH_SPACING
        _drop(self.grid, QColor('#123123'), QPointF(step * 2 - 2, 5))
        _drop(self.grid, QColor('#456456'), QPointF(step * 2 + 4, 5))
        _drop(self.grid, QColor('#789789'), QPointF(280, 5))
        self.assertEqual(dropped, [('#123123', 2), ('#456456', 2), ('#789789', len(COLORS))])

    def test_current_color_is_highlighted(self) -> None:
        """The swatch matching the current color is drawn with the highlight border."""
        self.grid.resize(300, 100)
        self.grid.set_current_color(QColor('#ff0000ff'))
        image = self.grid.grab().toImage()
        highlight = self.grid.palette().highlight().color()
        rect = self.grid.swatch_rect(2)
        self.assertEqual(image.pixelColor(rect.left() + 1, rect.center().y()).rgb(), highlight.rgb())
        other = self.grid.swatch_rect(3)
        self.assertNotEqual(image.pixelColor(other.left() + 1, other.center().y()).rgb(), highlight.rgb())


class ColorPanelSavedColorsTest(IntraPaintTestCase):
    """Tests the saved and recent colors in ColorControlPanel."""

    def setUp(self) -> None:
        super().setUp()
        Cache().set(Cache.LAST_BRUSH_COLOR, '#ff336699')
        Cache().set(Cache.RECENT_COLORS, ['#ff112233', '#ff445566'])
        AppConfig().set(AppConfig.SAVED_COLORS, ['#ffaabbcc'])
        self.panel = ColorControlPanel(disable_extended_layouts=True)
        self.panel.set_four_tab_mode()
        self.saved_grid = self.panel.saved_colors_panel.grid
        self.saved_grid.resize(300, 100)
        self.recent_grid = self.panel.recent_colors_row.grid
        self.recent_grid.resize(300, 100)

    def test_save_button_saves_current_color(self) -> None:
        """The save button adds the current color to the saved colors and their grid."""
        self.panel.saved_colors_panel.save_button.click()
        self.assertEqual(AppConfig().get(AppConfig.SAVED_COLORS), ['#ffaabbcc', '#ff336699'])
        self.assertEqual(_names(self.saved_grid.colors()), ['#ffaabbcc', '#ff336699'])

    def test_saved_swatch_click_sets_and_commits_foreground(self) -> None:
        """Clicking a saved color sets the foreground and records it as a recent color."""
        _click(self.saved_grid, _center(self.saved_grid, 0))
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), '#ffaabbcc')
        self.assertEqual(Cache().get(Cache.RECENT_COLORS), ['#ffaabbcc', '#ff112233', '#ff445566'])
        self.assertEqual(self.panel.wheel_picker.selected_color(), QColor('#ffaabbcc'))

    def test_recent_row_follows_cache_and_click_moves_color_to_front(self) -> None:
        """The recent row shows the recent colors, and clicking one makes it the foreground and the newest."""
        self.assertEqual(_names(self.recent_grid.colors()), ['#ff112233', '#ff445566'])
        _click(self.recent_grid, _center(self.recent_grid, 1))
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), '#ff445566')
        self.assertEqual(_names(self.recent_grid.colors()), ['#ff445566', '#ff112233'])

    def test_drop_saves_and_reorders(self) -> None:
        """Dropping a new color saves it at the drop point, and dropping a saved color moves it there."""
        _drop(self.saved_grid, QColor('#ff336699'), QPointF(0, 5))
        self.assertEqual(AppConfig().get(AppConfig.SAVED_COLORS), ['#ff336699', '#ffaabbcc'])
        _drop(self.saved_grid, QColor('#ff336699'), QPointF(280, 5))
        self.assertEqual(AppConfig().get(AppConfig.SAVED_COLORS), ['#ffaabbcc', '#ff336699'])

    def test_saving_past_custom_palette_slots(self) -> None:
        """Saving more colors than the old Custom colors grid has slots keeps them all, and that grid shows the
        first ones."""
        slots = self.panel.findChild(CustomColorPaletteWidget).color_count()
        colors = [f'#ff0000{index:02x}' for index in range(slots + 2)]
        for color in colors:
            # Called directly, since an exception raised in a button's slot doesn't reach the test.
            color_controller.save_color(QColor(color))
        self.assertEqual(AppConfig().get(AppConfig.SAVED_COLORS), ['#ffaabbcc', *colors])
        custom_palette = self.panel.findChild(CustomColorPaletteWidget)
        self.assertEqual(custom_palette.get_color(1).name(QColor.NameFormat.HexArgb), colors[0])
