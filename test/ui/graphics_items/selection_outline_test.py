"""Tests that the selection outline's fill follows the selection overlay setting and its outline keeps animating."""
import sys

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPolygonF
from PySide6.QtWidgets import QApplication, QGraphicsScene, QGraphicsView

from src.config.application_config import AppConfig
from src.ui.graphics_items.selection_outline import SelectionOutline
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

POLYGON = QPolygonF([QPointF(0, 0), QPointF(40, 0), QPointF(20, 30)])
OVERLAY_COLOR = '#99FF0000'


class SelectionOutlineTest(IntraPaintTestCase):
    """The overlay setting hides only the fill, and the fill animation stops with it."""

    def setUp(self) -> None:
        super().setUp()
        config = AppConfig()
        config.set(AppConfig.SELECTION_COLOR, OVERLAY_COLOR)
        config.set(AppConfig.SHOW_SELECTION_OVERLAY, True)
        config.set(AppConfig.ANIMATE_SELECTION_FILL, True)
        config.set(AppConfig.ANIMATE_SELECTION_OUTLINE, True)
        self._outlines: list[SelectionOutline] = []
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.outline = self._make_outline()

    def tearDown(self) -> None:
        # The outline isn't a QObject, so the config keeps its connections until they are removed:
        for outline in self._outlines:
            AppConfig().disconnect_all(outline)
            self.scene.removeItem(outline)
        self._outlines.clear()
        super().tearDown()

    def _make_outline(self) -> SelectionOutline:
        outline = SelectionOutline(self.view, [POLYGON])
        self._outlines.append(outline)
        return outline

    def _animating(self) -> bool:
        animation = self.outline._animator.animation  # pylint: disable=protected-access
        return animation.state() == animation.State.Running

    def test_overlay_shows_by_default(self) -> None:
        """The fill takes the selection color and animates."""
        self.assertEqual(self.outline.fill_color, QColor(OVERLAY_COLOR))
        self.assertTrue(self.outline.animated_fill)

    def test_hiding_overlay_keeps_animated_outline(self) -> None:
        """Hiding the overlay clears the fill but leaves the outline animating, and showing it restores the fill."""
        AppConfig().set(AppConfig.SHOW_SELECTION_OVERLAY, False)
        self.assertEqual(self.outline.fill_color.alpha(), 0)
        self.assertFalse(self.outline.animated_fill)
        self.assertTrue(self.outline.animated_outline)
        self.assertTrue(self._animating())
        AppConfig().set(AppConfig.SHOW_SELECTION_OVERLAY, True)
        self.assertEqual(self.outline.fill_color, QColor(OVERLAY_COLOR))
        self.assertTrue(self.outline.animated_fill)

    def test_hidden_overlay_with_static_outline_stops_animating(self) -> None:
        """With outline animation off, a hidden fill leaves nothing to animate."""
        AppConfig().set(AppConfig.ANIMATE_SELECTION_OUTLINE, False)
        self.assertTrue(self._animating(), 'the animated fill still runs')
        AppConfig().set(AppConfig.SHOW_SELECTION_OVERLAY, False)
        self.assertFalse(self._animating())
        AppConfig().set(AppConfig.SHOW_SELECTION_OVERLAY, True)
        self.assertTrue(self._animating())

    def test_color_change_keeps_overlay_hidden(self) -> None:
        """Changing the selection color while the overlay is hidden doesn't bring the fill back."""
        AppConfig().set(AppConfig.SHOW_SELECTION_OVERLAY, False)
        AppConfig().set(AppConfig.SELECTION_COLOR, '#9900FF00')
        self.assertEqual(self.outline.fill_color.alpha(), 0)
        AppConfig().set(AppConfig.SHOW_SELECTION_OVERLAY, True)
        self.assertEqual(self.outline.fill_color, QColor('#9900FF00'))

    def test_per_item_overlay_flag_hides_fill(self) -> None:
        """An outline with `show_overlay` off stays unfilled whatever the setting says."""
        self.outline.show_overlay = False
        self.assertEqual(self.outline.fill_color.alpha(), 0)
        AppConfig().set(AppConfig.SHOW_SELECTION_OVERLAY, False)
        AppConfig().set(AppConfig.SHOW_SELECTION_OVERLAY, True)
        self.assertEqual(self.outline.fill_color.alpha(), 0)
        self.outline.show_overlay = True
        self.assertEqual(self.outline.fill_color, QColor(OVERLAY_COLOR))

    def test_new_outline_honors_hidden_overlay(self) -> None:
        """An outline created while the overlay is hidden starts without a fill."""
        AppConfig().set(AppConfig.SHOW_SELECTION_OVERLAY, False)
        outline = self._make_outline()
        self.assertEqual(outline.fill_color.alpha(), 0)
        self.assertFalse(outline.animated_fill)
