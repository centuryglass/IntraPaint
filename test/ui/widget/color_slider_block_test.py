"""Tests GradientSlider, ColorSliderBlock, and the Sliders tab in the color panel."""
from unittest.mock import MagicMock, patch

import numpy as np
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QKeyEvent, QKeySequence, QPalette
from PySide6.QtWidgets import QApplication
from PySide6 import QtTest

from src.config.cache import Cache
from src.hotkey_filter import HotkeyFilter
from src.ui.panel.color_panel import ColorControlPanel
from src.ui.widget.color_picker.color_slider_block import ColorSliderBlock, MODE_RGB, MODE_HSV, MODE_OKLCH, MODES
from src.ui.widget.color_picker.gradient_slider import GradientSlider
from src.util.visual import color_math
from test.base_test_case import IntraPaintTestCase
from test.ui.widget.color_picker_test_utils import press, move, release, SignalRecorder

SLIDER_WIDTH = 300


def _point(slider: GradientSlider, value: float) -> QPointF:
    return QPointF(slider.x_for_value(value), slider.height() / 2)


class GradientSliderTest(IntraPaintTestCase):
    """Tests GradientSlider."""

    def setUp(self) -> None:
        super().setUp()
        self.slider = GradientSlider(0.0, 100.0, step=1.0)
        self.slider.resize(SLIDER_WIDTH, self.slider.sizeHint().height())
        self.changed = SignalRecorder(self.slider.value_changed)
        self.committed = SignalRecorder(self.slider.value_committed)

    def test_drag_changes_then_release_commits(self) -> None:
        """Pressing and dragging emit value_changed only; releasing emits value_committed once."""
        press(self.slider, _point(self.slider, 20))
        move(self.slider, _point(self.slider, 60))
        self.assertAlmostEqual(self.slider.value(), 60, delta=0.5)
        self.assertEqual(len(self.changed.values), 2)
        self.assertEqual(self.committed.values, [])
        release(self.slider, _point(self.slider, 60))
        self.assertEqual(self.committed.values, [self.slider.value()])

    def test_drag_clamps_to_range(self) -> None:
        """Dragging past either end stops at the range limit."""
        press(self.slider, _point(self.slider, 50))
        move(self.slider, QPointF(-50, 5))
        self.assertEqual(self.slider.value(), 0.0)
        move(self.slider, QPointF(SLIDER_WIDTH + 50, 5))
        self.assertEqual(self.slider.value(), 100.0)

    def _key(self, key: Qt.Key) -> None:
        self.slider.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))

    def test_keys_step_and_commit(self) -> None:
        """Arrow keys step by the step size, Home and End jump to the ends, and each change commits."""
        self.slider.set_value(50)
        for key in (Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_Down, Qt.Key.Key_End, Qt.Key.Key_End):
            self._key(key)
        self.assertEqual(self.changed.values, [51.0, 50.0, 49.0, 100.0])
        self.assertEqual(self.committed.values, [51.0, 50.0, 49.0, 100.0])

    def test_focused_slider_gets_arrow_keys_before_hotkeys(self) -> None:
        """A focused slider receives arrow keys even when an application hotkey is bound to them."""
        hotkey = MagicMock(return_value=True)
        binding_id = 'gradient_slider_test_left'
        HotkeyFilter.instance().register_keybinding(binding_id, hotkey, QKeySequence(Qt.Key.Key_Left))
        try:
            self.slider.show()
            self.slider.set_value(50)
            with patch.object(QApplication, 'focusWidget', return_value=self.slider):
                QtTest.QTest.keyClick(self.slider, Qt.Key.Key_Left)
        finally:
            HotkeyFilter.instance().remove_keybinding(binding_id)
        self.assertEqual(self.slider.value(), 49.0)
        hotkey.assert_not_called()

    def test_set_value_is_silent(self) -> None:
        """set_value clamps without emitting."""
        self.slider.set_value(150)
        self.assertEqual(self.slider.value(), 100.0)
        self.assertEqual(self.changed.values, [])

    def test_renders_gradient_and_hatches_transparent_samples(self) -> None:
        """The track shows the gradient's colors, transparent samples show hatching, and an edge line marks the
        boundary."""
        rgba = np.zeros((4, 4))
        rgba[:2] = (1.0, 0.0, 0.0, 1.0)
        self.slider.set_gradient(rgba)
        self.slider.set_value(0)
        image = self.slider.grab().toImage()
        track = self.slider.track_bounds()
        y = int(track.center().y())
        left = image.pixelColor(int(track.left() + 8), y)
        self.assertEqual((left.red(), left.green(), left.blue()), (255, 0, 0))
        palette = self.slider.palette()
        background = palette.color(QPalette.ColorRole.Mid).lightness()
        start = int(track.left() + track.width() * 0.7)
        lightness = {image.pixelColor(x, y).lightness() for x in range(start, start + 16)}
        self.assertIn(background, lightness)
        self.assertLess(min(lightness), background)
        self.assertGreater(max(lightness), background)
        edge_x = int(track.left() + track.width() / 2)
        self.assertEqual(image.pixelColor(edge_x, y).rgb(), palette.color(QPalette.ColorRole.WindowText).rgb())

    def test_has_color_at(self) -> None:
        """Values over transparent samples have no color; checkerboard sliders have color everywhere."""
        rgba = np.zeros((4, 4))
        rgba[:2, 3] = 1.0
        self.slider.set_gradient(rgba)
        self.assertTrue(self.slider.has_color_at(10))
        self.assertFalse(self.slider.has_color_at(90))
        checkered = GradientSlider(0.0, 100.0, checkerboard=True)
        checkered.set_gradient(rgba)
        self.assertTrue(checkered.has_color_at(90))


class ColorSliderBlockTest(IntraPaintTestCase):
    """Tests ColorSliderBlock."""

    def setUp(self) -> None:
        super().setUp()
        Cache().restore_default_options(Cache.COLOR_SLIDER_MODE)
        self.block = ColorSliderBlock()
        self.block.resize(SLIDER_WIDTH, self.block.sizeHint().height())
        self.block.set_color(QColor('#80cc3366'))
        self.changed = SignalRecorder(self.block.color_changed)
        self.committed = SignalRecorder(self.block.color_committed)

    def test_set_color_round_trips_in_every_mode(self) -> None:
        """Setting a color and reading it back gives the same color in each mode, alpha included."""
        colors = ('#ff000000', '#ffffffff', '#80cc3366', '#ff0000ff', '#0012ab34', '#ff808080', '#ff00ff00')
        for mode in MODES:
            self.block.set_mode(mode)
            for color_str in colors:
                self.block.set_color(QColor(color_str))
                self.assertEqual(self.block.selected_color().name(QColor.NameFormat.HexArgb), color_str,
                                 f'{mode} {color_str}')
        self.assertEqual(self.changed.colors, [])

    def test_components_in_each_mode(self) -> None:
        """Each mode shows the color's components in its display units."""
        self.block.set_mode(MODE_RGB)
        self.assertEqual(self.block.components(), (0xcc, 0x33, 0x66))
        self.block.set_mode(MODE_HSV)
        np.testing.assert_allclose(self.block.components(), (340.0, 75.0, 80.0), atol=0.01)
        self.block.set_mode(MODE_OKLCH)
        lightness, chroma, hue = color_math.srgb_to_oklch((0xcc / 255, 0x33 / 255, 0x66 / 255))
        np.testing.assert_allclose(self.block.components(), (lightness * 100, chroma, hue), atol=1e-9)
        self.assertEqual([spin_box.value() for spin_box in self.block.spin_boxes],
                         [round(lightness * 100, 1), round(chroma, 3), round(hue, 1)])

    def test_mode_saved_in_cache(self) -> None:
        """Switching modes saves the mode, and a new block starts in the saved mode."""
        self.block.set_mode(MODE_OKLCH)
        self.assertEqual(Cache().get(Cache.COLOR_SLIDER_MODE), MODE_OKLCH)
        self.assertEqual(ColorSliderBlock().mode(), MODE_OKLCH)

    def test_slider_drag_changes_then_release_commits(self) -> None:
        """Dragging a slider changes that component without committing; releasing commits the color."""
        self.block.set_mode(MODE_RGB)
        green = self.block.sliders[1]
        press(green, _point(green, 0x33))
        move(green, _point(green, 200))
        self.assertAlmostEqual(self.block.selected_color().green(), 200, delta=1)
        self.assertEqual(self.block.selected_color().red(), 0xcc)
        self.assertEqual(self.block.selected_color().alpha(), 0x80)
        self.assertEqual(self.committed.colors, [])
        release(green, _point(green, 200))
        self.assertEqual(self.committed.colors, [self.block.selected_color()])

    def test_spin_box_entry_commits(self) -> None:
        """Entering a spin box value changes and commits the color."""
        self.block.set_mode(MODE_HSV)
        self.block.spin_boxes[2].setValue(40)
        self.assertEqual(self.changed.colors, [self.block.selected_color()])
        self.assertEqual(self.committed.colors, [self.block.selected_color()])
        hue, saturation, value = self.block.components()
        self.assertAlmostEqual(hue, 340.0, delta=0.01)
        self.assertEqual(value, 40.0)

    def test_hue_kept_through_gray(self) -> None:
        """Dragging HSV saturation or OKLCH chroma to zero and back keeps the hue."""
        for mode, chroma_index, hue_index in ((MODE_HSV, 1, 0), (MODE_OKLCH, 1, 2)):
            self.block.set_mode(mode)
            self.block.set_color(QColor('#cc3366'))
            hue = self.block.components()[hue_index]
            slider = self.block.sliders[chroma_index]
            press(slider, QPointF(0, 5))
            release(slider, QPointF(0, 5))
            self.assertEqual(self.block.components()[hue_index], hue, mode)
            self.block.set_color(self.block.selected_color())
            self.assertEqual(self.block.components()[hue_index], hue, mode)

    def test_out_of_gamut_chroma_keeps_slider_and_maps_color(self) -> None:
        """An out-of-gamut OKLCH chroma stays on the slider while the color maps to the gamut edge."""
        self.block.set_mode(MODE_OKLCH)
        self.block.spin_boxes[1].setValue(0.37)
        self.assertEqual(self.block.components()[1], 0.37)
        lightness, _, hue = self.block.components()
        expected = color_math.oklch_to_srgb_in_gamut((lightness / 100, 0.37, hue)) * 255
        color = self.block.selected_color()
        np.testing.assert_allclose((color.red(), color.green(), color.blue()), expected, atol=0.51)
        self.block.set_color(color)
        self.assertEqual(self.block.components()[1], 0.37)


class ColorPanelSlidersTabTest(IntraPaintTestCase):
    """Tests the Sliders tab in ColorControlPanel."""

    def setUp(self) -> None:
        super().setUp()
        Cache().set(Cache.LAST_BRUSH_COLOR, '#ff336699')
        Cache().set(Cache.RECENT_COLORS, [])
        Cache().restore_default_options(Cache.COLOR_SLIDER_MODE)
        self.panel = ColorControlPanel()
        self.block = self.panel.slider_block
        self.block.set_mode(MODE_RGB)
        self.block.resize(SLIDER_WIDTH, self.block.sizeHint().height())

    def test_sliders_follow_foreground(self) -> None:
        """The sliders start on the foreground color and follow changes to it."""
        self.assertEqual(self.block.components(), (0x33, 0x66, 0x99))
        Cache().set(Cache.LAST_BRUSH_COLOR, '#ff112233')
        self.assertEqual(self.block.components(), (0x11, 0x22, 0x33))

    def test_drag_sets_foreground_and_release_records_recent_color(self) -> None:
        """Dragging writes the foreground live without recording it; releasing records it as a recent color."""
        red = self.block.sliders[0]
        press(red, _point(red, 0x33))
        move(red, _point(red, 255))
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), '#ffff6699')
        self.assertEqual(Cache().get(Cache.RECENT_COLORS), [])
        release(red, _point(red, 255))
        self.assertEqual(Cache().get(Cache.RECENT_COLORS), ['#ffff6699'])
        self.assertEqual(self.panel.ring_square.color(), QColor('#ffff6699'))
