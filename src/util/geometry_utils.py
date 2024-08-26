"""Provides a utility function for handling image or widget placement."""
import math
from typing import Tuple, Optional

from PySide6.QtCore import QRect, QSize, QRectF, QSizeF, QPoint, QPointF, QLineF, Qt
from PySide6.QtGui import QTransform, QPolygonF, QPainter, QColor

from src.util.math_utils import convert_degrees
from src.util.shared_constants import MIN_NONZERO, FLOAT_MAX


def get_scaled_placement(container_rect: QRect | QSize,
                         inner_size: QSize, margin_width: int = 0) -> QRect:
    """
    Calculate the most appropriate placement of a scaled rectangle within a container, without changing aspect ratio.
    Parameters:
    -----------
    container_rect : QRect
        Bounds of the container where the scaled rectangle will be placed. If QSize, it is assumed to be at (0, 0).
    inner_size : QSize
        S of the rectangle to be scaled and placed within the container.
    margin_width : int
        Distance in pixels of the area around the container edges that should remain empty.
    Returns:
    --------
    placement : QRect
        Size and position of the scaled rectangle within container_rect.
    """
    if isinstance(container_rect, QSize):
        container_rect = QRect(QPoint(), container_rect)
    container_size = container_rect.size() - QSize(margin_width * 2, margin_width * 2)
    scale = min(container_size.width() / max(inner_size.width(), 1),
                container_size.height() / max(inner_size.height(), 1))
    x = float(container_rect.x() + margin_width)
    y = float(container_rect.y() + margin_width)
    if (inner_size.width() * scale) < container_size.width():
        x += (container_size.width() - inner_size.width() * scale) / 2
    if (inner_size.height() * scale) < container_size.height():
        y += (container_size.height() - inner_size.height() * scale) / 2
    return QRect(int(x), int(y), int(inner_size.width() * scale), int(inner_size.height() * scale))


def get_rect_transformation(source: QRect | QRectF | QSize, destination: QRect | QRectF | QSize) -> QTransform:
    """Gets the transformation required to transform source into destination. Parameters may be either QRect or QSize,
       if QSize is used they will be treated as a rectangle of that size at the origin."""

    def _as_rect_f(param):
        if isinstance(param, (QSize, QSizeF)):
            return QRectF(0.0, 0.0, param.width(), param.height())
        return QRectF(param)

    source, destination = (_as_rect_f(param) for param in (source, destination))
    # Extract points from the original rectangle
    orig_points, trans_points = (QPolygonF([rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight()])
                                 for rect in (source, destination))
    transform = QTransform()
    assert QTransform.quadToQuad(orig_points, trans_points,
                                 transform), f'Failed transformation: {source} -> {destination}'
    return transform


def map_rect_precise(rect: QRect | QRectF, transform: QTransform) -> QRectF:
    """Returns the bounds of a rectangle after applying a transformation, converted to floating point to prevent
     rounding errors."""
    return transform.map(QPolygonF(QRectF(rect))).boundingRect()


def translate_to_point(transform: QTransform,
                       new_origin: Optional[QPointF | QPoint] = None) -> QTransform:
    """Creates an adjusted transformation by adding a final translation to ensure (0, 0) lands on a specific point."""
    if new_origin is None:
        new_origin = QPointF(0.0, 0.0)
    if isinstance(new_origin, QPoint):
        new_origin = QPointF(new_origin)
    initial_origin = transform.map(QPointF(0.0, 0.0))
    if initial_origin == new_origin:
        return QTransform(transform)
    return transform * QTransform.fromTranslate(new_origin.x() - initial_origin.x(),
                                                new_origin.y() - initial_origin.y())


def transform_str(transformation: QTransform) -> str:
    """Return a string representation of a transformation matrix for debugging."""
    return (f'\n\t[m11:{transformation.m11()}, m12:{transformation.m12()}, m13:{transformation.m13()}]'
            f'\n\t[m21:{transformation.m21()}, m22:{transformation.m22()}, m23:{transformation.m23()}]'
            f'\n\t[m31:{transformation.m31()}, m32:{transformation.m32()}, m33:{transformation.m33()}]\n')


def transforms_approx_equal(m1: QTransform, m2: QTransform, precision: int) -> bool:
    """Return whether two transformation matrices are approximately equal when rounded to a given precision."""
    return round(m1.m11(), precision) == round(m2.m11(), precision) \
        and round(m1.m12(), precision) == round(m2.m12(), precision) \
        and round(m1.m13(), precision) == round(m2.m13(), precision) \
        and round(m1.m21(), precision) == round(m2.m21(), precision) \
        and round(m1.m22(), precision) == round(m2.m22(), precision) \
        and round(m1.m23(), precision) == round(m2.m23(), precision) \
        and round(m1.m31(), precision) == round(m2.m31(), precision) \
        and round(m1.m32(), precision) == round(m2.m32(), precision) \
        and round(m1.m33(), precision) == round(m2.m33(), precision)


def rotation_angle(transformation: QTransform) -> float:
    """Returns the rotation component of a transformation, in degrees."""
    rotation_pt = transformation.map(QPointF(1.0, 1.0)) - transformation.map(QPointF(0.0, 0.0))
    return (math.degrees(math.atan2(rotation_pt.y(), rotation_pt.x())) - 45) % 360


def translation_point(transformation: QTransform) -> QPointF:
    """Returns the translation component of a transformation as a point."""
    return QPointF(transformation.m31(), transformation.m32())


def transform_scale(transformation: QTransform) -> Tuple[float, float]:
    """Returns the scaling component of a transformation."""
    width_init = 1.0
    height_init = 1.0
    top_left = transformation.map(QPointF(0.0, 0.0))
    top_right = transformation.map(QPointF(1.0, 0.0))
    bottom_left = transformation.map(QPointF(0.0, 1.0))
    width_final = math.copysign(QLineF(top_left, top_right).length(), transformation.m11())
    height_final = math.copysign(QLineF(top_left, bottom_left).length(), transformation.m22())
    scale_x = width_final / width_init
    scale_y = height_final / height_init
    angle = rotation_angle(transformation)
    if 90 <= angle <= 270:
        scale_x *= -1
        scale_y *= -1
    return scale_x, scale_y


def extract_transform_parameters(transform: QTransform,
                                 origin: Optional[QPointF] = None) -> Tuple[float, float, float, float, float]:
    """Break a matrix down into a scale, rotation, and translation at an arbitrary origin, returning
     x_offset, y_offset, x_scale, y_scale, rotation_degrees"""
    # Not all transformations can be decomposed this way, throw an error if this one can't be:
    assert transform.isInvertible(), f'Non-invertible transform {transform_str(transform)}'
    assert transform.m13() == 0.0
    assert transform.m23() == 0.0
    assert transform.m33() == 1.0

    if origin is None:
        origin = QPointF()

    # Calculate offset:
    transform_at_origin = QTransform.fromTranslate(origin.x(), origin.y()) * transform \
                          * QTransform.fromTranslate(-origin.x(), -origin.y())
    x_offset = transform_at_origin.dx()
    y_offset = transform_at_origin.dy()

    # Calculate approximate angles (negated because the Qt y-axis points down):
    angle_line = QLineF(transform.map(origin), transform.map(QPointF(origin.x() + 1.0, origin.y())))
    angle_degrees = convert_degrees(-angle_line.angle())

    # Calculate scale:
    scaling_transform_at_origin = QTransform.fromTranslate(origin.x(), origin.y()) \
                                  * transform * QTransform.fromTranslate(-origin.x() - x_offset, -origin.y() - y_offset) \
                                  * QTransform().rotate(-angle_degrees)
    x_scale = scaling_transform_at_origin.m11()
    y_scale = scaling_transform_at_origin.m22()

    # x_scale, y_scale, rotation equals -x_scale, -y_scale, rotation+180deg, so standardize as follows:
    # - x_scale and Y_scale will never both be negative.
    # - If one of the two values must be negative, choose the option that results in a rotation that's less than 180
    #   degrees.
    if (x_scale < 0 and y_scale < 0) or ((x_scale < 0 or y_scale < 0) and angle_degrees >= 180.0):
        x_scale *= -1
        y_scale *= -1
        angle_degrees = convert_degrees(angle_degrees - 180.0)
    return x_offset, y_offset, x_scale, y_scale, angle_degrees


def combine_transform_parameters(x_offset: float, y_offset: float, x_scale: float, y_scale: float,
                                 degrees: float, origin: Optional[QPointF] = None) -> QTransform:
    """Combine a scale, rotation, and translation about an arbitrary origin into a single transformation"""
    if origin is None:
        origin = QPointF()
    assert x_scale != 0.0 and y_scale != 0.0, 'Non-invertible transformation parameters used'
    matrix = QTransform.fromTranslate(-origin.x(), -origin.y())
    matrix *= QTransform.fromScale(x_scale, y_scale)
    matrix *= QTransform().rotate(degrees)
    matrix *= QTransform.fromTranslate(x_offset + origin.x(), y_offset + origin.y())
    return matrix


def adjusted_placement_in_bounds(rect: QRect, bounds: QRect) -> QRect:
    """Returns the closest rectangle to the rect param that fits within a bounding rectangle.

    More specifically:
    - Width and height of the rectangle are only reduced if they exceed the width or height of the bounds.
    - The rectangle is translated the minimum distance necessary to place it fully within the bounds.
    """
    if bounds.width() <= rect.width() and bounds.height() <= rect.height():
        return QRect(bounds)
    adjusted_rect = QRect(rect)
    if bounds.contains(rect):
        return adjusted_rect
    if adjusted_rect.width() > bounds.width():
        adjusted_rect.setWidth(bounds.width())
    if adjusted_rect.height() > bounds.height():
        adjusted_rect.setHeight(bounds.height())
    if adjusted_rect.x() < bounds.x():
        adjusted_rect.moveLeft(bounds.x())
    if (adjusted_rect.x() + adjusted_rect.width()) > (bounds.x() + bounds.width()):
        adjusted_rect.moveLeft(bounds.x() + bounds.width() - adjusted_rect.width())
    if adjusted_rect.y() < bounds.y():
        adjusted_rect.moveTop(bounds.y())
    if (adjusted_rect.y() + adjusted_rect.height()) > (bounds.y() + bounds.height()):
        adjusted_rect.moveTop(bounds.y() + bounds.height() - adjusted_rect.height())
    assert bounds.contains(adjusted_rect)
    return adjusted_rect


def is_smaller_size(size1: QSize, size2: QSize) -> bool:
    """Returns whether size1 is smaller than size2"""
    return size1.width() * size1.height() < size2.width() * size2.height()


def fill_outside_rect(painter: QPainter, bounds: QRect, excluded: QRect, color: QColor | Qt.GlobalColor) -> None:
    """Paint all content within a given bounds, excluding one rectangle"""
    if bounds.isEmpty():
        return
    if excluded.isEmpty() or not bounds.intersects(excluded):
        painter.fillRect(bounds, color)
        return
    bounds = bounds.normalized()
    excluded = excluded.normalized().intersected(bounds)
    right = QRect(excluded.x() + excluded.width(), bounds.y(),
                  (bounds.x() + bounds.width()) - (excluded.x() + excluded.width()), bounds.height())
    left = QRect(bounds.x(), bounds.y(), excluded.x() - bounds.x(), bounds.height())
    top = QRect(left.x() + left.width(), bounds.y(), right.x() - (left.x() + left.width()), excluded.y() - bounds.y())
    bottom = QRect(top.x(), excluded.y() + excluded.height(), top.width(),
                   bounds.height() - (excluded.y() + excluded.height()))
    for border_rect in (left, right, top, bottom):
        assert bounds.contains(border_rect)
        if not border_rect.isEmpty():
            painter.fillRect(border_rect, color)


def closest_point_keeping_aspect_ratio(moving_point: QPointF, source_point: QPointF, aspect_ratio: float) -> QPointF:
    """
    Given a moving_point, a source_point, and an aspect_ratio, find the adjusted point closest to the moving point where
    the absolute aspect ratio of the rectangle created by source_point, adjusted_point is equal to abs(aspect_ratio).

    Parameters:
    -----------
    moving_point: QPointF
        The point to adjust.
    source_point: QPointF
        The fixed initial point used in calculating the aspect ratio.
    aspect_ratio: float
        The expected aspect ratio, as width/height. If the value is closer to zero than MIN_NONZERO, it will be adjusted
        to MIN_NONZERO.
    Returns:
    --------
    adjusted_point: QPointF
        Given that rect_final = QRectF(source_point, adjusted_point), adjusted_point is the closest point to
        moving_point where abs(aspect_ratio) equals abs(final_rect.width() / final_rect.height()).
    """
    aspect_ratio = max(abs(aspect_ratio), MIN_NONZERO)
    width = abs(moving_point.x() - source_point.x())
    height = abs(moving_point.y() - source_point.y())
    adjusted_height = width / aspect_ratio
    adjusted_width = height / aspect_ratio
    point_options = [
        QPointF(moving_point.x(), source_point.y() + adjusted_height),
        QPointF(moving_point.x(), source_point.y() - adjusted_height),
        QPointF(source_point.x() + adjusted_width, moving_point.y()),
        QPointF(source_point.x() - adjusted_width, moving_point.y())
    ]
    min_distance = FLOAT_MAX
    adjusted_point = None
    for point in point_options:
        distance = QLineF(moving_point, point).length()
        if distance < min_distance:
            min_distance = distance
            adjusted_point = point
    assert adjusted_point is not None
    return adjusted_point


def closest_size_keeping_aspect_ratio(new_size: QSizeF, aspect_ratio: float) -> QSizeF:
    """Given a new size and an aspect ratio, return the size with the same aspect ratio that's closes to new_size."""
    closest_point = closest_point_keeping_aspect_ratio(QPointF(new_size.width(), new_size.height()), QPointF(),
                                                       aspect_ratio)
    return QSizeF(closest_point.x(), closest_point.y())
