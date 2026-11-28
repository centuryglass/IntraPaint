"""Provides a utility function for handling image or widget placement."""
import logging
import math
from typing import NamedTuple, Optional

from PySide6.QtCore import QRect, QSize, QRectF, QSizeF, QPoint, QPointF, QLineF, Qt, QMargins
from PySide6.QtGui import QTransform, QPolygonF

from src.util.math_utils import convert_degrees
from src.util.shared_constants import MIN_NONZERO, FLOAT_MAX

logger = logging.getLogger(__name__)


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


def align_inner_bounds(outer_bounds: QRect | QRectF, inner_bounds: QRect | QRectF,
                       alignment: Qt.AlignmentFlag, margins: Optional[QMargins] = None) -> None:
    """Edits an inner_bounds rectangle in-place to position it within a rectangle using a given alignment."""
    assert outer_bounds.width() >= inner_bounds.width() and outer_bounds.height() >= inner_bounds.height() \
           and not inner_bounds.isEmpty(), f'outer={outer_bounds}, inner={inner_bounds}'
    if margins is None:
        left_margin = 0
        right_margin = 0
        top_margin = 0
        bottom_margin = 0
    else:
        left_margin = margins.left()
        right_margin = margins.right()
        top_margin = margins.top()
        bottom_margin = margins.bottom()

    def _validate_and_correct_margins(dim_name: str, outer_size: int, inner_size: int,
                                      start_margin: int, end_margin: int) -> tuple[int, int]:
        if outer_size >= (inner_size + start_margin + end_margin):
            return start_margin, end_margin
        logger.warning(f'inner {dim_name} plus margins exceeds outer {dim_name}, margins will be adjusted.  '
                       f'outer={outer_size}, inner={inner_size}, margins={start_margin},{end_margin}')
        margin_available = outer_size - inner_size
        if margin_available == 0:
            return 0, 0
        if start_margin == 0:
            return 0, margin_available
        new_start_margin = round(margin_available * start_margin / (start_margin + end_margin))
        return new_start_margin, margin_available - new_start_margin

    left_margin, right_margin = _validate_and_correct_margins('width', outer_bounds.width(),
                                                              inner_bounds.width(), left_margin, right_margin)
    top_margin, bottom_margin = _validate_and_correct_margins('height', outer_bounds.height(),
                                                              inner_bounds.height(), top_margin, bottom_margin)
    x: int | float = outer_bounds.x() + left_margin
    y: int | float = outer_bounds.y() + top_margin
    if alignment & Qt.AlignmentFlag.AlignHCenter == Qt.AlignmentFlag.AlignHCenter:
        x += (outer_bounds.width() - inner_bounds.width() - left_margin - right_margin) / 2
    elif alignment & Qt.AlignmentFlag.AlignRight == Qt.AlignmentFlag.AlignRight:
        x = outer_bounds.x() + outer_bounds.width() - inner_bounds.width() - right_margin
    if alignment & Qt.AlignmentFlag.AlignVCenter == Qt.AlignmentFlag.AlignVCenter:
        y += (outer_bounds.height() - inner_bounds.height() - top_margin - bottom_margin) / 2
    elif alignment & Qt.AlignmentFlag.AlignBottom == Qt.AlignmentFlag.AlignBottom:
        y = outer_bounds.y() + outer_bounds.height() - inner_bounds.height() - bottom_margin
    if isinstance(inner_bounds, QRect):
        x = int(round(x))
        y = int(round(y))
    inner_bounds.moveLeft(x)
    inner_bounds.moveTop(y)
    assert outer_bounds.contains(inner_bounds), f'{inner_bounds} not in {outer_bounds}'


def get_rect_transformation(source: QRect | QRectF | QSize, destination: QRect | QRectF | QSize) -> QTransform:
    """Gets the transformation required to transform source into destination. Parameters may be either QRect or QSize,
       if QSize is used they will be treated as a rectangle of that size at the origin."""

    def _as_rect_f(param: QRect | QRectF | QSize | QSizeF) -> QRectF:
        if isinstance(param, (QSize, QSizeF)):
            return QRectF(0.0, 0.0, param.width(), param.height())
        return QRectF(param)

    source_rect: QRectF
    dest_rect: QRectF
    source_rect, dest_rect = (_as_rect_f(param) for param in (source, destination))
    if dest_rect.size().isEmpty():
        logger.error('Invalid rect transform: destination is empty')
        return QTransform()
    # Extract points from the original rectangle
    sx = dest_rect.width() / source_rect.width()
    sy = dest_rect.height() / source_rect.height()
    return QTransform.fromTranslate(-source_rect.x(), -source_rect.y()) * QTransform().scale(sx, sy) \
        * QTransform.fromTranslate(dest_rect.x(), dest_rect.y())


def map_rect_precise(rect: QRect | QRectF, transform: QTransform) -> QRectF:
    """Returns the bounds of a rectangle after applying a transformation, converted to floating point to prevent
     rounding errors."""
    polygon = QPolygonF(QRectF(rect))
    transformed_poly = transform.map(polygon)
    assert isinstance(transformed_poly, QPolygonF)
    return transformed_poly.boundingRect()


def panel_position(rect: QRect | QRectF, transform: QTransform) -> QPointF:
    """Returns the X/Y position the text tool panel shows for a transformed rectangle: the scene position of the
       rectangle's local top-left corner.

    The corner is the same point the layer transform tool's panel shows with its origin snapped to the top-left
    corner (TransformState.origin_pos). For a flipped rectangle it is not the top-left of the bounding box.
    The text tool reads and writes position through this function and transform_at_panel_position.
    """
    return transform.map(QPointF(rect.topLeft()))


def transform_at_panel_position(rect: QRect | QRectF, transform: QTransform, position: QPointF) -> QTransform:
    """Returns the transform translated so that panel_position(rect, result) is position, with rotation and scale
       unchanged."""
    offset = position - panel_position(rect, transform)
    return transform * QTransform.fromTranslate(offset.x(), offset.y())


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


def transform_scale(transformation: QTransform) -> tuple[float, float]:
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


# How far a linear matrix entry may sit from a whole number and still count as one in
# transform_needs_smooth_sampling. It absorbs the float residue that composing rotations leaves, while moving no pixel
# by more than 0.01 px across a 10000 px layer.
PIXEL_GRID_TOLERANCE = 1e-6


def transform_needs_smooth_sampling(transformation: QTransform) -> bool:
    """Returns whether layers drawn through a transformation are sampled smoothly, rather than pixel-exact.

    A transformation draws pixel-exact when its linear part maps the pixel grid onto itself: it is axis-aligned, or
    turned by a right angle, and every entry of m11, m12, m21 and m22 is a whole number, within PIXEL_GRID_TOLERANCE.
    That covers flips and uneven whole-number scales. Every other scale, rotation or skew is sampled smoothly, which
    blends neighboring source pixels, so a changed pixel can affect image pixels one past its mapped bounds.
    Translation is ignored.
    """
    entries = (transformation.m11(), transformation.m12(), transformation.m21(), transformation.m22())
    if any(abs(entry - round(entry)) > PIXEL_GRID_TOLERANCE for entry in entries):
        return True
    m11, m12, m21, m22 = (round(entry) for entry in entries)
    axis_aligned = (m12 == 0 and m21 == 0) or (m11 == 0 and m22 == 0)
    return not axis_aligned or m11 * m22 - m12 * m21 == 0


class TransformParameters(NamedTuple):
    """A transformation without perspective, measured about an origin.

    Applied in the order scale, skew, rotation, offset (see `combine_transform_parameters`). `skew` and `rotation` are
    in degrees.
    """
    x_offset: float
    y_offset: float
    x_scale: float
    y_scale: float
    skew: float
    rotation: float


def extract_transform_parameters(transform: QTransform, origin: Optional[QPointF] = None) -> TransformParameters:
    """Breaks a matrix without perspective into offset, scale, skew and rotation about an origin.

    The result round-trips through `combine_transform_parameters`. Rotation is the direction of the layer's x-axis,
    in [0, 360). The scales are never both negative, and if one is, rotation is below 180 degrees.
    """
    # Not all transformations can be decomposed this way, throw an error if this one can't be:
    assert transform.isInvertible(), f'Non-invertible transform {transform_str(transform)}'
    assert transform.m13() == 0.0
    assert transform.m23() == 0.0
    assert transform.m33() == 1.0

    if origin is None:
        origin = QPointF()

    transform_at_origin = QTransform.fromTranslate(origin.x(), origin.y()) * transform \
        * QTransform.fromTranslate(-origin.x(), -origin.y())
    x_offset = transform_at_origin.dx()
    y_offset = transform_at_origin.dy()

    # (m11, m12) is where the x-axis arrow goes, and (m21, m22) is where the y-axis arrow goes.
    x_scale = math.hypot(transform.m11(), transform.m12())
    angle_degrees = convert_degrees(math.degrees(math.atan2(transform.m12(), transform.m11())))
    y_scale = transform.determinant() / x_scale
    along_x_axis = (transform.m21() * transform.m11() + transform.m22() * transform.m12()) / x_scale
    skew_degrees = -math.degrees(math.atan(along_x_axis / y_scale))

    # x_scale, y_scale, rotation equals -x_scale, -y_scale, rotation+180deg with the same skew, so standardize:
    # - x_scale and y_scale will never both be negative.
    # - If one of the two values must be negative, choose the option that results in a rotation that's less than 180
    #   degrees.
    if (x_scale < 0 and y_scale < 0) or ((x_scale < 0 or y_scale < 0) and angle_degrees >= 180.0):
        x_scale *= -1
        y_scale *= -1
        angle_degrees = convert_degrees(angle_degrees - 180.0)
    return TransformParameters(x_offset, y_offset, x_scale, y_scale, skew_degrees, angle_degrees)


def combine_transform_parameters(x_offset: float, y_offset: float, x_scale: float, y_scale: float, skew: float,
                                 degrees: float, origin: Optional[QPointF] = None) -> QTransform:
    """Combines scale, skew, rotation and offset about an origin into a single transformation, applied in that order.

    Positive skew moves the top edge right relative to the bottom edge, and must be strictly between -90 and 90 degrees.
    """
    if origin is None:
        origin = QPointF()
    assert x_scale != 0.0 and y_scale != 0.0, 'Non-invertible transformation parameters used'
    assert -90.0 < skew < 90.0, f'Skew {skew} outside (-90, 90)'
    matrix = QTransform.fromTranslate(-origin.x(), -origin.y())
    matrix *= QTransform.fromScale(x_scale, y_scale)
    if skew != 0.0:
        matrix *= QTransform(1.0, 0.0, -math.tan(math.radians(skew)), 1.0, 0.0, 0.0)
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
    adjusted_width = height * aspect_ratio
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


def closest_point_keeping_angle(start_point: QPointF, end_point: QPointF, angle_degrees: float) -> QPointF:
    """Given a start point, an end point, and an angle, return the closest point to the end point that keeps
       the angle of the line fixed at angle_degrees."""
    fixed_line = QLineF(start_point, end_point)
    fixed_line.setAngle(angle_degrees)
    perpendicular_line = QLineF(end_point, end_point + QPointF(1.0, 0.0))
    perpendicular_line.setAngle(angle_degrees + 90.0)
    return fixed_line.intersects(perpendicular_line)[1]


def closest_point_at_angle_option(start_point: QPointF, end_point: QPointF,
                                  angles: list[float]) -> tuple[QPointF, float]:
    """Given a start point, an end point, and a list of possible angles, return the closest point to the end point that
       fixes the angle at a value in the list, and the angle selected."""
    closest_point: Optional[QPointF] = None
    distance = FLOAT_MAX
    closest_angle = -1.0
    for angle in angles:
        closest_at_angle = closest_point_keeping_angle(start_point, end_point, angle)
        test_distance = QLineF(end_point, closest_at_angle).length()
        if test_distance < distance:
            closest_point = closest_at_angle
            distance = test_distance
            closest_angle = angle
    assert closest_point is not None
    return closest_point, closest_angle
