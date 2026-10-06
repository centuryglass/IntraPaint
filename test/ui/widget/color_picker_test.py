"""Tests TabbedColorPicker's shared color, its layouts, ColorControlPanel's layout choice, and ColorDialog."""
from PySide6.QtCore import QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QColor
from PySide6 import QtTest

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.ui.modal.color_dialog import ColorDialog
from src.ui.panel.color_panel import ColorControlPanel, choose_layout
from src.ui.widget.color_pair_widget import ColorPairWidget
from src.ui.widget.color_picker.color_comparison import ColorComparison
from src.ui.widget.color_picker.color_slider_block import MODE_RGB
from src.ui.widget.color_picker.tabbed_color_picker import TabbedColorPicker, ColorPickerLayout, WHEEL_TAB_TITLE, \
    SLIDERS_TAB_TITLE, PALETTES_TAB_TITLE, ALPHA_TAB_TITLE
from test.base_test_case import IntraPaintTestCase
from test.ui.widget.color_picker_test_utils import press, move, release, SignalRecorder

WIDGET_SIZE = 200
SLIDER_WIDTH = 300


def _titles(*titles: str) -> list[str]:
    return [title.replace('&', '') for title in titles]


class TabbedColorPickerTest(IntraPaintTestCase):
    """Tests that every part of TabbedColorPicker edits one color."""

    def setUp(self) -> None:
        super().setUp()
        Cache().restore_default_options(Cache.COLOR_SLIDER_MODE)
        self.picker = TabbedColorPicker()
        self.picker.set_current_color(QColor('#336699'))
        self.picker.ring_square.resize(WIDGET_SIZE, WIDGET_SIZE)
        self.selected = SignalRecorder(self.picker.color_selected)
        self.committed = SignalRecorder(self.picker.color_committed)

    def _enter_hex(self, text: str) -> None:
        field = self.picker.alpha_hex_row.hex_field
        field.setText(text)
        QtTest.QTest.keyClick(field, Qt.Key.Key_Return)

    def test_set_color_round_trips_and_shows_everywhere(self) -> None:
        """Setting a color reads back unchanged and shows in every part, without committing."""
        color = QColor('#80cc3366')
        self.picker.set_current_color(color)
        self.assertEqual(self.picker.selected_color(), color)
        self.assertEqual(self.picker.ring_square.color(), color)
        self.assertEqual(self.picker.slider_block.selected_color(), color)
        self.assertEqual(self.picker.secondary_slider_block.selected_color(), color)
        self.assertEqual(self.picker.alpha_hex_row.color(), color)
        self.assertEqual(self.picker.header.hex_label.text(), '#80cc3366')
        self.assertEqual(self.selected.colors, [color])
        self.assertEqual(self.committed.colors, [])

    def test_hex_field_accepts_argb(self) -> None:
        """Entering #AARRGGBB selects that color and alpha, and commits it."""
        self._enter_hex('#80112233')
        expected = QColor(0x11, 0x22, 0x33, 0x80)
        self.assertEqual(self.picker.selected_color(), expected)
        self.assertEqual(self.picker.alpha_hex_row.alpha_slider.value(), 0x80)
        self.assertEqual(self.picker.ring_square.color(), expected)
        self.assertEqual(self.selected.colors, [expected])
        self.assertEqual(self.committed.colors, [expected])

    def test_invalid_hex_restores_field(self) -> None:
        """Invalid hex text reverts to the current color without emitting."""
        self._enter_hex('nonsense')
        self.assertEqual(self.picker.alpha_hex_row.hex_field.text(), '#336699')
        self.assertEqual(self.selected.colors, [])
        self.assertEqual(self.committed.colors, [])

    def test_alpha_slider_drag_commits_on_release(self) -> None:
        """Dragging the alpha slider changes alpha everywhere without committing; releasing it commits."""
        slider = self.picker.alpha_hex_row.alpha_slider
        slider.resize(SLIDER_WIDTH, slider.sizeHint().height())
        press(slider, QPointF(slider.x_for_value(200), 5))
        move(slider, QPointF(slider.x_for_value(100), 5))
        self.assertEqual(self.picker.selected_color().alpha(), 100)
        self.assertEqual(self.picker.ring_square.color().alpha(), 100)
        self.assertEqual(self.picker.header.hex_label.text(), '#64336699')
        self.assertEqual(self.committed.colors, [])
        release(slider, QPointF(slider.x_for_value(100), 5))
        self.assertEqual([color.alpha() for color in self.committed.colors], [100])

    def test_ring_drag_updates_other_parts_and_commits_on_release(self) -> None:
        """Dragging in the square updates the sliders and hex field; only the release commits."""
        ring_square = self.picker.ring_square
        press(ring_square, ring_square.point_for_saturation_value(0.0, 1.0))
        self.assertEqual(self.picker.selected_color(), QColor('#ffffff'))
        self.assertEqual(self.picker.alpha_hex_row.hex_field.text(), '#ffffff')
        self.assertEqual(self.picker.slider_block.selected_color(), QColor('#ffffff'))
        self.assertEqual(self.committed.colors, [])
        release(ring_square, ring_square.point_for_saturation_value(0.0, 1.0))
        self.assertEqual(self.committed.colors, [QColor('#ffffff')])

    def test_slider_drag_updates_ring(self) -> None:
        """Dragging a slider updates the ring; releasing it commits."""
        block = self.picker.slider_block
        block.set_mode(MODE_RGB)
        block.resize(SLIDER_WIDTH, block.sizeHint().height())
        red = block.sliders[0]
        point = QPointF(red.x_for_value(255), red.height() / 2)
        press(red, point)
        self.assertEqual(self.picker.ring_square.color(), QColor('#ff6699'))
        self.assertEqual(self.committed.colors, [])
        release(red, point)
        self.assertEqual(self.committed.colors, [QColor('#ff6699')])

    def test_screen_pick_commits(self) -> None:
        """A picked screen color is selected and committed."""
        self.picker.screen_color_picked.emit(QColor('#123456'))
        self.assertEqual(self.picker.selected_color(), QColor('#123456'))
        self.assertEqual(self.committed.colors, [QColor('#123456')])

    def test_screen_pick_preview_shows_cursor_position(self) -> None:
        """While picking, the header shows the cursor position, and hides it when picking stops."""
        label = self.picker.header.picking_label
        self.picker.color_previewed.emit(QPoint(12, 34), QColor('#000000'))
        self.assertFalse(label.isHidden())
        self.assertIn('12,34', label.text())
        self.picker.stopped_color_picking.emit()
        self.assertTrue(label.isHidden())


class ColorPickerLayoutTest(IntraPaintTestCase):
    """Tests the parts and tabs each ColorPickerLayout shows."""

    def setUp(self) -> None:
        super().setUp()
        self.picker = TabbedColorPicker()

    def _shown_parts(self) -> set[str]:
        parts = {
            'header': self.picker.header,
            'ring': self.picker.ring_square,
            'sliders': self.picker.slider_block,
            'secondary_sliders': self.picker.secondary_slider_block,
            'alpha_hex': self.picker.alpha_hex_row,
            'saved': self.picker.saved_colors_panel,
            'recent': self.picker.recent_colors_row,
        }
        return {name for name, part in parts.items() if not part.isHidden()}

    def _tab_tooltips(self) -> list[str]:
        tabs = self.picker.tab_widget
        assert tabs is not None
        return [tabs.tabToolTip(index) for index in range(tabs.count())]

    def _tab_texts(self) -> list[str]:
        tabs = self.picker.tab_widget
        assert tabs is not None
        return [tabs.tabText(index) for index in range(tabs.count())]

    def test_side_layouts(self) -> None:
        """The side layout has three labeled tabs; the compact one hides labels and recent colors."""
        self.picker.set_picker_layout(ColorPickerLayout.SIDE)
        self.assertEqual(self._tab_tooltips(), _titles(WHEEL_TAB_TITLE, SLIDERS_TAB_TITLE, PALETTES_TAB_TITLE))
        self.assertEqual(self._tab_texts(), [WHEEL_TAB_TITLE, SLIDERS_TAB_TITLE, PALETTES_TAB_TITLE])
        self.assertEqual(self._shown_parts(), {'header', 'ring', 'sliders', 'alpha_hex', 'saved', 'recent'})
        self.picker.set_picker_layout(ColorPickerLayout.SIDE_COMPACT)
        self.assertEqual(self._tab_texts(), ['', '', ''])
        self.assertEqual(self._shown_parts(), {'header', 'ring', 'sliders', 'alpha_hex', 'saved'})

    def test_untabbed_layouts(self) -> None:
        """The tall side layout and the wide bottom layout have no tabs; only the wide one shows both slider
        blocks."""
        self.picker.set_picker_layout(ColorPickerLayout.SIDE_TALL)
        self.assertIsNone(self.picker.tab_widget)
        self.assertEqual(self._shown_parts(), {'header', 'ring', 'sliders', 'alpha_hex', 'saved', 'recent'})
        self.picker.set_picker_layout(ColorPickerLayout.BOTTOM_WIDE)
        self.assertIsNone(self.picker.tab_widget)
        self.assertEqual(self._shown_parts(), {'header', 'ring', 'sliders', 'secondary_sliders', 'alpha_hex', 'saved',
                                               'recent'})

    def test_bottom_tabbed_layouts(self) -> None:
        """The medium bottom layout tabs sliders and palettes; the short one also tabs alpha + hex, icon-only."""
        self.picker.set_picker_layout(ColorPickerLayout.BOTTOM_MEDIUM)
        self.assertEqual(self._tab_tooltips(), _titles(SLIDERS_TAB_TITLE, PALETTES_TAB_TITLE))
        self.assertEqual(self._shown_parts(), {'header', 'ring', 'sliders', 'alpha_hex', 'saved', 'recent'})
        self.picker.set_picker_layout(ColorPickerLayout.BOTTOM_SHORT)
        self.assertEqual(self._tab_tooltips(), _titles(SLIDERS_TAB_TITLE, PALETTES_TAB_TITLE, ALPHA_TAB_TITLE))
        self.assertEqual(self._tab_texts(), ['', '', ''])
        self.assertEqual(self._shown_parts(), {'header', 'ring', 'sliders', 'alpha_hex', 'saved'})

    def test_layout_change_keeps_color_and_open_tab(self) -> None:
        """Switching layouts keeps the color, and keeps the open tab when the new layout has it."""
        self.picker.set_current_color(QColor('#80cc3366'))
        self.picker.set_picker_layout(ColorPickerLayout.SIDE)
        tabs = self.picker.tab_widget
        assert tabs is not None
        tabs.setCurrentIndex(2)
        self.picker.set_picker_layout(ColorPickerLayout.BOTTOM_MEDIUM)
        self.assertEqual(self._tab_tooltips()[self.picker.tab_widget.currentIndex()],
                         _titles(PALETTES_TAB_TITLE)[0])
        self.assertEqual(self.picker.selected_color(), QColor('#80cc3366'))
        self.assertEqual(self.picker.ring_square.color(), QColor('#80cc3366'))

    def test_row_layout_ring_follows_height(self) -> None:
        """In bottom layouts the ring is as wide as the picker is tall, up to a share of its width."""
        self.picker.set_picker_layout(ColorPickerLayout.BOTTOM_MEDIUM)
        # A hidden widget gets its resize event only once shown.
        self.picker.show()
        self.picker.resize(900, 250)
        margins = self.picker.layout().contentsMargins()
        self.assertEqual(self.picker.ring_square.minimumWidth(), 250 - margins.top() - margins.bottom())
        self.picker.set_picker_layout(ColorPickerLayout.SIDE)
        self.assertEqual(self.picker.ring_square.minimumWidth(), 0)


class ChooseLayoutTest(IntraPaintTestCase):
    """Tests ColorControlPanel's layout choice."""

    def test_side_dock(self) -> None:
        """Side docks use the tall layout when tall, the compact one when narrow or short, and tabs otherwise."""
        vertical = Qt.Orientation.Vertical
        self.assertEqual(choose_layout(QSize(300, 1000), vertical), ColorPickerLayout.SIDE_TALL)
        self.assertEqual(choose_layout(QSize(300, 600), vertical), ColorPickerLayout.SIDE)
        self.assertEqual(choose_layout(QSize(240, 600), vertical), ColorPickerLayout.SIDE_COMPACT)
        self.assertEqual(choose_layout(QSize(300, 400), vertical), ColorPickerLayout.SIDE_COMPACT)
        self.assertEqual(choose_layout(QSize(300, 600), None), ColorPickerLayout.SIDE)

    def test_bottom_dock(self) -> None:
        """Bottom docks use four columns when wide, the short layout when short, and the medium one otherwise."""
        horizontal = Qt.Orientation.Horizontal
        self.assertEqual(choose_layout(QSize(1400, 300), horizontal), ColorPickerLayout.BOTTOM_WIDE)
        self.assertEqual(choose_layout(QSize(800, 300), horizontal), ColorPickerLayout.BOTTOM_MEDIUM)
        self.assertEqual(choose_layout(QSize(1400, 200), horizontal), ColorPickerLayout.BOTTOM_SHORT)

    def test_chosen_layouts_fit(self) -> None:
        """Each layout's minimum size fits the panel size that chooses it, at the 1024x600 budget's dock sizes."""
        picker = TabbedColorPicker()
        for size, orientation in ((QSize(240, 300), Qt.Orientation.Vertical),
                                  (QSize(300, 560), Qt.Orientation.Vertical),
                                  (QSize(300, 1000), Qt.Orientation.Vertical),
                                  (QSize(1400, 300), Qt.Orientation.Horizontal),
                                  (QSize(700, 300), Qt.Orientation.Horizontal),
                                  (QSize(600, 200), Qt.Orientation.Horizontal)):
            picker.set_picker_layout(choose_layout(size, orientation))
            picker.resize(size)
            minimum = picker.minimumSizeHint()
            self.assertLessEqual(minimum.width(), size.width(), f'{picker.picker_layout()} at {size}')
            self.assertLessEqual(minimum.height(), size.height(), f'{picker.picker_layout()} at {size}')


class ColorControlPanelTest(IntraPaintTestCase):
    """Tests ColorControlPanel's header and layout updates."""

    def setUp(self) -> None:
        super().setUp()
        Cache().set(Cache.LAST_BRUSH_COLOR, '#ff336699')
        Cache().set(Cache.RECENT_COLORS, [])
        self.panel = ColorControlPanel()

    def test_header_shows_color_pair(self) -> None:
        """The foreground panel's header holds the color pair and the foreground's hex value."""
        self.assertIsNotNone(self.panel.header.findChild(ColorPairWidget))
        self.assertEqual(self.panel.header.hex_label.text(), '#336699')
        Cache().set(Cache.LAST_BRUSH_COLOR, '#ff112233')
        self.assertEqual(self.panel.header.hex_label.text(), '#112233')

    def test_layout_follows_size_and_orientation(self) -> None:
        """Resizing or moving the panel to another dock picks the matching layout."""
        self.panel.resize(300, 1000)
        self.panel.set_orientation(Qt.Orientation.Vertical)
        self.assertEqual(self.panel.picker_layout(), ColorPickerLayout.SIDE_TALL)
        self.panel.resize(300, 600)
        self.panel.set_orientation(Qt.Orientation.Vertical)
        self.assertEqual(self.panel.picker_layout(), ColorPickerLayout.SIDE)
        self.panel.resize(1400, 300)
        self.panel.set_orientation(Qt.Orientation.Horizontal)
        self.assertEqual(self.panel.picker_layout(), ColorPickerLayout.BOTTOM_WIDE)

    def test_screen_pick_sets_and_records_foreground(self) -> None:
        """A picked screen color becomes the foreground and a recent color."""
        self.panel.screen_color_picked.emit(QColor('#ff445566'))
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), '#ff445566')
        self.assertEqual(Cache().get(Cache.RECENT_COLORS), ['#ff445566'])


class ColorDialogTest(IntraPaintTestCase):
    """Tests ColorDialog's comparison, without opening it."""

    def setUp(self) -> None:
        super().setUp()
        AppConfig().set(AppConfig.SAVED_COLORS, [])
        self.dialog = ColorDialog()
        self.dialog.selected_color = QColor('#336699')
        self.dialog.comparison.set_original(QColor('#336699'))
        self.comparison = self.dialog.comparison

    def _click(self, point: QPoint) -> None:
        QtTest.QTest.mouseClick(self.comparison, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)

    def test_uses_dialog_layout_with_comparison(self) -> None:
        """The dialog uses the dialog layout, with the comparison in its header."""
        self.assertEqual(self.dialog.color_picker.picker_layout(), ColorPickerLayout.DIALOG)
        self.assertIs(self.dialog.color_picker.header.findChild(ColorComparison), self.comparison)

    def test_clicking_original_reverts(self) -> None:
        """Clicking the starting color goes back to it; clicking the new color does nothing."""
        self.dialog.selected_color = QColor('#ff0000')
        new_half = QPoint(self.comparison.width() * 3 // 4, self.comparison.height() // 2)
        self._click(new_half)
        self.assertEqual(self.dialog.selected_color, QColor('#ff0000'))
        self._click(self.comparison.original_bounds().center())
        self.assertEqual(self.dialog.selected_color, QColor('#336699'))

    def test_comparison_shows_both_colors(self) -> None:
        """The comparison draws the starting color on the left and the new color on the right."""
        self.dialog.selected_color = QColor('#ff0000')
        image = self.comparison.grab().toImage()
        original_center = self.comparison.original_bounds().center()
        self.assertEqual(image.pixelColor(original_center).rgb(), QColor('#336699').rgb())
        new_center = QPoint(self.comparison.width() * 3 // 4, self.comparison.height() // 2)
        self.assertEqual(image.pixelColor(new_center).rgb(), QColor('#ff0000').rgb())
