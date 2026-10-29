"""Outlines a region in a variable QGraphicsView, adjusting line width based on view scale."""
import sys
from typing import Any, Optional
from weakref import ref

from PySide6.QtCore import Qt, QRectF, QRect, QTimer
from PySide6.QtGui import QPainter, QPen, QPainterPath, QColor
from PySide6.QtWidgets import QWidget, QGraphicsItem, QGraphicsView, QGraphicsScene, QStyleOptionGraphicsItem, \
    QGraphicsObject

from src.ui.graphics_items.animated_dash_item import is_shown_in_scene, sync_animation_timer
from src.util.shared_constants import TIMELAPSE_MODE_FLAG

# ~15 frames per second, a few dash units per step. A QPropertyAnimation would tick every frame while the outline is
# visible, repainting it at the full frame rate even when nothing else changed.
DASH_ANIMATION_INTERVAL_MS = 66
DASH_ANIMATION_STEP = 5


class Outline(QGraphicsObject):
    """Outlines a region in a variable QGraphicsView, adjusting line width based on view scale.

    The outline will have the following properties:

    - When set to a scene rectangle, it will resize to draw its borders exactly around that rectangle, with zero
      overlap.
    - Line width will be set to either 1px in scene coordinates or 4px in view coordinates, whichever is larger.
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
        """Gets the outline width based on the current scale of the scene within its QGraphicsView."""
        if self.scene() is None or self._view is None or self._rect.isEmpty():
            return 0.0
        view_scale = self._view.transform().m11()
        if self._cosmetic:
            return 6.0 / view_scale
        return max(1.0, 6.0 / view_scale)

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draws the outline within the scene."""
        if painter is None:
            return
        line_width = self.get_outline_width()

        outline_white = QColor(Qt.GlobalColor.white)
        outline_white.setAlphaF(0.7)
        outline_black = QColor(Qt.GlobalColor.black)
        outline_black.setAlphaF(0.7)

        inner_border = self._rect.adjusted(-line_width / 4, -line_width / 4, line_width / 4, line_width / 4)
        mid_border = inner_border.adjusted(-line_width / 3, -line_width / 3, line_width / 3, line_width / 3)
        outer_border = mid_border.adjusted(-line_width / 4, -line_width / 4, line_width / 4, line_width / 4)

        black_line_pen = QPen(outline_black, line_width / 4 if not self._cosmetic else 1, Qt.PenStyle.SolidLine)
        white_line_pen = QPen(outline_white, line_width if not self._cosmetic else 4)
        dotted_line_pen = QPen(Qt.GlobalColor.black, line_width / 4 if not self._cosmetic else 1, Qt.PenStyle.DotLine)
        dotted_line_pen.setDashPattern(self.dash_pattern)
        dotted_line_pen.setDashOffset(self._dash_offset / 10)
        if self._cosmetic:
            black_line_pen.setCosmetic(True)
            white_line_pen.setCosmetic(True)
            dotted_line_pen.setCosmetic(True)

        painter.setPen(white_line_pen)
        painter.drawRect(mid_border)
        painter.setPen(dotted_line_pen)
        painter.drawRect(inner_border)
        painter.setPen(black_line_pen)
        painter.drawRect(outer_border)

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
        """Returns the rectangle within the scene containing all pixels drawn by the outline."""
        line_width = self.get_outline_width()
        return self._rect.adjusted(-line_width, -line_width, line_width, line_width)

    def shape(self) -> QPainterPath:
        """Returns the outline's bounds as a shape."""
        path = QPainterPath()
        path.addRect(QRectF(self.boundingRect()))
        return path
