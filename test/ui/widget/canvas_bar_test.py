"""Tests the canvas bar's hint pairs, zoom field, Reset view, and what it moves out as the image panel narrows."""
import sys

from PySide6.QtCore import QPointF, QSize
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QPushButton

from src.config.application_config import AppConfig
from src.image.layers.image_stack import ImageStack
from src.ui.panel.image_panel import ImagePanel
from src.ui.widget.canvas_bar import CanvasBar, split_hint_pairs
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

IMAGE_SIZE = QSize(512, 384)
PANEL_HEIGHT = 600
WIDE = 2000
HINT_TEXT = 'A: first pair - B: second pair<br/>C: third pair - D: fourth pair</br>E: fifth pair'


class SplitHintPairsTest(IntraPaintTestCase):
    """Tests splitting a tool's input hint into pairs."""

    def test_splits_on_line_breaks_and_dashes(self) -> None:
        """Line breaks, including the malformed </br>, and " - " separate pairs, and empty pairs are dropped."""
        self.assertEqual(split_hint_pairs(HINT_TEXT),
                         ['A: first pair', 'B: second pair', 'C: third pair', 'D: fourth pair', 'E: fifth pair'])
        self.assertEqual(split_hint_pairs('A: pick color - <br/>B: pan'), ['A: pick color', 'B: pan'])
        self.assertEqual(split_hint_pairs(''), [])


class CanvasBarTest(IntraPaintTestCase):
    """Tests the bar under an ImagePanel with rulers and the navigation button."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(IMAGE_SIZE, QSize(256, 256), QSize(8, 8), QSize(2048, 2048))
        self.panel = ImagePanel(self.image_stack, include_rulers=True, include_navigation_button=True)
        self.panel.resize(WIDE, PANEL_HEIGHT)
        self.panel.show()
        self.viewer = self.panel.image_viewer
        bar = self.panel.control_bar
        assert bar is not None
        self.bar: CanvasBar = bar
        self.panel.set_control_hint(HINT_TEXT)

    def tearDown(self) -> None:
        self.panel.close()
        self.panel.deleteLater()
        super().tearDown()

    def _resize_bar(self, width: int) -> None:
        """Resizes the panel so the bar gets `width`."""
        self.panel.resize(self.panel.width() + width - self.bar.width(), PANEL_HEIGHT)
        self.assertEqual(self.bar.width(), width)

    def _visible(self, name: str) -> bool:
        """Returns whether the bar's widget at a private attribute shows."""
        return getattr(self.bar, name).isVisibleTo(self.bar)

    def test_wide_bar_shows_everything(self) -> None:
        """With room to spare, every hint pair, Rulers, the navigation button and Reset view's label show, with no
        "?" or "..."."""
        self.assertEqual(self.bar.shown_hint_count(), 5)
        self.assertFalse(self._visible('_hint_button'))
        self.assertTrue(self._visible('_rulers_button'))
        self.assertTrue(self._visible('_navigation_button'))
        self.assertFalse(self._visible('_more_button'))
        labeled, glyph = self.bar.reset_buttons
        self.assertTrue(labeled.isVisibleTo(self.bar))
        self.assertFalse(glyph.isVisibleTo(self.bar))

    def test_narrowing_moves_hints_then_labels_then_toggles(self) -> None:
        """Hint pairs leave from the end into "?" first, then Reset view's label gives way to its glyph, then Rulers
        and the navigation button move into "..."."""
        labeled, _ = self.bar.reset_buttons
        steps: list[tuple[int, bool, bool]] = []
        for width in range(WIDE, self.bar.minimumSizeHint().width() - 1, -10):
            self._resize_bar(width)
            state = (self.bar.shown_hint_count(), labeled.isVisibleTo(self.bar), self._visible('_rulers_button'))
            if len(steps) == 0 or steps[-1] != state:
                steps.append(state)
            hints_hidden = self.bar.shown_hint_count() < len(self.bar.hint_pairs)
            self.assertEqual(self._visible('_hint_button'), hints_hidden)
            self.assertEqual(self._visible('_more_button'), not self._visible('_rulers_button'))
            self.assertLessEqual(self.bar.minimumSizeHint().width(), width)
        self.assertEqual(steps, [(5, True, True), (4, True, True), (3, True, True), (2, True, True),
                                 (1, True, True), (0, True, True), (0, False, True), (0, False, False)])

    def test_minimum_width_is_the_smallest_plan(self) -> None:
        """The bar's minimum width doesn't depend on what it shows, so it never widens the window."""
        minimum = self.bar.minimumSizeHint()
        self._resize_bar(minimum.width())
        self.assertEqual(self.bar.minimumSizeHint(), minimum)
        self._resize_bar(WIDE)
        self.assertEqual(self.bar.minimumSizeHint(), minimum)

    def test_hidden_hints_leave_no_hint_controls(self) -> None:
        """With control hints turned off, neither pairs nor "?" show, and the right-click action turns them on."""
        AppConfig().set(AppConfig.SHOW_TOOL_CONTROL_HINTS, False)
        self.assertEqual(self.bar.shown_hint_count(), 0)
        self.assertFalse(self._visible('_hint_button'))
        actions = self.bar.actions()
        self.assertEqual(len(actions), 1)
        actions[0].trigger()
        self.assertTrue(AppConfig().get(AppConfig.SHOW_TOOL_CONTROL_HINTS))
        self.assertEqual(self.bar.shown_hint_count(), 5)

    def test_reset_view_enabled_only_away_from_default(self) -> None:
        """Reset view is disabled at the default view, enabled after a pan or a zoom, and restores the default."""
        for button in self.bar.reset_buttons:
            self.assertFalse(button.isEnabled())
        self.viewer.offset = QPointF(30.0, 0.0)
        for button in self.bar.reset_buttons:
            self.assertTrue(button.isEnabled())
        self.bar.reset_buttons[0].click()
        self.assertTrue(self.viewer.is_at_default_view)
        for button in self.bar.reset_buttons:
            self.assertFalse(button.isEnabled())
        self.viewer.scene_scale = self.viewer.scene_scale * 2
        for button in self.bar.reset_buttons:
            self.assertTrue(button.isEnabled())

    def test_zoom_field_shows_percent_and_sets_scale(self) -> None:
        """The zoom field shows the view scale as a percentage, and setting it zooms the view."""
        self.viewer.scene_scale = 1.5
        self.assertEqual(self.bar.zoom_field.value_text(), '150%')
        self.bar.zoom_field.set_value(2.0)
        self.assertAlmostEqual(self.viewer.scene_scale, 2.0)

    def test_zoom_buttons_step_like_page_keys(self) -> None:
        """The + and - buttons zoom by the same steps as the zoom in and zoom out keys."""
        self.viewer.scene_scale = 1.5
        self.viewer.zoom_in()
        expected_in = self.viewer.scene_scale
        self.viewer.scene_scale = 1.5
        self.bar._zoom_in_button.click()  # pylint: disable=protected-access
        self.assertAlmostEqual(self.viewer.scene_scale, expected_in)
        self.viewer.zoom_out()
        expected_out = self.viewer.scene_scale
        self.viewer.scene_scale = expected_in
        self.bar._zoom_out_button.click()  # pylint: disable=protected-access
        self.assertAlmostEqual(self.viewer.scene_scale, expected_out)

    def test_rulers_toggle_follows_config(self) -> None:
        """The Rulers toggle is checked while rulers show, and toggling it shows or hides them."""
        rulers = self.bar._rulers_button  # pylint: disable=protected-access
        assert rulers is not None
        self.assertEqual(rulers.isChecked(), AppConfig().get(AppConfig.SHOW_RULERS))
        rulers.setChecked(False)
        self.assertFalse(AppConfig().get(AppConfig.SHOW_RULERS))
        AppConfig().set(AppConfig.SHOW_RULERS, True)
        self.assertTrue(rulers.isChecked())
        self.assertEqual(len(rulers.actions()), 1)

    def test_navigation_button_requests_window(self) -> None:
        """The navigation button, in the bar or in "...", asks the panel's owner for the navigation window."""
        requests: list[bool] = []
        self.panel.navigation_window_requested.connect(lambda: requests.append(True))
        self.bar._navigation_button.click()  # pylint: disable=protected-access
        content = self.bar.more_popover_content()
        buttons = [button for button in content.findChildren(QPushButton) if not isinstance(button, QCheckBox)]
        self.assertEqual(len(buttons), 1)
        buttons[0].click()
        self.assertEqual(len(requests), 2)
        content.deleteLater()

    def test_more_popover_toggles_options(self) -> None:
        """The "..." popover's check boxes set rulers, ruler highlights and control hints."""
        content = self.bar.more_popover_content()
        check_boxes = content.findChildren(QCheckBox)
        keys = (AppConfig.SHOW_RULERS, AppConfig.SHOW_RULER_HIGHLIGHTS, AppConfig.SHOW_TOOL_CONTROL_HINTS)
        self.assertEqual(len(check_boxes), len(keys))
        for check_box, key in zip(check_boxes, keys):
            self.assertEqual(check_box.isChecked(), AppConfig().get(key))
            check_box.setChecked(not check_box.isChecked())
            self.assertEqual(check_box.isChecked(), AppConfig().get(key))
        content.deleteLater()

    def test_hint_popover_lists_every_pair(self) -> None:
        """"?" opens a popover listing every hint pair."""
        self._resize_bar(self.bar.minimumSizeHint().width())
        self.bar._hint_button.click()  # pylint: disable=protected-access
        popover = self.bar._popover  # pylint: disable=protected-access
        assert popover is not None and popover.content is not None
        try:
            texts = [label.text() for label in popover.content.findChildren(QLabel)]
            self.assertEqual(texts, split_hint_pairs(HINT_TEXT))
        finally:
            popover.hide()


class PlainCanvasBarTest(IntraPaintTestCase):
    """Tests a bar without rulers or the navigation button, as in the navigation window."""

    def test_no_toggles_and_no_more_button(self) -> None:
        """Without Rulers or the navigation button, the bar never shows "...", and its popover holds only the hints
        toggle."""
        image_stack = ImageStack(IMAGE_SIZE, QSize(256, 256), QSize(8, 8), QSize(2048, 2048))
        panel = ImagePanel(image_stack)
        panel.show()
        try:
            bar = panel.control_bar
            assert bar is not None
            panel.resize(QSize(bar.minimumSizeHint().width() + 30, PANEL_HEIGHT))
            self.assertFalse(bar._more_button.isVisibleTo(bar))  # pylint: disable=protected-access
            content = bar.more_popover_content()
            self.assertEqual(len(content.findChildren(QCheckBox)), 1)
            content.deleteLater()
        finally:
            panel.close()
            panel.deleteLater()
