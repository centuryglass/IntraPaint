"""Outlines a region in a variable QGraphicsView, adjusting line width based on view scale."""
import math
import sys
from typing import Any, Optional
from weakref import ref

from PySide6.QtCore import Qt, QRectF, QRect, QTimer, QPointF
from PySide6.QtGui import QPainter, QPen, QPainterPath, QColor, QPolygonF, QTransform
from PySide6.QtWidgets import QWidget, QGraphicsItem, QGraphicsView, QGraphicsScene, QStyleOptionGraphicsItem, \
    QGraphicsObject

from src.ui.graphics_items.animated_dash_item import is_shown_in_scene, sync_animation_timer
from src.util.shared_constants import TIMELAPSE_MODE_FLAG

# ~15 frames per second, a few dash units per step. A QPropertyAnimation would tick every frame while the outline is
# visible, repainting it at the full frame rate even when nothing else changed.
DASH_ANIMATION_INTERVAL_MS = 66
DASH_ANIMATION_STEP = 5


def _offset_quad(corners: QPolygonF, offset: float) -> QPolygonF:
    """Returns a convex polygon with each edge moved outward by an offset, keeping its corners mitered."""
    count = corners.size()
    if count < 3:
        return QPolygonF(corners)
    center = QPointF(sum(pt.x() for pt in corners) / count, sum(pt.y() for pt in corners) / count)

    def _outward_normal(start: QPointF, end: QPointF) -> QPointF:
        edge = end - start
        length = math.hypot(edge.x(), edge.y())
        if length == 0:
            return QPointF()
        normal = QPointF(edge.y() / length, -edge.x() / length)
        midpoint = (start + end) / 2
        if QPointF.dotProduct(normal, midpoint - center) < 0:
            normal = -normal
        return normal

    offset_corners = QPolygonF()
    for i in range(count):
        before = _outward_normal(corners[i - 1], corners[i])
        after = _outward_normal(corners[i], corners[(i + 1) % count])
        denominator = 1 + QPointF.dotProduct(before, after)
        miter = (before + after) / denominator if denominator > 1e-6 else before
        offset_corners.append(corners[i] + miter * offset)
    return offset_corners


class Outline(QGraphicsObject):
    """Outlines a region in a variable QGraphicsView, adjusting line width based on view scale.

    The outline will have the following properties:

    - When set to a rectangle in item coordinates, it will draw its borders exactly around that rectangle as the item
      transform and view map it, with zero overlap.
    - Line width is measured in view pixels, ignoring the item transform: 6px, or 1 scene pixel if that is larger and
      the outline is not cosmetic.
    - The outline will be a solid white line with 0.7 opacity.
    - Overlapping the outer and inner edges of the outline, two more rectangles will be drawn to make the outline
      borders clearer. These will each have widths of line_width / 4, and will be drawn as black dashed lines with
      100% opacity.
    - If animated, dotted lines will slowly move to increase visibility.
    """

    @property
    def _view(self) -> Optional[QGraphicsView]:
        # Held weakly, since the view holds its scene's items:
        view = self._view_ref()
        return view

    def __init__(self,
                 scene: QGraphicsScene,
                 view: QGraphicsView,
                 parent: Optional[QGraphicsItem] = None,
                 cosmetic_line_draw: bool = False):
        super().__init__(parent)
        self._rect = QRectF()
        self._view_ref = ref(view)
        self._animated = False
        self._dash_pattern = [2, 2, 4, 2, 2, 2]
        self._dash_loop = sum(self._dash_pattern) * 10
        self._dash_offset = 0
        self._cosmetic = cosmetic_line_draw
        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(DASH_ANIMATION_INTERVAL_MS)
        self._animation_timer.timeout.connect(self._advance_dash_offset)
        scene.addItem(self)

    def _advance_dash_offset(self) -> None:
        """Moves the dashed border one step, repainting only the outline's own bounds."""
        self._dash_offset = (self._dash_offset + DASH_ANIMATION_STEP) % self._dash_loop
        self.update()

    @property
    def dash_pattern(self) -> list[int]:
        """Returns the dash pattern used by the outline."""
        return self._dash_pattern

    @dash_pattern.setter
    def dash_pattern(self, dash_pattern: list[int]) -> None:
        """Updates the dash pattern used by the outline."""
        self._dash_pattern = dash_pattern
        self._dash_loop = sum(dash_pattern) * 10
        self.update()

    def _update_animation_state(self) -> None:
        """Runs the animation only while animation is enabled and the outline is shown in a scene around a region."""
        sync_animation_timer(self._animation_timer, self._animated,
                             is_shown_in_scene(self) and not self._rect.isEmpty())

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:  # pylint: disable=invalid-name
        """Starts or stops the animation as the outline is shown, hidden, added to a scene or removed from one."""
        if change in (QGraphicsItem.GraphicsItemChange.ItemVisibleHasChanged,
                      QGraphicsItem.GraphicsItemChange.ItemSceneHasChanged):
            self._update_animation_state()
        return super().itemChange(change, value)

    @property
    def animated(self) -> bool:
        """Returns whether dotted lines are animated."""
        return self._animated

    @animated.setter
    def animated(self, should_animate: bool) -> None:
        """Sets whether dotted lines are animated."""
        if TIMELAPSE_MODE_FLAG in sys.argv:
            return
        self._animated = should_animate
        self._update_animation_state()

    def get_outline_width(self) -> float:
        """Returns the outline's total width in view pixels: 6, or one scene pixel if that is wider and not cosmetic.

        The width is measured on screen, so it ignores the outline's own item transform. A transformed layer's
        outline is no thicker than an untransformed one.
        """
        if self.scene() is None or self._view is None or self._rect.isEmpty():
            return 0.0
        if self._cosmetic:
            return 6.0
        return max(6.0, self._view.transform().m11())

    def _device_borders(self, device_transform: QTransform, line_width: float) -> list[QPolygonF]:
        """Returns the inner, middle and outer border polygons in device pixels, under a transform from item space."""
        corners = device_transform.map(QPolygonF(self._rect))
        if corners.size() > 4:
            corners.remove(4)  # QPolygonF(QRectF) repeats the first corner to close the polygon.
        inner_offset = line_width / 4
        mid_offset = inner_offset + line_width / 3
        outer_offset = mid_offset + line_width / 4
        return [_offset_quad(corners, offset) for offset in (inner_offset, mid_offset, outer_offset)]

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draws the outline in device pixels, so the item transform moves it without thickening its lines."""
        if painter is None:
            return
        line_width = self.get_outline_width()
        if line_width <= 0:
            return
        inner_border, mid_border, outer_border = self._device_borders(painter.worldTransform(), line_width)

        outline_white = QColor(Qt.GlobalColor.white)
        outline_white.setAlphaF(0.7)
        outline_black = QColor(Qt.GlobalColor.black)
        outline_black.setAlphaF(0.7)

        thin_width = 1 if self._cosmetic else line_width / 4
        black_line_pen = QPen(outline_black, thin_width, Qt.PenStyle.SolidLine)
        white_line_pen = QPen(outline_white, 4 if self._cosmetic else line_width)
        dotted_line_pen = QPen(Qt.GlobalColor.black, thin_width, Qt.PenStyle.DotLine)
        dotted_line_pen.setDashPattern(self.dash_pattern)
        dotted_line_pen.setDashOffset(self._dash_offset / 10)
        for pen in (black_line_pen, white_line_pen, dotted_line_pen):
            pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)

        painter.save()
        painter.resetTransform()
        painter.setPen(white_line_pen)
        painter.drawPolygon(mid_border)
        painter.setPen(dotted_line_pen)
        painter.drawPolygon(inner_border)
        painter.setPen(black_line_pen)
        painter.drawPolygon(outer_border)
        painter.restore()

    @property
    def outlined_region(self) -> QRectF:
        """Returns the outlined area in the scene."""
        return self._rect

    @outlined_region.setter
    def outlined_region(self, new_region: QRect | QRectF) -> None:
        """Updates the outlined area in the scene."""
        self.prepareGeometryChange()
        self._rect = QRectF(new_region)
        self._update_animation_state()

    def boundingRect(self) -> QRectF:
        """Returns the rectangle in item coordinates containing all pixels drawn by the outline in its view."""
        line_width = self.get_outline_width()
        view = self._view
        if line_width <= 0 or view is None:
            return QRectF(self._rect)
        device_transform = self.deviceTransform(view.viewportTransform())
        item_transform, invertible = device_transform.inverted()
        if not invertible:
            return QRectF(self._rect)
        # The outer border's center line, plus the half-width of the widest pen and a pixel of antialiasing:
        drawn_bounds = _offset_quad(self._device_borders(device_transform, line_width)[1], line_width / 2 + 1)
        return item_transform.map(drawn_bounds).boundingRect()

    def shape(self) -> QPainterPath:
        """Returns the outline's bounds as a shape."""
        path = QPainterPath()
        path.addRect(QRectF(self.boundingRect()))
        return path
