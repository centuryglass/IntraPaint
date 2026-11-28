"""Tests that region outlines keep the same on-screen line width whatever their item transform."""
import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QTransform
from PySide6.QtWidgets import QApplication, QGraphicsScene, QGraphicsView

from src.ui.graphics_items.outline import Outline
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

VIEW_SIZE = 300
SCREEN_RECT = QRectF(50, 50, 200, 200)
BACKGROUND = QColor(0, 0, 255)


class OutlineTest(IntraPaintTestCase):
    """An outline is drawn at a fixed width in view pixels, so a scaled or rotated layer's outline is not thicker."""

    def setUp(self) -> None:
        super().setUp()
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, VIEW_SIZE, VIEW_SIZE)
        self.view = QGraphicsView(self.scene)
        self.view.setFixedSize(VIEW_SIZE, VIEW_SIZE)
        self.view.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.outline = Outline(self.scene, self.view)

    def _render(self) -> QImage:
        image = QImage(VIEW_SIZE, VIEW_SIZE, QImage.Format.Format_ARGB32)
        image.fill(BACKGROUND)
        painter = QPainter(image)
        self.scene.render(painter, QRectF(image.rect()), self.scene.sceneRect())
        painter.end()
        return image

    def _left_edge_columns(self, image: QImage) -> list[int]:
        """Returns the columns the outline covers on the row through the middle of its left edge."""
        row = VIEW_SIZE // 2
        return [x for x in range(VIEW_SIZE // 2) if image.pixelColor(x, row) != BACKGROUND]

    def _outline_with_transform(self, region: QRectF, transform: QTransform) -> list[int]:
        self.outline.setTransform(transform)
        self.outline.outlined_region = region
        return self._left_edge_columns(self._render())

    def test_scaled_outline_matches_unscaled_width(self) -> None:
        expected = self._outline_with_transform(SCREEN_RECT, QTransform())
        self.assertGreater(len(expected), 0, 'the untransformed outline was not drawn')
        scaled = self._outline_with_transform(QRectF(5, 5, 20, 20), QTransform.fromScale(10, 10))
        self.assertEqual(expected, scaled)

    def test_unevenly_scaled_outline_matches_unscaled_width(self) -> None:
        expected = self._outline_with_transform(SCREEN_RECT, QTransform())
        scaled = self._outline_with_transform(QRectF(25, 5, 100, 20), QTransform.fromScale(2, 10))
        self.assertEqual(expected, scaled)

    def test_bounds_cover_drawn_outline_under_scale(self) -> None:
        self.outline.setTransform(QTransform.fromScale(10, 10))
        self.outline.outlined_region = QRectF(5, 5, 20, 20)
        scene_bounds = self.outline.mapRectToScene(self.outline.boundingRect())
        columns = self._left_edge_columns(self._render())
        self.assertLessEqual(scene_bounds.left(), columns[0])
        self.assertLess(scene_bounds.left(), SCREEN_RECT.left() - 6, 'bounds too small to hold the 6px outline')
        self.assertGreater(scene_bounds.left(), SCREEN_RECT.left() - 20, 'bounds grew with the item scale')

    def test_rotated_outline_stays_outside_region(self) -> None:
        self.outline.setTransform(QTransform().translate(150, 150).rotate(30).scale(8, 4))
        self.outline.outlined_region = QRectF(-10, -10, 20, 20)
        image = self._render()
        center = image.pixelColor(150, 150)
        self.assertEqual(center, BACKGROUND, 'the outline drew inside the region it outlines')
        bounds = self.outline.mapRectToScene(self.outline.boundingRect())
        drawn = [(x, y) for y in range(VIEW_SIZE) for x in range(VIEW_SIZE) if image.pixelColor(x, y) != BACKGROUND]
        self.assertGreater(len(drawn), 0)
        self.assertTrue(all(bounds.contains(x + 0.5, y + 0.5) for x, y in drawn), 'drawn pixels fall outside bounds')
