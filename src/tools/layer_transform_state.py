"""The layer transform tool's state: one immutable value that holds a layer's transform as editable fields.

The state projects to a matrix one way, through `combine_transform_parameters`, and `TransformState.from_matrix` is
the only decomposition. Each edit returns a new state that holds one point in place, so a field the edit doesn't
name keeps its value.
"""
import math
from dataclasses import dataclass, replace
from typing import Optional

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QTransform

from src.util.math_utils import clamp
from src.util.shared_constants import MIN_NONZERO
from src.util.visual.geometry_utils import combine_transform_parameters, extract_transform_parameters

CENTER = (0.5, 0.5)

# A QTransform's affine entries, in the order QTransform's six-argument constructor takes them:
_AffineEntries = tuple[float, float, float, float, float, float]


def _nonzero(scale: float) -> float:
    """Returns scale, moved out to MIN_NONZERO with its sign kept if it is closer to zero."""
    if abs(scale) < MIN_NONZERO:
        return math.copysign(MIN_NONZERO, scale)
    return scale


@dataclass(frozen=True)
class TransformState:
    """A layer's transform, without perspective, as the transform tool edits it.

    Fields hold plain floats, so no Qt value is shared with a state. The Qt-valued properties return new copies.
    - `bounds`: the layer's untransformed rectangle, as (x, y, width, height).
    - `relative`: the transformation origin as a fraction of `bounds`, from 0 to 1 on each axis.
    - `origin`: the origin's scene position, which the panel shows as X and Y.
    - `x_scale`, `y_scale`, `skew` and `rotation` are applied about the origin, as `combine_transform_parameters`
      describes. `skew` and `rotation` are in degrees.
    - `source` holds the matrix the state was read from, until an edit changes the transform. `matrix()` returns it
      unchanged, so reading a layer's transform into a state and writing it back leaves the layer as it was.
    """
    bounds: tuple[float, float, float, float]
    relative: tuple[float, float]
    origin: tuple[float, float]
    x_scale: float
    y_scale: float
    skew: float
    rotation: float
    source: Optional[_AffineEntries] = None

    @staticmethod
    def from_matrix(matrix: QTransform, rect: QRectF,
                    relative_origin: QPointF = QPointF(*CENTER)) -> Optional['TransformState']:
        """Reads a matrix into a state about the origin at relative_origin within rect.

        Returns None for a perspective or non-invertible matrix, which the fields can't express.
        """
        if (matrix.m13() != 0.0 or matrix.m23() != 0.0 or matrix.m33() != 1.0
                or not matrix.isInvertible()):
            return None
        rect = QRectF(rect)
        relative = (relative_origin.x(), relative_origin.y())
        origin_local = _local_point(rect, relative)
        params = extract_transform_parameters(matrix, origin_local)
        origin_pos = matrix.map(origin_local)
        return TransformState((rect.x(), rect.y(), rect.width(), rect.height()), relative,
                              (origin_pos.x(), origin_pos.y()), params.x_scale, params.y_scale, params.skew,
                              params.rotation,
                              (matrix.m11(), matrix.m12(), matrix.m21(), matrix.m22(), matrix.dx(), matrix.dy()))

    # -----------------------------------------------------------------------------------------------------------------
    # Readings
    # -----------------------------------------------------------------------------------------------------------------

    @property
    def rect(self) -> QRectF:
        """The layer's untransformed bounds."""
        return QRectF(*self.bounds)

    @property
    def relative_origin(self) -> QPointF:
        """The transformation origin as a fraction of `rect`."""
        return QPointF(*self.relative)

    @property
    def origin_local(self) -> QPointF:
        """The transformation origin in the layer's untransformed coordinates."""
        return _local_point(self.rect, self.relative)

    @property
    def origin_pos(self) -> QPointF:
        """The transformation origin's scene position."""
        return QPointF(*self.origin)

    @property
    def width(self) -> float:
        """The layer's scaled width, ignoring skew and rotation."""
        return abs(self.bounds[2] * self.x_scale)

    @property
    def height(self) -> float:
        """The layer's scaled height, ignoring skew and rotation."""
        return abs(self.bounds[3] * self.y_scale)

    def matrix(self) -> QTransform:
        """Returns the transform the state describes."""
        if self.source is not None:
            return QTransform(*self.source)
        origin_local = self.origin_local
        return combine_transform_parameters(self.origin[0] - origin_local.x(), self.origin[1] - origin_local.y(),
                                            self.x_scale, self.y_scale, self.skew, self.rotation, origin_local)

    # -----------------------------------------------------------------------------------------------------------------
    # Edits
    # -----------------------------------------------------------------------------------------------------------------

    def _edited(self, **changes) -> 'TransformState':
        """Returns a copy with changes applied and no source matrix, so `matrix()` projects its fields."""
        return replace(self, source=None, **changes)

    def moved_by(self, dx: float, dy: float) -> 'TransformState':
        """Returns the state moved by (dx, dy) in the scene."""
        if dx == 0.0 and dy == 0.0:
            return self
        return self._edited(origin=(self.origin[0] + dx, self.origin[1] + dy))

    def with_origin_pos(self, pos: QPointF) -> 'TransformState':
        """Returns the state moved so that the transformation origin lands on pos."""
        return self.moved_by(pos.x() - self.origin[0], pos.y() - self.origin[1])

    def with_rotation(self, degrees: float) -> 'TransformState':
        """Returns the state rotated to degrees about the transformation origin."""
        if degrees == self.rotation:
            return self
        return self._edited(rotation=degrees)

    def with_skew(self, degrees: float) -> 'TransformState':
        """Returns the state skewed to degrees about the transformation origin. degrees must be strictly between -90
           and 90."""
        if degrees == self.skew:
            return self
        return self._edited(skew=degrees)

    def with_scale(self, x_scale: float, y_scale: float) -> 'TransformState':
        """Returns the state scaled about the transformation origin. A scale closer to zero than MIN_NONZERO moves out
           to it, keeping its sign."""
        x_scale, y_scale = _nonzero(x_scale), _nonzero(y_scale)
        if x_scale == self.x_scale and y_scale == self.y_scale:
            return self
        return self._edited(x_scale=x_scale, y_scale=y_scale)

    def with_size(self, width: float, height: float) -> 'TransformState':
        """Returns the state scaled about the transformation origin to a width and height, keeping each scale's sign,
           so a flip stays. An axis of zero untransformed length keeps its scale."""
        rect_width, rect_height = self.bounds[2], self.bounds[3]
        x_scale = math.copysign(width / rect_width, self.x_scale) if rect_width != 0 else self.x_scale
        y_scale = math.copysign(height / rect_height, self.y_scale) if rect_height != 0 else self.y_scale
        return self.with_scale(x_scale, y_scale)

    def with_relative_origin(self, point: QPointF) -> 'TransformState':
        """Returns the state with the transformation origin moved to point, a fraction of `rect` clamped to 0-1. The
           layer stays put: the matrix is unchanged, and `origin_pos` follows the origin."""
        relative = (clamp(point.x(), 0.0, 1.0), clamp(point.y(), 0.0, 1.0))
        if relative == self.relative:
            return self
        origin_pos = self.matrix().map(_local_point(self.rect, relative))
        return replace(self, relative=relative, origin=(origin_pos.x(), origin_pos.y()))

    def anchored(self, local_point: QPointF, scene_point: QPointF) -> 'TransformState':
        """Returns the state moved so that local_point, in untransformed coordinates, maps to scene_point."""
        mapped = self.matrix().map(local_point)
        return self.moved_by(scene_point.x() - mapped.x(), scene_point.y() - mapped.y())

    def with_corner_moved(self, corner: QPointF, target: QPointF,
                          fixed_ratio: Optional[float] = None) -> 'TransformState':
        """Returns the state scaled so that corner, one of `rect`'s corners, moves to target, holding the opposite
           corner in place. Both points are in untransformed coordinates.

        The scale is applied before skew and rotation, so both keep their values. With fixed_ratio, the result keeps
        abs(x_scale / y_scale) at that ratio.
        """
        rect = self.rect
        fixed = QPointF(rect.left() + rect.right() - corner.x(), rect.top() + rect.bottom() - corner.y())

        def _change(target_offset: float, span: float) -> float:
            if span == 0.0:
                return 1.0
            if abs(target_offset) < MIN_NONZERO:
                return MIN_NONZERO / abs(span)
            return target_offset / span

        x_change = _change(target.x() - fixed.x(), corner.x() - fixed.x())
        y_change = _change(target.y() - fixed.y(), corner.y() - fixed.y())
        final_x_scale = x_change * self.x_scale
        final_y_scale = y_change * self.y_scale
        if fixed_ratio is not None and abs(final_x_scale) * fixed_ratio != abs(final_y_scale):
            if abs(final_x_scale) < abs(final_y_scale):
                x_change = math.copysign(x_change * final_y_scale / final_x_scale * fixed_ratio, x_change)
            else:
                y_change = math.copysign(y_change * final_x_scale / final_y_scale / fixed_ratio, y_change)
        if abs(final_x_scale) < MIN_NONZERO:
            x_change = MIN_NONZERO / self.x_scale
        if abs(final_y_scale) < MIN_NONZERO:
            y_change = MIN_NONZERO / self.y_scale
        if x_change == 1.0 and y_change == 1.0:
            return self
        matrix = self.matrix()
        matrix.translate(fixed.x(), fixed.y())
        matrix.scale(x_change, y_change)
        matrix.translate(-fixed.x(), -fixed.y())
        scaled = TransformState.from_matrix(matrix, rect, self.relative_origin)
        return self if scaled is None else scaled

    def with_corner_turned(self, corner: QPointF, target: QPointF) -> 'TransformState':
        """Returns the state rotated about the transformation origin so that corner, in untransformed coordinates,
           lies in target's direction from the origin. target is a scene point.

        Angles are measured in the scene, so the corner follows the cursor on scaled and flipped layers too.
        """
        corner_start = self.matrix().map(corner)
        origin = self.origin_pos
        start_vector = corner_start - origin
        target_vector = target - origin
        start_angle = math.degrees(math.atan2(start_vector.y(), start_vector.x()))
        target_angle = math.degrees(math.atan2(target_vector.y(), target_vector.x()))
        return self.with_rotation(self.rotation + target_angle - start_angle)


def _local_point(rect: QRectF, relative: tuple[float, float]) -> QPointF:
    """Returns the point at a fractional position within rect."""
    return QPointF(rect.x() + rect.width() * relative[0], rect.y() + rect.height() * relative[1])
