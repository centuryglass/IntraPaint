"""Tests ruler tick layout, the rulers' mapping to the image viewer, and their placement in ImagePanel."""
import sys

from PySide6.QtCore import QPoint, QPointF, QRect, QSize
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.image.layers.image_stack import ImageStack
from src.ui.panel.image_panel import ImagePanel
from src.ui.panel.image_panel import GENERATION_AREA_RULER_LANE, SELECTION_RULER_LANE, RULER_HIGHLIGHT_LANES
from src.ui.widget.ruler import major_tick_step, minor_tick_step, tick_values, Ruler, MAJOR_TICK_LENGTH, \
    MIN_HIGHLIGHT_CONTRAST
from src.util.visual.contrast_color import contrast_ratio
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

IMAGE_SIZE = QSize(512, 384)
PANEL_SIZE = QSize(800, 600)


class TickStepTest(IntraPaintTestCase):
    """Tests the pure tick spacing functions."""

    def test_major_step_is_smallest_fitting_step(self) -> None:
        """Major steps follow the 1/2/5 x 10^n sequence, choosing the smallest one at least min_spacing apart."""
        self.assertEqual(major_tick_step(1.0, 40.0), 50)
        self.assertEqual(major_tick_step(1.0, 50.0), 50)
        self.assertEqual(major_tick_step(1.0, 51.0), 100)
        self.assertEqual(major_tick_step(8.0, 30.0), 5)
        self.assertEqual(major_tick_step(0.05, 40.0), 1000)
        self.assertEqual(major_tick_step(0.3, 40.0), 200)

    def test_major_step_never_below_one_pixel(self) -> None:
        """At any zoom, major ticks are at least one image pixel apart."""
        self.assertEqual(major_tick_step(100.0, 30.0), 1)

    def test_minor_step_divides_major_step(self) -> None:
        """Minor steps use the most divisions that keep them whole pixels and far enough apart."""
        self.assertEqual(minor_tick_step(50, 1.27), 5)
        self.assertEqual(minor_tick_step(5, 8.0), 1)
        self.assertEqual(minor_tick_step(20, 1.0), 5)
        self.assertEqual(minor_tick_step(200, 0.3), 20)

    def test_minor_step_without_fitting_division(self) -> None:
        """When no division fits, the minor step is the major step, so there are no minor ticks."""
        self.assertEqual(minor_tick_step(1, 100.0), 1)
        self.assertEqual(minor_tick_step(100, 0.05), 100)

    def test_tick_values(self) -> None:
        """Tick values are every multiple of the step within the range, including negative ones."""
        self.assertEqual(tick_values(-3.5, 12.0, 5), [0, 5, 10])
        self.assertEqual(tick_values(-12.0, -1.0, 5), [-10, -5])
        self.assertEqual(tick_values(5.0, 10.0, 5), [5, 10])
        self.assertEqual(tick_values(1.0, 4.0, 5), [])


class ImagePanelRulerTest(IntraPaintTestCase):
    """Tests rulers placed beside an ImagePanel's image viewer."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(IMAGE_SIZE, QSize(256, 256), QSize(8, 8), QSize(2048, 2048))
        self.panel = ImagePanel(self.image_stack, include_rulers=True)
        self.panel.resize(PANEL_SIZE)
        self.panel.show()
        self.viewer = self.panel.image_viewer
        horizontal, vertical = self.panel.rulers
        assert horizontal is not None and vertical is not None
        self.horizontal: Ruler = horizontal
        self.vertical: Ruler = vertical

    def tearDown(self) -> None:
        self.panel.close()
        self.panel.deleteLater()
        super().tearDown()

    def _ruler_point(self, scene_point: QPointF) -> tuple[float, float]:
        """Returns where a scene point appears along the horizontal and vertical rulers."""
        viewport = self.viewer.viewport()
        assert viewport is not None
        global_point = viewport.mapToGlobal(QPointF(self.viewer.mapFromScene(scene_point)))
        return self.horizontal.mapFromGlobal(global_point).x(), self.vertical.mapFromGlobal(global_point).y()

    def _assert_rulers_match_view(self) -> None:
        for scene_point in (QPointF(0.0, 0.0), QPointF(100.0, 50.0), QPointF(IMAGE_SIZE.width(), IMAGE_SIZE.height())):
            expected_x, expected_y = self._ruler_point(scene_point)
            self.assertAlmostEqual(self.horizontal.image_to_ruler(scene_point.x()), expected_x, delta=1.0)
            self.assertAlmostEqual(self.vertical.image_to_ruler(scene_point.y()), expected_y, delta=1.0)

    def test_panels_have_no_rulers_by_default(self) -> None:
        """Rulers are opt-in, so the navigation window's panel has none."""
        panel = ImagePanel(self.image_stack)
        self.assertEqual(panel.rulers, (None, None))

    def test_rulers_match_view_mapping(self) -> None:
        """Image coordinates map to the ruler positions where the viewer shows them, before and after zooming."""
        self._assert_rulers_match_view()
        self.viewer.scene_scale = 8.0
        self._assert_rulers_match_view()
        self.viewer.offset = QPointF(40.0, -25.0)
        self._assert_rulers_match_view()

    def test_resize_reports_view_change(self) -> None:
        """Resizing changes the mapping without a scale or offset signal, so the view reports it for ruler repaints."""
        changes: list[bool] = []
        self.viewer.view_changed.connect(lambda: changes.append(True))
        self.panel.resize(PANEL_SIZE.width() + 200, PANEL_SIZE.height() + 100)
        self.assertGreater(len(changes), 0)
        self._assert_rulers_match_view()

    def test_ticks_follow_zoom(self) -> None:
        """Zooming in narrows the major step, down to single pixels."""
        def _major_step(ruler: Ruler) -> int:
            values = [tick.value for tick in ruler.ticks() if tick.length == MAJOR_TICK_LENGTH]
            return values[1] - values[0]
        default_step = _major_step(self.horizontal)
        self.viewer.scene_scale = 64.0
        self.assertLess(_major_step(self.horizontal), default_step)
        self.assertEqual(_major_step(self.horizontal), 1)

    def test_major_ticks_are_labeled(self) -> None:
        """Every major tick, and only major ticks, carries its image coordinate as a label."""
        ticks = self.horizontal.ticks()
        self.assertGreater(len(ticks), 0)
        for tick in ticks:
            if tick.length == MAJOR_TICK_LENGTH:
                self.assertEqual(tick.label, str(tick.value))
            else:
                self.assertIsNone(tick.label)

    def test_cursor_marker_follows_view_cursor(self) -> None:
        """The cursor markers line up with the viewer's cursor, and clear when it leaves."""
        cursor = QPoint(120, 80)
        self.viewer.set_cursor_pos(cursor)
        global_cursor = self.viewer.mapToGlobal(cursor)
        self.assertEqual(self.horizontal.cursor_position, self.horizontal.mapFromGlobal(global_cursor).x())
        self.assertEqual(self.vertical.cursor_position, self.vertical.mapFromGlobal(global_cursor).y())
        self.viewer.set_cursor_pos(None)
        self.assertIsNone(self.horizontal.cursor_position)
        self.assertIsNone(self.vertical.cursor_position)

    def test_generation_area_highlight(self) -> None:
        """The rulers shade the generation area's extent, and follow it when it moves."""
        self.image_stack.generation_area = QRect(100, 50, 256, 256)
        self.assertEqual([(h.start, h.end) for h in self.horizontal.highlights], [(100, 356)])
        self.assertEqual([(h.start, h.end) for h in self.vertical.highlights], [(50, 306)])
        self.image_stack.generation_area = QRect(0, 10, 256, 256)
        self.assertEqual([(h.start, h.end) for h in self.horizontal.highlights], [(0, 256)])

    def test_generation_area_highlight_hidden_with_generation_controls(self) -> None:
        """Without image generation controls, the generation area isn't highlighted."""
        self.panel.set_image_generation_controls_visible(False)
        self.assertEqual(self.horizontal.highlights, [])

    def test_selection_highlight(self) -> None:
        """The rulers shade the selection's bounds alongside the generation area."""
        selection_layer = self.image_stack.selection_layer
        image = selection_layer.image
        painter = QPainter(image)
        painter.fillRect(QRect(300, 200, 120, 90), QColor(255, 0, 0))
        painter.end()
        selection_layer.image = image
        self.assertIn((300, 420), [(h.start, h.end) for h in self.horizontal.highlights])
        self.assertIn((200, 290), [(h.start, h.end) for h in self.vertical.highlights])

    def test_highlight_setting(self) -> None:
        """Turning off ruler highlights clears them, and turning it back on restores them."""
        self.assertNotEqual(self.horizontal.highlights, [])
        AppConfig().set(AppConfig.SHOW_RULER_HIGHLIGHTS, False)
        self.assertEqual(self.horizontal.highlights, [])
        self.assertEqual(self.vertical.highlights, [])
        AppConfig().set(AppConfig.SHOW_RULER_HIGHLIGHTS, True)
        self.assertNotEqual(self.horizontal.highlights, [])

    def test_visibility_setting(self) -> None:
        """The show-rulers setting hides and shows both rulers."""
        self.assertTrue(self.horizontal.isVisible())
        AppConfig().set(AppConfig.SHOW_RULERS, False)
        self.assertFalse(self.horizontal.isVisible())
        self.assertFalse(self.vertical.isVisible())
        AppConfig().set(AppConfig.SHOW_RULERS, True)
        self.assertTrue(self.horizontal.isVisible())
        self.assertTrue(self.vertical.isVisible())

    def test_generation_area_color_setting(self) -> None:
        """The generation area highlight uses its configured color, and follows changes to it."""
        AppConfig().set(AppConfig.RULER_GENERATION_AREA_COLOR, '#00ff00')
        self.assertEqual([h.color for h in self.horizontal.highlights], [QColor('#00ff00')])
        AppConfig().set(AppConfig.RULER_GENERATION_AREA_COLOR, '#ff00ff')
        self.assertEqual([h.color for h in self.vertical.highlights], [QColor('#ff00ff')])

    def test_font_size_setting(self) -> None:
        """A larger ruler font makes both rulers and the corner between them thicker."""
        initial_thickness = self.horizontal.thickness
        AppConfig().set(AppConfig.RULER_FONT_SIZE, AppConfig().get(AppConfig.RULER_FONT_SIZE) * 3)
        self.assertGreater(self.horizontal.thickness, initial_thickness)
        self.assertEqual(self.vertical.thickness, self.horizontal.thickness)
        self.assertEqual(self.horizontal.maximumHeight(), self.horizontal.thickness)
        self.assertEqual(self.vertical.maximumWidth(), self.vertical.thickness)
        corner = self.panel._ruler_corner  # pylint: disable=protected-access
        assert corner is not None
        self.assertEqual(corner.maximumSize(), QSize(self.vertical.thickness, self.horizontal.thickness))

    def test_highlight_lanes(self) -> None:
        """The generation area and the selection get separate lanes, so their bars never overlap."""
        selection_layer = self.image_stack.selection_layer
        image = selection_layer.image
        painter = QPainter(image)
        painter.fillRect(QRect(300, 200, 120, 90), QColor(255, 0, 0))
        painter.end()
        selection_layer.image = image
        for ruler in (self.horizontal, self.vertical):
            self.assertEqual(ruler.highlight_lanes, RULER_HIGHLIGHT_LANES)
            self.assertEqual(sorted(h.lane for h in ruler.highlights),
                             sorted([GENERATION_AREA_RULER_LANE, SELECTION_RULER_LANE]))

    def test_highlight_setting_frees_lane_space(self) -> None:
        """Turning off highlights removes their lanes, making the rulers thinner, and turning it on restores them."""
        thickness_with_lanes = self.horizontal.thickness
        AppConfig().set(AppConfig.SHOW_RULER_HIGHLIGHTS, False)
        self.assertEqual(self.horizontal.highlight_lanes, 0)
        self.assertLess(self.horizontal.thickness, thickness_with_lanes)
        self.assertEqual(self.vertical.thickness, self.horizontal.thickness)
        AppConfig().set(AppConfig.SHOW_RULER_HIGHLIGHTS, True)
        self.assertEqual(self.horizontal.thickness, thickness_with_lanes)

    def test_highlight_color_contrasts_with_dark_ruler(self) -> None:
        """A dark highlight color is lightened to stand out on a dark ruler background."""
        palette = QPalette(self.horizontal.palette())
        background = QColor('#1b1e20')
        palette.setColor(QPalette.ColorRole.Button, background)
        self.horizontal.setPalette(palette)
        AppConfig().set(AppConfig.RULER_GENERATION_AREA_COLOR, '#995f5555')
        highlight = self.horizontal.highlights[0]
        self.assertGreaterEqual(contrast_ratio(self.horizontal.highlight_color(highlight), background),
                                MIN_HIGHLIGHT_CONTRAST)
