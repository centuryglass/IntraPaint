"""Tests ColorPickerParts' shared color, ColorControlPanel's planned sections, and ColorDialog."""
from PySide6.QtCore import QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDockWidget, QLabel, QMainWindow, QScrollArea, QWidget
from PySide6 import QtTest

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.ui.modal.color_dialog import ColorDialog
from src.ui.layout.panel_fit import FitContent, Orientation
from src.ui.panel.color_panel import ColorControlPanel
from src.ui.widget.color_pair_widget import ColorPairWidget
from src.ui.widget.color_picker.color_comparison import ColorComparison
from src.ui.widget.color_picker.color_picker_parts import ColorPickerParts
from src.ui.widget.color_picker.color_slider_block import MODE_RGB
from src.ui.widget.color_picker.okhsv_ring_square import MIN_SIZE as RING_MIN_SIZE
from test.base_test_case import IntraPaintTestCase
from test.ui.widget.color_picker_test_utils import press, move, release, SignalRecorder

WIDGET_SIZE = 200
SLIDER_WIDTH = 300


class ColorPickerPartsTest(IntraPaintTestCase):
    """Tests that every part of ColorPickerParts edits one color."""

    def setUp(self) -> None:
        super().setUp()
        self.picker = ColorPickerParts()
        self.picker.set_current_color(QColor('#336699'))
        self.picker.ring_square.resize(WIDGET_SIZE, WIDGET_SIZE)
        self.selected = SignalRecorder(self.picker.color_selected)
        self.committed = SignalRecorder(self.picker.color_committed)

    def _enter_hex(self, text: str) -> None:
        field = self.picker.header.hex_field
        field.setText(text)
        QtTest.QTest.keyClick(field, Qt.Key.Key_Return)

    def test_set_color_round_trips_and_shows_everywhere(self) -> None:
        """Setting a color reads back unchanged and shows in every part, without committing."""
        color = QColor('#80cc3366')
        self.picker.set_current_color(color)
        self.assertEqual(self.picker.selected_color(), color)
        self.assertEqual(self.picker.ring_square.color(), color)
        self.assertEqual(self.picker.slider_block.selected_color(), color)
        self.assertEqual(self.picker.header.hex_field.color(), color)
        self.assertEqual(self.picker.slider_block.alpha_slider.value(), 0x80)
        self.assertEqual(self.picker.header.hex_field.text(), '#80cc3366')
        self.assertEqual(self.selected.colors, [color])
        self.assertEqual(self.committed.colors, [])

    def test_hex_field_accepts_argb(self) -> None:
        """Entering #AARRGGBB selects that color and alpha, and commits it."""
        self._enter_hex('#80112233')
        expected = QColor(0x11, 0x22, 0x33, 0x80)
        self.assertEqual(self.picker.selected_color(), expected)
        self.assertEqual(self.picker.slider_block.alpha_slider.value(), 0x80)
        self.assertEqual(self.picker.ring_square.color(), expected)
        self.assertEqual(self.selected.colors, [expected])
        self.assertEqual(self.committed.colors, [expected])

    def test_invalid_hex_restores_field(self) -> None:
        """Invalid hex text reverts to the current color without emitting."""
        self._enter_hex('nonsense')
        self.assertEqual(self.picker.header.hex_field.text(), '#336699')
        self.assertEqual(self.selected.colors, [])
        self.assertEqual(self.committed.colors, [])

    def test_alpha_slider_drag_commits_on_release(self) -> None:
        """Dragging the alpha slider changes alpha everywhere without committing; releasing it commits."""
        slider = self.picker.slider_block.alpha_slider
        slider.resize(SLIDER_WIDTH, slider.sizeHint().height())
        press(slider, QPointF(slider.x_for_value(200), 5))
        move(slider, QPointF(slider.x_for_value(100), 5))
        self.assertEqual(self.picker.selected_color().alpha(), 100)
        self.assertEqual(self.picker.ring_square.color().alpha(), 100)
        self.assertEqual(self.picker.header.hex_field.text(), '#64336699')
        self.assertEqual(self.committed.colors, [])
        release(slider, QPointF(slider.x_for_value(100), 5))
        self.assertEqual([color.alpha() for color in self.committed.colors], [100])

    def test_ring_drag_updates_other_parts_and_commits_on_release(self) -> None:
        """Dragging in the square updates the sliders and hex field; only the release commits."""
        ring_square = self.picker.ring_square
        press(ring_square, ring_square.point_for_saturation_value(0.0, 1.0))
        self.assertEqual(self.picker.selected_color(), QColor('#ffffff'))
        self.assertEqual(self.picker.header.hex_field.text(), '#ffffff')
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
        self.picker.header.screen_color_picked.emit(QColor('#123456'))
        self.assertEqual(self.picker.selected_color(), QColor('#123456'))
        self.assertEqual(self.committed.colors, [QColor('#123456')])

    def test_screen_pick_preview_shows_cursor_position(self) -> None:
        """While picking, the header shows the cursor position, and hides it when picking stops."""
        label = self.picker.header.picking_label
        self.picker.header.color_previewed.emit(QPoint(12, 34), QColor('#000000'))
        self.assertFalse(label.isHidden())
        self.assertIn('12,34', label.text())
        self.picker.header.stopped_color_picking.emit()
        self.assertTrue(label.isHidden())


    def test_slider_summary_names_components_and_alpha(self) -> None:
        """The sliders' summary gives the mode, its three components and alpha."""
        self.picker.slider_block.set_mode(MODE_RGB)
        self.picker.set_current_color(QColor(0x33, 0x66, 0x99, 0x80))
        self.assertEqual(self.picker.slider_block.summary(), 'RGB 51, 102, 153, alpha 128')


def _overflows(need: QSize, space: QSize) -> bool:
    return need.width() > space.width() or need.height() > space.height()


class ColorControlPanelTest(IntraPaintTestCase):
    """Tests ColorControlPanel's header, its sections' planning and its size hints."""

    def setUp(self) -> None:
        super().setUp()
        Cache().set(Cache.LAST_BRUSH_COLOR, '#ff336699')
        Cache().set(Cache.RECENT_COLORS, ['#ff112233', '#ff445566'])
        AppConfig().set(AppConfig.SAVED_COLORS, ['#ffaabbcc'])
        self.panel = ColorControlPanel()

    def _collapsed(self) -> list[str]:
        return [section.title for section in self.panel.sections if section.is_collapsed()]

    def test_header_shows_color_pair(self) -> None:
        """The foreground panel's header holds the color pair and the foreground's hex value."""
        header = self.panel.parts.header
        self.assertIsNotNone(header.findChild(ColorPairWidget))
        self.assertEqual(header.hex_field.text(), '#336699')
        Cache().set(Cache.LAST_BRUSH_COLOR, '#ff112233')
        self.assertEqual(header.hex_field.text(), '#112233')

    def test_sections_in_order_with_summaries(self) -> None:
        """Wheel, Sliders, Recent and Saved, each with a summary for its collapsed header."""
        self.assertEqual([section.title for section in self.panel.sections], ['Wheel', 'Sliders', 'Recent', 'Saved'])
        for section in self.panel.sections:
            with self.subTest(section=section.title):
                self.assertNotEqual(section.summary(), '')
        self.assertEqual(self.panel.sections[2].summary(), '2 colors')
        self.assertEqual(self.panel.sections[3].summary(), '1 of 64')

    def test_roomy_space_expands_every_section(self) -> None:
        """With room for everything, no section collapses, and the ring grows past its smallest size."""
        for orientation, space in ((Orientation.SIDE, QSize(320, 1000)), (Orientation.STRIP, QSize(1400, 320))):
            with self.subTest(orientation=orientation):
                self.panel.set_fit_space(orientation, space)
                self.assertEqual(self._collapsed(), [])
                self.assertGreater(self.panel.parts.ring_square.width(), RING_MIN_SIZE)

    def test_a_section_collapses_only_when_it_does_not_fit(self) -> None:
        """Each section a plan collapses would make the content overflow its space if expanded, and the planned
        content itself fits. Each size gets a new panel, since a plan keeps the previous one's placement within
        `HYSTERESIS` of fitting."""
        spaces = {Orientation.SIDE: (QSize(260, 300), QSize(260, 420), QSize(260, 560), QSize(400, 360)),
                  Orientation.STRIP: (QSize(500, 200), QSize(700, 200), QSize(900, 240))}
        for orientation, sizes in spaces.items():
            for space in sizes:
                with self.subTest(orientation=orientation, space=space):
                    panel = ColorControlPanel()
                    planner = panel._planner  # pylint: disable=protected-access
                    panel.set_fit_space(orientation, space)
                    placement = planner.placement
                    assert placement is not None
                    self.assertFalse(_overflows(planner.measure_placement(placement), space))
                    for index, form in enumerate(placement):
                        if form is None:
                            expanded = tuple(0 if i == index else f for i, f in enumerate(placement))
                            self.assertTrue(_overflows(planner.measure_placement(expanded), space),
                                            panel.sections[index].title)

    def test_grown_ring_keeps_the_content_in_its_space(self) -> None:
        """The ring grows into spare room only as far as the content still fits the space."""
        for orientation, space in ((Orientation.SIDE, QSize(300, 700)), (Orientation.STRIP, QSize(900, 260))):
            with self.subTest(orientation=orientation):
                self.panel.set_fit_space(orientation, space)
                self.panel.resize(space)
                self.assertFalse(_overflows(self.panel.layout().minimumSize(), space))

    def test_strip_puts_sections_side_by_side(self) -> None:
        """A strip stacks the header in its first column and puts the sections in columns after it."""
        self.panel.resize(1400, 260)
        self.panel.show()
        self.panel.set_fit_space(Orientation.STRIP, QSize(1400, 260))
        self.panel.layout().activate()
        header = self.panel.parts.header
        wheel, sliders = self.panel.sections[:2]
        self.assertLess(header.geometry().right(), wheel.mapTo(self.panel, QPoint()).x())
        self.assertLess(wheel.mapTo(self.panel, QPoint()).x(), sliders.mapTo(self.panel, QPoint()).x())
        self.panel.hide()

    def test_fit_base_size_collapses_every_section(self) -> None:
        """A `FitContent` host measures the panel with every section collapsed and the ring at its smallest."""
        self.panel.set_fit_space(Orientation.SIDE, QSize(320, 1000))
        base = self.panel.fit_base_size(Orientation.SIDE)
        self.assertEqual(self._collapsed(), ['Wheel', 'Sliders', 'Recent', 'Saved'])
        self.panel.set_fit_space(Orientation.SIDE, QSize(320, 1000))
        self.assertEqual(self.panel.fit_base_size(Orientation.SIDE), base)

    def test_minimum_size_does_not_depend_on_history(self) -> None:
        """Outside a `DockPanel`, the minimum size is the smallest plan's for the orientation, whatever sizes the
        panel had before."""
        sizes = (QSize(1400, 300), QSize(300, 1000), QSize(300, 600), QSize(240, 300), QSize(700, 200))
        for orientation in (Qt.Orientation.Vertical, Qt.Orientation.Horizontal):
            self.panel.set_orientation(orientation)
            expected = self.panel.minimumSizeHint()
            for size in sizes:
                with self.subTest(orientation=orientation, size=size):
                    self.panel.resize(size)
                    self.panel.set_orientation(orientation)
                    self.assertEqual(self.panel.minimumSizeHint(), expected)

    def test_minimum_size_follows_the_font(self) -> None:
        """Changing the font measures the smallest plans again. A strip's stacks the header's fields, so its height
        follows the font."""
        self.panel.set_orientation(Qt.Orientation.Horizontal)
        before = self.panel.minimumSizeHint()
        font = self.panel.font()
        font.setPointSize(font.pointSize() * 2)
        self.panel.setFont(font)
        self.assertGreater(self.panel.minimumSizeHint().height(), before.height())

    def test_shrinking_floating_dock_keeps_its_size(self) -> None:
        """A floating dock shrinking from a tall size keeps the size it was given."""
        window = QMainWindow()
        window.setCentralWidget(QLabel('central'))
        dock = QDockWidget('color', window)
        dock.setWidget(self.panel)
        window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        window.resize(1600, 1000)
        window.show()
        dock.setFloating(True)
        self.panel.set_orientation(Qt.Orientation.Vertical)
        dock.resize(456, 1200)
        self.assertEqual(self._collapsed(), [])
        dock.resize(456, 400)
        self.assertEqual(dock.height(), 400)
        window.close()

    def test_scroll_area_uses_visible_size(self) -> None:
        """In a scroll area the panel plans for the visible area, so nothing scrolls."""
        for orientation, size in ((Qt.Orientation.Vertical, QSize(680, 420)), (Qt.Orientation.Horizontal,
                                                                                QSize(700, 260))):
            with self.subTest(orientation=orientation, size=size):
                panel = ColorControlPanel()
                area = QScrollArea()
                area.setWidgetResizable(True)
                area.setWidget(panel)
                area.show()
                try:
                    panel.set_orientation(orientation)
                    area.resize(size)
                    self.assertEqual(area.verticalScrollBar().maximum(), 0)
                    self.assertEqual(area.horizontalScrollBar().maximum(), 0)
                    self.assertGreaterEqual(panel.width(), area.viewport().width())
                finally:
                    area.hide()

    def test_overflow_content_is_empty(self) -> None:
        """No control is optional, so the More popover never gets any from the panel."""
        overflow = self.panel.overflow_content()
        self.assertEqual(overflow.findChildren(QWidget), [])
        self.assertIsInstance(self.panel, FitContent)

    def test_screen_pick_sets_and_records_foreground(self) -> None:
        """A picked screen color becomes the foreground and a recent color."""
        self.panel.parts.header.screen_color_picked.emit(QColor('#ff445566'))
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), '#ff445566')
        self.assertEqual(Cache().get(Cache.RECENT_COLORS)[0], '#ff445566')


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

    def test_header_holds_comparison(self) -> None:
        """The comparison sits in the picker's header."""
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
