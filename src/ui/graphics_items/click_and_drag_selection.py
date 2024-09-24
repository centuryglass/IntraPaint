"""An object that creates a temporary graphics item used to visualize clicking and dragging to select a region."""
from typing import Optional

from PySide6.QtCore import QRect, QPoint, QPointF, QLineF, QObject, QSizeF
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPen, QBrush, QColor, QTransform, QPolygonF, QPainterPath, QPainter
from PySide6.QtWidgets import QGraphicsScene, QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from src.config.key_config import KeyConfig
from src.util.math_utils import clamp
from src.util.visual.geometry_utils import closest_point_keeping_aspect_ratio
from src.util.visual.shape_mode import ShapeMode

DEFAULT_SELECTION_LINE_COLOR = Qt.GlobalColor.black
DEFAULT_SELECTION_LINE_WIDTH = 2.0
DEFAULT_SELECTION_FILL_COLOR = QColor(100, 100, 100)


class _ShapeItem(QGraphicsItem):

    def __init__(self) -> None:
        super().__init__()
        self._mode = ShapeMode.RECTANGLE
        self._pen = QPen()
        self._brush = QBrush()
        self._vertex_count = 3
        self._inner_radius_fraction = 0.5
        self._start_point = QPointF()
        self._end_point = QPointF()

    def is_empty(self) -> bool:
        """Returns whether the shape currently has zero size and is not drawn in the scene."""
        return self._start_point == self._end_point

    def clear(self) -> None:
        """Resets the shape size to zero."""
        if not self.is_empty():
            self.prepareGeometryChange()
            self._start_point = QPointF()
            self._end_point = QPointF()
            self.update()

    def point_rect(self) -> QRectF:
        """Returns the rectangle defined by the start and end points."""
        return QRectF(self._start_point, self._end_point)

    def set_mode(self, mode: ShapeMode) -> None:
        """Update the type of shape being drawn."""
        if self._mode != mode:
            self._mode = mode
            if not self.is_empty():
                self.prepareGeometryChange()
                self.update()

    def set_start_point(self, start_point: QPointF) -> None:
        """Update the shape's start point."""
        if self._start_point != start_point:
            self._start_point = QPointF(start_point)
            self.prepareGeometryChange()
            self.update()

    def set_end_point(self, end_point: QPointF) -> None:
        """Update the shape's end point."""
        if self._end_point != end_point:
            self._end_point = QPointF(end_point)
            self.prepareGeometryChange()
            self.update()

    def set_pen(self, pen: QPen) -> None:
        """Update the pen used to draw the shape's outline."""
        if self._pen != pen:
            if self._pen.width() != pen.width():
                self.prepareGeometryChange()
            self._pen = QPen(pen)
            if not self.is_empty():
                self.update()

    def set_brush(self, brush: QBrush):
        """Update the brush used to fill the shape."""
        if self._brush != brush:
            self._brush = QBrush(brush)
            if not self.is_empty():
                self.update()

    def set_vertex_count(self, vertex_count: int):
        """Update the vertex count when drawing in polygon or star mode."""
        if self._vertex_count != vertex_count:
            self._vertex_count = vertex_count
            if self._mode in (ShapeMode.POLYGON, ShapeMode.STAR) and not self.is_empty():
                self.prepareGeometryChange()
                self.update()

    def set_inner_radius_fraction(self, inner_radius_fraction: float) -> None:
        """Update the inner radius fraction when drawing in star mode."""
        if self._inner_radius_fraction != inner_radius_fraction:
            self._inner_radius_fraction = inner_radius_fraction
            if self._mode == ShapeMode.STAR and not self.is_empty():
                self.update()

    def boundingRect(self) -> QRectF:
        """Returns the rectangle within the scene containing all pixels drawn by the outline."""
        if self.is_empty():
            return QRectF(self._start_point, QSizeF(0.0, 0.0))
        line_width = self._pen.width() / 2
        return self.painter_path().boundingRect().adjusted(-line_width, -line_width, line_width, line_width)

    def painter_path(self) -> QPainterPath:
        """Returns the outline's bounds as a shape."""
        rect = QRectF(self._start_point, self._end_point)
        if self._mode == ShapeMode.ELLIPSE:
            path = QPainterPath()
            path.addEllipse(rect.center(), rect.width() / 2, rect.height() / 2)
        elif self._mode == ShapeMode.RECTANGLE:
            path = QPainterPath()
            path.addRect(rect)
        else:
            assert self._mode in (ShapeMode.POLYGON, ShapeMode.STAR), f'Invalid mode {self._mode}'
            line = QLineF(rect.center(), self._start_point)
            initial_angle = line.angle()
            radius = line.length()
            inner_radius = radius * self._inner_radius_fraction
            path = self._mode.painter_path(rect.toAlignedRect(), radius, self._vertex_count, inner_radius,
                                           initial_angle)
        return path

    def shape(self) -> QPainterPath:
        """Returns the outline's bounds as a shape."""
        return self.painter_path()

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draws the shape using the provided pen and brush."""
        if painter is None or self.is_empty():
            return
        painter.save()
        path = self.painter_path()
        painter.fillPath(path, self._brush)
        painter.setPen(self._pen)
        painter.drawPath(path)
        painter.restore()


class ClickAndDragSelection(QObject):
    """An object that creates a temporary graphics item used to visualize clicking and dragging to select a region."""

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__()
        self._scene = scene
        self._selection_shape = _ShapeItem()
        self._scene.addItem(self._selection_shape)
        self._mode = ShapeMode.RECTANGLE
        self._pen: QPen = QPen(DEFAULT_SELECTION_LINE_COLOR, DEFAULT_SELECTION_LINE_WIDTH)
        self._brush: QBrush = QBrush(DEFAULT_SELECTION_FILL_COLOR, Qt.BrushStyle.Dense5Pattern)
        self._last_bounds: Optional[QRect] = None
        self._transform = QTransform()
        self._aspect_ratio: Optional[float] = None
        self._inner_radius_fraction = 0.5
        self._vertex_count = 5
        self._selecting = False

    @property
    def last_selection_bounds(self) -> Optional[QRect]:
        """Return the bounds from the last selection, or None if no selection has happened yet."""
        return QRect(self._last_bounds) if self._last_bounds is not None else None

    @property
    def mode(self) -> ShapeMode:
        """Return the active selection mode."""
        return self._mode

    @mode.setter
    def mode(self, new_mode: ShapeMode) -> None:
        if new_mode == self._mode:
            return
        self._mode = new_mode
        self._selection_shape.set_mode(new_mode)

    @property
    def vertex_count(self) -> int:
        """Accesses the vertex count used when the mode is POLYGON or STAR."""
        return self._vertex_count

    @vertex_count.setter
    def vertex_count(self, count: int) -> None:
        count = max(count, 3)
        if self._vertex_count == count:
            return
        self._vertex_count = count
        self._selection_shape.set_vertex_count(count)

    @property
    def inner_radius_fraction(self) -> float:
        """Accesses the inner point radius used when the mode is STAR."""
        return self._inner_radius_fraction

    @inner_radius_fraction.setter
    def inner_radius_fraction(self, radius: float) -> None:
        radius = float(clamp(radius, 0.01, 1.0))
        if self._inner_radius_fraction == radius:
            return
        self._inner_radius_fraction = radius
        self._selection_shape.set_inner_radius_fraction(radius)

    def set_aspect_ratio(self, aspect_ratio: Optional[float]) -> None:
        """Set or clear a fixed aspect ratio for selection."""
        self._aspect_ratio = aspect_ratio

    @property
    def selecting(self) -> bool:
        """Return whether a selection is currently in-progress."""
        return self._selecting

    @property
    def transform(self) -> QTransform:
        """Access the transformation applied to the selection graphics item."""
        return QTransform(self._transform)

    @transform.setter
    def transform(self, transform: QTransform) -> None:
        """Sets the transformation applied to the selection."""
        if transform == self._transform:
            return
        assert transform.isInvertible()
        self._transform = QTransform(transform)
        self._selection_shape.setTransform(self._transform)

    def start_selection(self, start_point: QPoint) -> None:
        """Start a new selection.

        Parameters:
        -----------
        start_point: QPoint
            The initial selection point, as an untransformed scene coordinate.
        """
        start_point = self._transform.inverted()[0].map(start_point)
        self._selection_shape.clear()
        self._selection_shape.set_start_point(QPointF(start_point))
        self._selection_shape.set_end_point(QPointF(start_point))
        self._selecting = True

    def drag_to(self, drag_point: QPoint) -> None:
        """Continue a selection.

        Parameters:
        -----------
        drag_point: QPoint
            The point where the mouse is currently placed, as an untransformed scene coordinate.
        """
        drag_point = self._transform.inverted()[0].map(drag_point)
        if not self.selecting:
            self.start_selection(drag_point)
            return
        assert self._selection_shape is not None
        rect = self._selection_shape.point_rect()
        if self._aspect_ratio is not None:
            bottom_right = closest_point_keeping_aspect_ratio(QPointF(drag_point), rect.topLeft(),
                                                              self._aspect_ratio).toPoint()
        elif KeyConfig.modifier_held(KeyConfig.FIXED_ASPECT_MODIFIER):
            bottom_right = closest_point_keeping_aspect_ratio(QPointF(drag_point), rect.topLeft(),
                                                              1.0).toPoint()
        else:
            bottom_right = drag_point
        self._selection_shape.set_end_point(QPointF(bottom_right))

    def end_selection(self, end_point: QPoint) -> QPolygonF:
        """Finish a selection, and return the selected rectangle in the scene.
        Parameters:
        -----------
        end_point: QPoint
            The point where the selection finished, as an untransformed scene coordinate.
        Returns:
        -------
        QPolygonF
            The final selected rectangle or ellipse, transformed back into scene coordinates.
        """
        assert self._selection_shape is not None
        self.drag_to(end_point)
        shape = QPolygonF(self._selection_shape.painter_path().toFillPolygon(self._transform))
        self._last_bounds = shape.boundingRect().toAlignedRect()
        self._selection_shape.clear()
        self._selecting = False
        return shape

    def set_pen(self, pen: QPen) -> None:
        """Set the selection item's line drawing pen."""
        self._pen = QPen(pen)
        self._selection_shape.set_pen(self._pen)

    def set_brush(self, brush: QBrush) -> None:
        """set the selection item's fill brush."""
        self._brush = QBrush(brush)
        self._selection_shape.set_brush(self._brush)
