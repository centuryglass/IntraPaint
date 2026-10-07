"""Tests the OKHSV ring + square, hex parsing, and the ring in the color panel."""
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor

from src.config.cache import Cache
from src.ui.panel.color_panel import ColorControlPanel
from src.ui.widget.color_picker.alpha_hex_row import parse_hex_color, format_hex_color
from src.ui.widget.color_picker.okhsv_ring_square import OkhsvRingSquare, MAX_SQUARE_RENDER_SIZE
from src.util.visual import color_math
from test.base_test_case import IntraPaintTestCase
from test.ui.widget.color_picker_test_utils import press as _press, move as _move, release as _release, \
    SignalRecorder

WIDGET_SIZE = 200


class HexParsingTest(IntraPaintTestCase):
    """Tests parse_hex_color and format_hex_color."""

    def test_accepts_supported_forms(self) -> None:
        """#RGB, #RRGGBB and #AARRGGBB parse, with or without the #."""
        self.assertEqual(parse_hex_color('#f00'), QColor(255, 0, 0, 255))
        self.assertEqual(parse_hex_color('#112233'), QColor(0x11, 0x22, 0x33, 255))
        self.assertEqual(parse_hex_color('#80112233'), QColor(0x11, 0x22, 0x33, 0x80))
        self.assertEqual(parse_hex_color(' 80112233 '), QColor(0x11, 0x22, 0x33, 0x80))

    def test_rejects_other_text(self) -> None:
        """Color names, wrong lengths and non-hex digits don't parse."""
        for text in ('red', '#12345', '#1234567', '#1122334455', '#gg0000', ''):
            self.assertIsNone(parse_hex_color(text), text)

    def test_format(self) -> None:
        """Opaque colors drop the alpha digits."""
        self.assertEqual(format_hex_color(QColor(0x11, 0x22, 0x33)), '#112233')
        self.assertEqual(format_hex_color(QColor(0x11, 0x22, 0x33, 0x80)), '#80112233')


class OkhsvRingSquareTest(IntraPaintTestCase):
    """Tests OkhsvRingSquare."""

    def setUp(self) -> None:
        super().setUp()
        self.widget = OkhsvRingSquare()
        self.widget.resize(WIDGET_SIZE, WIDGET_SIZE)
        self.widget.set_okhsv(30.0, 0.5, 0.5)
        self.changed = SignalRecorder(self.widget.color_changed)
        self.committed = SignalRecorder(self.widget.color_committed)

    def test_square_press_sets_saturation_and_value(self) -> None:
        """A press in the square sets saturation and value from the point and keeps the hue."""
        _press(self.widget, self.widget.point_for_saturation_value(0.25, 0.75))
        tolerance = 1.0 / self.widget.square_bounds().width()
        self.assertAlmostEqual(self.widget.saturation, 0.25, delta=tolerance)
        self.assertAlmostEqual(self.widget.value, 0.75, delta=tolerance)
        self.assertEqual(self.widget.hue, 30.0)

    def test_ring_press_sets_hue(self) -> None:
        """A press on the ring sets the hue from the angle and keeps saturation and value."""
        for hue in (0.0, 120.0, 264.0, 350.0):
            _press(self.widget, self.widget.point_for_hue(hue))
            _release(self.widget, self.widget.point_for_hue(hue))
            self.assertAlmostEqual(self.widget.hue, hue, delta=0.5)
            self.assertEqual(self.widget.saturation, 0.5)
            self.assertEqual(self.widget.value, 0.5)

    def test_press_outside_ring_and_square_does_nothing(self) -> None:
        """A press in a corner, outside the ring, is ignored, and so is its release."""
        _press(self.widget, QPointF(1, 1))
        _release(self.widget, QPointF(1, 1))
        self.assertEqual((self.widget.hue, self.widget.saturation, self.widget.value), (30.0, 0.5, 0.5))
        self.assertEqual(self.changed.colors, [])
        self.assertEqual(self.committed.colors, [])

    def test_drag_changes_without_committing_until_release(self) -> None:
        """Dragging emits color_changed only; releasing emits color_committed once with the final color."""
        _press(self.widget, self.widget.point_for_saturation_value(0.1, 0.9))
        _move(self.widget, self.widget.point_for_saturation_value(0.5, 0.8))
        _move(self.widget, self.widget.point_for_saturation_value(0.9, 0.7))
        self.assertEqual(len(self.changed.colors), 3)
        self.assertEqual(self.committed.colors, [])
        _release(self.widget, self.widget.point_for_saturation_value(0.9, 0.7))
        self.assertEqual(self.committed.colors, [self.widget.color()])
        self.assertEqual(self.changed.colors[-1], self.widget.color())

    def test_drag_continues_outside_the_square(self) -> None:
        """A drag started in the square clamps to its edge instead of switching to the ring."""
        _press(self.widget, self.widget.point_for_saturation_value(0.5, 0.5))
        _move(self.widget, QPointF(WIDGET_SIZE - 1, 1))
        self.assertEqual((self.widget.hue, self.widget.saturation, self.widget.value), (30.0, 1.0, 1.0))

    def test_set_color_round_trips(self) -> None:
        """Setting a color and reading it back gives the same 8-bit color, alpha included."""
        for color_str in ('#ff000000', '#ffffffff', '#80cc3366', '#ff0000ff', '#0012ab34', '#ff808080'):
            self.widget.set_color(QColor(color_str))
            self.assertEqual(self.widget.color().name(QColor.NameFormat.HexArgb), color_str)

    def test_gray_and_black_keep_hue(self) -> None:
        """A gray keeps the current hue, and black also keeps the current saturation."""
        self.widget.set_color(QColor('#808080'))
        self.assertEqual(self.widget.hue, 30.0)
        self.assertEqual(self.widget.saturation, 0.0)
        self.widget.set_okhsv(200.0, 0.6, 0.5)
        self.widget.set_color(QColor('#000000'))
        self.assertEqual((self.widget.hue, self.widget.saturation, self.widget.value), (200.0, 0.6, 0.0))

    def test_set_color_does_not_emit(self) -> None:
        """set_color updates silently."""
        self.widget.set_color(QColor('#336699'))
        self.assertEqual(self.changed.colors, [])
        self.assertEqual(self.committed.colors, [])

    def test_renders_selected_hue_in_square(self) -> None:
        """The square shows the selected hue's OKHSV colors."""
        self.widget.set_okhsv(140.0, 1.0, 1.0)
        image = self.widget.grab().toImage()
        for saturation, value in ((0.0, 1.0), (0.85, 0.85), (0.5, 0.2), (0.2, 0.6)):
            pixel = image.pixelColor(self.widget.point_for_saturation_value(saturation, value).toPoint())
            expected = color_math.okhsv_to_srgb((140.0, saturation, value)) * 255
            for channel, expected_channel in zip((pixel.red(), pixel.green(), pixel.blue()), expected):
                self.assertAlmostEqual(channel, expected_channel, delta=6)


    def test_renders_okhsv_hues_on_ring(self) -> None:
        """The ring shows each hue's full-saturation, full-value OKHSV color where a press selects that hue."""
        image = self.widget.grab().toImage()
        for hue in (0.0, 45.0, 120.0, 200.0, 300.0):
            pixel = image.pixelColor(self.widget.point_for_hue(hue).toPoint())
            expected = color_math.okhsv_to_srgb((hue, 1.0, 1.0)) * 255
            for channel, expected_channel in zip((pixel.red(), pixel.green(), pixel.blue()), expected):
                self.assertAlmostEqual(channel, expected_channel, delta=8, msg=f'hue {hue}')

    def test_large_square_renders_at_capped_resolution(self) -> None:
        """A large square scales up a capped render, still matching the selected hue's colors."""
        self.widget.resize(1200, 1200)
        self.widget.set_okhsv(140.0, 1.0, 1.0)
        image = self.widget.grab().toImage()
        self.assertLessEqual(self.widget._get_square_image().width(), MAX_SQUARE_RENDER_SIZE)
        for saturation, value in ((0.0, 1.0), (0.85, 0.85), (0.5, 0.2)):
            pixel = image.pixelColor(self.widget.point_for_saturation_value(saturation, value).toPoint())
            expected = color_math.okhsv_to_srgb((140.0, saturation, value)) * 255
            for channel, expected_channel in zip((pixel.red(), pixel.green(), pixel.blue()), expected):
                self.assertAlmostEqual(channel, expected_channel, delta=6)


class ColorPanelWheelTabTest(IntraPaintTestCase):
    """Tests the Wheel tab in ColorControlPanel."""

    def setUp(self) -> None:
        super().setUp()
        Cache().set(Cache.LAST_BRUSH_COLOR, '#ff336699')
        Cache().set(Cache.RECENT_COLORS, [])
        self.panel = ColorControlPanel()
        self.ring_square = self.panel.ring_square
        self.ring_square.resize(WIDGET_SIZE, WIDGET_SIZE)

    def test_wheel_shows_foreground(self) -> None:
        """The wheel starts on the foreground color and follows changes to it."""
        self.assertEqual(self.ring_square.color(), QColor('#ff336699'))
        Cache().set(Cache.LAST_BRUSH_COLOR, '#ff112233')
        self.assertEqual(self.ring_square.color(), QColor('#ff112233'))

    def test_drag_sets_foreground_and_release_records_recent_color(self) -> None:
        """Dragging writes the foreground live without recording it; releasing records it as a recent color."""
        _press(self.ring_square, self.ring_square.point_for_saturation_value(0.0, 1.0))
        _move(self.ring_square, self.ring_square.point_for_saturation_value(0.0, 0.0))
        self.assertEqual(Cache().get(Cache.LAST_BRUSH_COLOR), '#ff000000')
        self.assertEqual(Cache().get(Cache.RECENT_COLORS), [])
        _release(self.ring_square, self.ring_square.point_for_saturation_value(0.0, 0.0))
        self.assertEqual(Cache().get(Cache.RECENT_COLORS), ['#ff000000'])
