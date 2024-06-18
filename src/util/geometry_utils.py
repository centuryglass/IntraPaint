"""Provides a utility function for handling image or widget placement."""

from PyQt5.QtCore import QRect, QSize, QRectF, QSizeF
from PyQt5.QtGui import QTransform, QPolygonF


def get_scaled_placement(container_rect: QRect,
                         inner_size: QSize, margin_width: int = 0) -> QRect:
    """
    Calculate the most appropriate placement of a scaled rectangle within a container, without changing aspect ratio.
    Parameters:
    -----------
    container_rect : QRect
        Bounds of the container where the scaled rectangle will be placed.        
    inner_size : QSize
        S of the rectangle to be scaled and placed within the container.
    margin_width : int
        Distance in pixels of the area around the container edges that should remain empty.
    Returns:
    --------
    placement : QRect
        Size and position of the scaled rectangle within container_rect.
    """
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


def transform_str(transformation: QTransform) -> str:
    """Return a string representation of a transformation matrix for debugging."""
    return (f'\n\t[{transformation.m11()}, {transformation.m12()}, {transformation.m13()}]'
            f'\n\t[{transformation.m21()}, {transformation.m22()}, {transformation.m23()}]'
            f'\n\t[{transformation.m31()}, {transformation.m32()}, {transformation.m33()}]\n')


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
