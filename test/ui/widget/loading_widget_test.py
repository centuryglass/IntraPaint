"""Tests LoadingWidget's design choice per load, its paused state, and what it draws."""
import sys

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage, QColor, QPalette
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.ui.loading.diffusion_ring import DiffusionRing
from src.ui.loading.loading_designs import load_loading_designs
from src.ui.widget.loading_widget import LoadingWidget
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

GOLDEN_DIR = 'test/resources/test_images/loading'
WIDGET_SIZE = 200


class LoadingWidgetTest(IntraPaintTestCase):
    """Tests LoadingWidget with the shipped designs."""

    def setUp(self) -> None:
        super().setUp()
        self.designs = load_loading_designs()
        self.by_label = {design.label: design for design in self.designs}
        self.widget = LoadingWidget(message='Loading...', designs=self.designs)
        self.widget.resize(WIDGET_SIZE, WIDGET_SIZE)

    def test_each_show_picks_a_new_design(self) -> None:
        """Showing the widget starts a new load with a design other than the last one."""
        previous = self.widget.design
        for _ in range(10):
            self.widget.show()
            self.assertIsNot(self.widget.design, previous)
            self.assertFalse(self.widget.paused)
            previous = self.widget.design
            self.widget.hide()

    def test_pause_holds_rest_frame(self) -> None:
        """Pausing shows the design's rest frame, and unpausing starts a new load with another design."""
        self.widget.show()
        diffusion_ring = self.by_label['Diffusion Ring']
        self.widget.design = diffusion_ring
        self.widget.paused = True
        self.assertTrue(self.widget.paused)
        self.assertEqual(self.widget.phase, diffusion_ring.rest_phase)
        self.widget.message = 'Step 2/30'
        self.assertFalse(self.widget.paused)
        self.assertIsNot(self.widget.design, diffusion_ring)

    def test_static_indicator_holds_rest_frame(self) -> None:
        """With the static option set, a load holds one design's rest frame, and message changes keep it."""
        AppConfig().set(AppConfig.STATIC_LOADING_INDICATOR, True)
        self.widget.show()
        design = self.widget.design
        self.assertEqual(self.widget.phase, design.rest_phase)
        self.assertFalse(self.widget.paused)
        self.widget.message = 'Step 2/30'
        self.assertIs(self.widget.design, design)
        self.assertEqual(self.widget.phase, design.rest_phase)
        self.widget.hide()
        self.widget.show()
        self.assertIsNot(self.widget.design, design)
        self.assertEqual(self.widget.phase, self.widget.design.rest_phase)

    def test_loop_restart_tells_design(self) -> None:
        """A running animation's phase wrapping to a new loop calls the design's next_loop, and pausing doesn't."""
        ring = self.by_label['Diffusion Ring']
        assert isinstance(ring, DiffusionRing)
        self.widget.show()
        self.widget.design = ring
        shown = ring.current_image
        self.widget.phase = 0.9
        self.assertEqual(ring.current_image, shown)
        self.widget.phase = 0.01
        self.assertNotEqual(ring.current_image, shown)
        self.widget.paused = True
        shown = ring.current_image
        self.widget.phase = 0.0
        self.assertEqual(ring.current_image, shown)

    def test_pause_before_show(self) -> None:
        """A widget paused before it ever animated still shows a rest frame, as in timelapse mode."""
        self.widget.paused = True
        self.assertTrue(self.widget.paused)
        self.assertEqual(self.widget.phase, self.widget.design.rest_phase)

    def test_message_while_hidden_does_not_animate(self) -> None:
        """Setting a message on a hidden widget doesn't start the animation."""
        self.widget.message = 'Loading model'
        self.assertFalse(self.widget.paused)
        self.assertEqual(self.widget.message, 'Loading model')

    def test_render_golden(self) -> None:
        """The widget draws the scrim, the design and the message, on dark and light themes."""
        self.widget.design = self.by_label['Pixel Orbit: ember']
        self.widget.phase = 0.3
        for theme, window_color in (('dark', QColor('#1e2128')), ('light', QColor('#eef0f3'))):
            with self.subTest(theme=theme):
                palette = self.widget.palette()
                palette.setColor(QPalette.ColorRole.Window, window_color)
                self.widget.setPalette(palette)
                image = QImage(WIDGET_SIZE, WIDGET_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
                image.fill(Qt.GlobalColor.transparent)
                self.widget.render(image, QPoint())
                self.assert_image_matches_golden(image, f'{GOLDEN_DIR}/loading_widget_{theme}.png')

    def test_font_size_depends_only_on_bounds(self) -> None:
        """The message size scales with the widget's bounds and doesn't change with the message."""
        def drawn_size() -> int:
            return self.widget._font_pixel_size  # pylint: disable=protected-access

        self.widget.show()
        small = drawn_size()
        self.widget.message = 'A much longer loading message than before'
        self.assertEqual(drawn_size(), small)
        self.widget.resize(WIDGET_SIZE * 4, WIDGET_SIZE * 4)
        self.assertEqual(drawn_size(), small * 4)
