"""Tests LoadingWidget's design choice per load, its paused state, and what it draws."""
import sys

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage, QColor, QPalette
from PySide6.QtWidgets import QApplication

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
        diffusion_ring = self.designs[1]
        self.widget.design = diffusion_ring
        self.widget.paused = True
        self.assertTrue(self.widget.paused)
        self.assertEqual(self.widget.phase, diffusion_ring.rest_phase)
        self.widget.message = 'Step 2/30'
        self.assertFalse(self.widget.paused)
        self.assertIsNot(self.widget.design, diffusion_ring)

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
        self.widget.design = self.designs[2]
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
