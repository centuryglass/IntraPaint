"""Outlines a region in a variable QGraphicsView, adjusting line width based on view scale."""
import sys
from typing import Optional

from PySide6.QtCore import Qt, QPropertyAnimation, QRectF, QRect, Property
from PySide6.QtGui import QPainter, QPen, QPainterPath, QColor, QShowEvent, QHideEvent
from PySide6.QtWidgets import QWidget, QGraphicsItem, QGraphicsView, QGraphicsScene, QStyleOptionGraphicsItem, \
    QGraphicsObject

from src.util.shared_constants import TIMELAPSE_MODE_FLAG


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

    def __init__(self,
                 scene: QGraphicsScene,
                 view: QGraphicsView,
                 parent: Optional[QGraphicsItem] = None):
        super().__init__(parent)
        self._rect = QRectF()
        self._view = view
        self._animated = False
        self._dash_pattern = [2, 2, 4, 2, 2, 2]
        self._dash_offset = 0
        self._anim = QPropertyAnimation(self, b"dash_offset")
        self._anim.setLoopCount(-1)
        self._anim.setStartValue(0)
        self._anim.setEndValue(140)
        self._anim.setDuration(1000)
        scene.addItem(self)

    def dash_offset_getter(self) -> int:
        """Animate dash offset to make the image generation area more visible."""
        return self._dash_offset

    def dash_offset_setter(self, offset: int) -> None:
        """Update the animated dash offset."""
        self._dash_offset = offset

    dash_offset = Property(int, dash_offset_getter, dash_offset_setter)

    @property
    def dash_pattern(self) -> list[int]:
        """Returns the dash pattern used by the outline."""
        return self._dash_pattern

    @dash_pattern.setter
    def dash_pattern(self, dash_pattern: list[int]) -> None:
        """Updates the dash pattern used by the outline."""
        self._dash_pattern = dash_pattern
        pattern_length = 0
        for length in dash_pattern:
            pattern_length += length
        self._anim.setEndValue(pattern_length * 10)

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
        if self._animated and self.isVisible():
            self._anim.start()
        else:
            self._anim.stop()

    def showEvent(self, _: Optional[QShowEvent]) -> None:
        """Starts the animation when the outline is shown."""
        if self._animated:
            self._anim.start()

    def hideEvent(self, _: Optional[QHideEvent]) -> None:
        """Stops the animation when the outline is hidden."""
        self._anim.stop()

    def get_outline_width(self) -> float:
        """Gets the outline width based on the current scale of the scene within its QGraphicsView."""
        if self.scene() is None or self._view is None or self._rect.isEmpty():
            return 0.0
        view_scale = self._view.transform().m11()
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

        black_line_pen = QPen(outline_black, line_width / 4, Qt.PenStyle.SolidLine)
        white_line_pen = QPen(outline_white, line_width)
        dotted_line_pen = QPen(Qt.GlobalColor.black, line_width / 4, Qt.PenStyle.DotLine)
        dotted_line_pen.setDashPattern(self.dash_pattern)
        dotted_line_pen.setDashOffset(self._dash_offset / 10)

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

    def boundingRect(self) -> QRectF:
        """Returns the rectangle within the scene containing all pixels drawn by the outline."""
        line_width = self.get_outline_width()
        return self._rect.adjusted(-line_width, -line_width, line_width, line_width)

    def shape(self) -> QPainterPath:
        """Returns the outline's bounds as a shape."""
        path = QPainterPath()
        path.addRect(QRectF(self.boundingRect()))
        return path
