"""Tests that animated outlines and preview lines animate only while shown in a scene with something to draw."""
import sys

from PySide6.QtCore import QLineF, QPointF, QRectF
from PySide6.QtGui import QPolygonF
from PySide6.QtWidgets import QApplication, QGraphicsRectItem, QGraphicsScene, QGraphicsView

from src.config.application_config import AppConfig
from src.ui.graphics_items.outline import Outline
from src.ui.graphics_items.path_creation_item import PathCreationItem
from src.ui.graphics_items.polygon_outline import PolygonOutline
from src.ui.graphics_items.temp_dashed_line_item import TempDashedLineItem
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

LINE = QLineF(QPointF(10, 10), QPointF(50, 30))
REGION = QRectF(0, 0, 40, 30)
POLYGON = QPolygonF([QPointF(0, 0), QPointF(40, 0), QPointF(20, 30)])


class DashAnimationTest(IntraPaintTestCase):
    """Each animated item runs its animation only while it is visible, in a scene, and has dashes to draw."""

    def setUp(self) -> None:
        super().setUp()
        AppConfig().set(AppConfig.ANIMATE_OUTLINES_AND_PREVIEWS, True)
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)

    def test_preview_line_animates_only_while_shown_with_a_line(self) -> None:
        line_item = TempDashedLineItem(self.scene)
        timer = line_item._animation_timer
        self.assertFalse(timer.isActive(), 'an empty preview line has nothing to animate')
        line_item.set_line(LINE)
        self.assertTrue(timer.isActive())
        line_item.setVisible(False)
        self.assertFalse(timer.isActive())
        line_item.show()
        self.assertTrue(timer.isActive())
        line_item.set_line(QLineF())
        self.assertFalse(timer.isActive())
        line_item.set_line(LINE)
        self.scene.removeItem(line_item)
        self.assertFalse(timer.isActive())

    def test_path_animates_only_with_a_segment(self) -> None:
        path_item = PathCreationItem(self.scene)
        timer = path_item._animation_timer
        path_item.add_point(QPointF(0, 0))
        self.assertFalse(timer.isActive(), 'a single point has no line to animate')
        path_item.add_point(QPointF(20, 20))
        self.assertTrue(timer.isActive())
        path_item.hide()
        self.assertFalse(timer.isActive())
        path_item.show()
        path_item.clear_points()
        self.assertFalse(timer.isActive())

    def test_outline_animates_only_while_shown_around_a_region(self) -> None:
        parent = QGraphicsRectItem()
        self.scene.addItem(parent)
        outline = Outline(self.scene, self.view, parent)
        outline.animated = True
        timer = outline._animation_timer
        self.assertFalse(timer.isActive(), 'an outline around nothing has nothing to animate')
        outline.outlined_region = REGION
        self.assertTrue(timer.isActive())
        outline.hide()
        self.assertFalse(timer.isActive())
        outline.show()
        self.assertTrue(timer.isActive())
        parent.hide()
        self.assertFalse(timer.isActive(), 'hiding the parent hides the outline')
        parent.show()
        self.assertTrue(timer.isActive())

    def test_polygon_outline_animates_only_while_shown(self) -> None:
        outline = PolygonOutline(self.view, [POLYGON])
        animation = outline._animator.animation
        self.assertTrue(animation.state() == animation.State.Running)
        outline.hide()
        self.assertTrue(animation.state() == animation.State.Stopped)
        outline.show()
        self.assertTrue(animation.state() == animation.State.Running)
        self.scene.removeItem(outline)
        self.assertTrue(animation.state() == animation.State.Stopped)
