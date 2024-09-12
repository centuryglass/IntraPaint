"""Provides controls for transforming a graphics item."""
import math
from typing import Optional, Dict, Tuple, Any, Generator, Iterable

from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QSizeF
from PySide6.QtGui import QPainter, QPen, QTransform, QPainterPath, QImage
from PySide6.QtWidgets import QWidget, QGraphicsItem, QStyleOptionGraphicsItem, \
    QGraphicsSceneMouseEvent, QGraphicsTransform, \
    QGraphicsObject

from src.ui.graphics_items.transform_handle import TransformHandle, TRANSFORM_MODE_SCALE, TRANSFORM_MODE_ROTATE
from src.util.visual.geometry_utils import extract_transform_parameters, combine_transform_parameters
from src.util.visual.graphics_scene_utils import (get_view_bounds_of_scene_item_rect,
                                                  map_scene_item_point_to_view_point,
                                                  get_scene_item_bounds_of_view_rect, get_view,
                                                  get_scene_bounds_of_scene_item_rect)
from src.util.visual.image_utils import create_transparent_image
from src.util.math_utils import clamp, avoiding_zero
from src.util.shared_constants import MIN_NONZERO

MIN_SCENE_DIM = 5

ORIGIN_HANDLE_ID = 'transformation origin'
TL_HANDLE_ID = 'top left'
TR_HANDLE_ID = 'top right'
BL_HANDLE_ID = 'bottom left'
BR_HANDLE_ID = 'bottom right'

LINE_COLOR = Qt.GlobalColor.black
LINE_WIDTH = 3


class TransformOutline(QGraphicsObject):
    """Translate, rotate, and/or scale a graphics item via mouse input or properties.

    To use:
    -------
    - Pass in initial scene bounds on construction.
    - Create the manipulated item as a child of the TransformOutline, placed on the same bounds.
    - Add to a QGraphicsView.
    - Adjust the origin of future transformations by dragging the center transformation handle, or by setting the
      transformation_origin property.
    - Translate by dragging the outline anywhere other than the transformation handles, or by assigning values to the
      x, y, or offset properties.
    - Scale by dragging the corner handles, or by assigning values to the width, height, or scale properties.
    - Rotate by double-clicking then dragging corner handles, or by assigning to the rotation property.
    - Export the final transformation as an image via the render method.
    """

    transform_changed = Signal(QTransform)
    offset_changed = Signal(float, float)
    scale_changed = Signal(float, float)
    angle_changed = Signal(float)

    # Signal specifically meant for using TransformOutline for rectangle positioning within a transformed layer:
    # Emitted rectangle factors in transform scale and offset, but ignores rotation.
    transformed_rect_changed = Signal(QRectF)

    def __init__(self, initial_bounds: QRectF, allow_rotate=True, include_origin_handle=True,
                 fixed_scale=False) -> None:
        super().__init__()

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._allow_rotate = allow_rotate
        self._handles: Dict[str, _Handle] = {}
        self._relative_origin = QPointF(0.5, 0.5)
        self._rect = QRectF(initial_bounds.normalized())
        self._origin = self._rect.center()
        self._x_offset = 0.0
        self._y_offset = 0.0
        self._x_scale = 0.0
        self._y_scale = 0.0
        self._degrees = 0.0
        self._pen = QPen(LINE_COLOR, LINE_WIDTH)
        self._pen.setCosmetic(True)
        self._preserve_aspect_ratio = False
        self._fixed_scale = fixed_scale
        self._mode = TRANSFORM_MODE_SCALE

        for handle_id in (TL_HANDLE_ID, TR_HANDLE_ID, BL_HANDLE_ID, BR_HANDLE_ID, ORIGIN_HANDLE_ID):
            if not include_origin_handle and handle_id == ORIGIN_HANDLE_ID:
                continue
            self._handles[handle_id] = _Handle(self, handle_id)
        self.transformation_origin = self.rect().center()
        self._update_handles()

    @property
    def transformed_scene_bounds(self) -> QRectF:
        """Returns the bounds of the outline within the scene after all transformations have been applied."""
        return get_scene_bounds_of_scene_item_rect(self._rect, self)

    def setTransformations(self, transformations: Iterable[QGraphicsTransform]) -> None:
        """Block alternate graphics transformations, they aren't useful here, and they'll break other calculations."""
        raise RuntimeError('Do not use setTransformations with TransformOutline.')

    def setTransform(self, matrix: QTransform, combine: bool = False) -> None:
        """Update listeners when transformations change."""
        if combine:
            dx, dy, sx, sy, angle = extract_transform_parameters(self.transform() * matrix, self.transformation_origin)
        else:
            dx, dy, sx, sy, angle = extract_transform_parameters(matrix, self.transformation_origin)
        offset_changed = dx != self._x_offset or dy != self._y_offset
        scale_changed = sx != self._x_scale or sy != self._y_scale
        angle_changed = angle != self._degrees
        self._x_offset = dx
        self._y_offset = dy
        self._x_scale = sx
        self._y_scale = sy
        self._degrees = angle
        super().setTransform(matrix, combine)
        if offset_changed or scale_changed or angle_changed:
            self.transform_changed.emit(self.transform())
        if offset_changed:
            self.offset_changed.emit(dx, dy)
        if scale_changed:
            self.scale_changed.emit(sx, sy)
        if angle_changed:
            self.angle_changed.emit(angle)
        if offset_changed or scale_changed:
            transformed_rect = QRectF(self.mapToScene(self._rect.topLeft()),
                                      QSizeF(abs(sx) * self._rect.width(), abs(sy) * self._rect.height()))
            self.transformed_rect_changed.emit(transformed_rect)

    def setZValue(self, z: float) -> None:
        """Ensure handle z-values stay in sync with the outline."""
        super().setZValue(z)
        for handle in self._handles.values():
            handle.setZValue(z - 2)

    @property
    def preserve_aspect_ratio(self) -> bool:
        """Returns whether all transformations preserve the original aspect ratio provided through setRect."""
        return self._preserve_aspect_ratio

    @preserve_aspect_ratio.setter
    def preserve_aspect_ratio(self, should_preserve: bool) -> None:
        self._preserve_aspect_ratio = should_preserve
        if should_preserve:
            x_scale, y_scale = self._x_scale, self._y_scale
            scale = max(abs(x_scale), abs(y_scale))
            x_scale = math.copysign(scale, x_scale)
            y_scale = math.copysign(scale, y_scale)
            self.transform_scale = (x_scale, y_scale)

    @property
    def x_pos(self) -> float:
        """The minimum x-position within the scene, after all transformations are applied."""
        return min(pt.x() for pt in self._corner_points_in_scene())

    @x_pos.setter
    def x_pos(self, new_x: float) -> None:
        """Set the minimum x-position within the scene, without changing rotation or scale."""
        offset = new_x - self.x_pos
        matrix = combine_transform_parameters(self._x_offset + offset, self._y_offset, self._x_scale, self._y_scale,
                                              self._degrees, self.transformation_origin)
        self.setTransform(matrix)

    @property
    def y_pos(self) -> float:
        """The minimum y-position within the scene, after all transformations are applied."""
        return min(pt.y() for pt in self._corner_points_in_scene())

    @y_pos.setter
    def y_pos(self, new_y: float) -> None:
        """Set the minimum x-position within the scene, without changing rotation or scale."""
        offset = new_y - self.y_pos
        matrix = combine_transform_parameters(self._x_offset, self._y_offset + offset, self._x_scale, self._y_scale,
                                              self._degrees, self.transformation_origin)
        self.setTransform(matrix)

    @property
    def width(self) -> float:
        """The full width within the scene, ignoring rotations."""
        return abs(self.rect().width() * self._x_scale)

    @width.setter
    def width(self, new_width) -> None:
        y_scale = self._y_scale
        x_scale = new_width / self.rect().width()
        if x_scale == 0:
            x_scale = math.copysign(MIN_NONZERO, x_scale)
        if self._preserve_aspect_ratio:
            y_scale = math.copysign(x_scale, y_scale)
        matrix = combine_transform_parameters(self._x_offset, self._y_offset, x_scale, y_scale, self._degrees,
                                              self.transformation_origin)
        self.setTransform(matrix)

    @property
    def height(self) -> float:
        """The full height within the scene, ignoring rotations."""
        return abs(self.rect().height() * self._y_scale)

    @height.setter
    def height(self, new_height: float) -> None:
        x_scale = self._x_scale
        y_scale = new_height / self.rect().height()
        if y_scale == 0:
            y_scale = math.copysign(MIN_NONZERO, y_scale)
        if self._preserve_aspect_ratio:
            x_scale = math.copysign(y_scale, x_scale)
        matrix = combine_transform_parameters(self._x_offset, self._y_offset, x_scale, y_scale, self._degrees,
                                              self.transformation_origin)
        self.setTransform(matrix)

    @property
    def offset(self) -> QPointF:
        """Gets the offset from the origin before rotation and scaling."""
        return QPointF(self._x_offset, self._y_offset)

    @offset.setter
    def offset(self, new_offset: QPointF) -> None:
        matrix = combine_transform_parameters(new_offset.x(), new_offset.y(), self._x_scale, self._y_scale,
                                              self._degrees, self.transformation_origin)
        self.setTransform(matrix)

    @property
    def transform_scale(self) -> Tuple[float, float]:
        """Get the width and height scale factors."""
        return self._x_scale, self._y_scale

    @transform_scale.setter
    def transform_scale(self, scale_factors: Tuple[float, float]) -> None:
        x_scale, y_scale = scale_factors
        if self._preserve_aspect_ratio:
            prev_x, prev_y = self.transform_scale
            x_change = x_scale - prev_x
            y_change = y_scale - prev_y
            if abs(x_change) > abs(y_change):
                y_scale = math.copysign(x_scale, y_scale)
            elif abs(y_change) > abs(x_change):
                x_scale = math.copysign(y_scale, x_scale)
            else:
                scale = max(x_scale, y_scale)
                x_scale = math.copysign(scale, x_scale)
                y_scale = math.copysign(scale, y_scale)
        matrix = combine_transform_parameters(self._x_offset, self._y_offset, x_scale, y_scale, self._degrees,
                                              self.transformation_origin)
        self.setTransform(matrix)

    @property
    def rotation_angle(self) -> float:
        """Gets the rotation in degrees."""
        return self._degrees

    @rotation_angle.setter
    def rotation_angle(self, angle: float) -> None:
        matrix = combine_transform_parameters(self._x_offset, self._y_offset, self._x_scale, self._y_scale, angle,
                                              self.transformation_origin)
        self.setTransform(matrix)

    @property
    def transformation_origin(self) -> QPointF:
        """Return the transformation origin point in local coordinates."""
        return self._origin

    @transformation_origin.setter
    def transformation_origin(self, pos: QPointF) -> None:
        """Move the transformation origin to a new point within the outline bounds."""
        bounds = self.rect()
        pos.setX(clamp(pos.x(), bounds.x(), bounds.right()))
        pos.setY(clamp(pos.y(), bounds.y(), bounds.bottom()))
        if pos != self._origin:
            if ORIGIN_HANDLE_ID in self._handles:
                origin_handle = self._handles[ORIGIN_HANDLE_ID]
                origin_handle.move_rect_center(pos)
                self._origin = pos
            self.setTransform(self.transform())

    def render(self) -> QImage:
        """Render all externally added child items to an image, with transformations included."""
        scene = self.scene()
        if scene is None:
            raise RuntimeError('TransformOutline cannot render without being in a scene.')

        # Find descendants, excluding handles:
        children = set()
        add_children = [self]
        while len(add_children) > 0:
            item = add_children.pop()
            for child in item.childItems():
                if isinstance(child, _Handle):
                    continue
                children.add(child)
                add_children.append(child)

        # Temporarily hide everything else in the scene:
        opacity_map: Dict[QGraphicsItem, float] = {}
        for item in scene.items():
            if item not in children:
                opacity_map[item] = item.opacity()
                item.setOpacity(0.0)
        scene.update()

        # Create image and render:
        bounds = self.mapRectToScene(self.rect())
        image = create_transparent_image(bounds.size().toSize())
        painter = QPainter(image)
        scene.render(painter, QRectF(QPointF(), bounds.size()), bounds)
        painter.end()

        # Restore previous scene item visibility:
        for scene_item, opacity in opacity_map.items():
            scene_item.setOpacity(opacity)
        scene.update()
        return image

    def mousePressEvent(self, event: Optional[QGraphicsSceneMouseEvent]) -> None:
        """Start dragging the layer."""
        assert event is not None
        for handle in self._handles.values():
            # Ensure handles can still be selected during extreme transformations by passing off input to any handle
            # within approx. 10px of the click event:
            view = get_view(self)
            handle_pos = map_scene_item_point_to_view_point(handle.rect().center(), handle)
            click_pos = QPointF(view.mapFromGlobal(event.screenPos()))
            distance = (click_pos - handle_pos).manhattanLength()
            if distance < handle.rect().width() * 2:
                handle.setSelected(True)
                handle.mousePressEvent(event)
                return
        super().mousePressEvent(event)
        self.setSelected(True)

    def mouseDoubleClickEvent(self, event: Optional[QGraphicsSceneMouseEvent]) -> None:
        """Change drag mode on double-click, if enabled."""
        assert event is not None
        if not self._allow_rotate:
            return
        if self._mode == TRANSFORM_MODE_SCALE:
            self._mode = TRANSFORM_MODE_ROTATE
        else:
            self._mode = TRANSFORM_MODE_SCALE
        for handle in self._handles.values():
            handle.set_mode_icon(self._mode)

    def mouseMoveEvent(self, event: Optional[QGraphicsSceneMouseEvent]) -> None:
        """Translate the layer, following the cursor."""
        assert event is not None
        super().mouseMoveEvent(event)
        for handle in self._handles.values():
            if handle.isSelected():
                handle.mouseMoveEvent(event)
                return
        change = QPointF(event.scenePos() - event.lastScenePos())
        self.offset = change + self.offset

    def mouseReleaseEvent(self, event: Optional[QGraphicsSceneMouseEvent]) -> None:
        """Stop dragging the layer."""
        assert event is not None
        super().mouseReleaseEvent(event)
        for handle in self._handles.values():
            if handle.isSelected():
                handle.mouseReleaseEvent(event)
        self.setSelected(False)

    def move_transformation_handle(self, handle_id: str, pos: QPointF) -> None:
        """Perform required changes whenever one of the handles moves."""
        assert handle_id in self._handles, str(self._handles)
        pos = self.mapFromScene(pos)
        if handle_id == ORIGIN_HANDLE_ID:
            self.transformation_origin = pos
        elif handle_id in (TL_HANDLE_ID, TR_HANDLE_ID, BL_HANDLE_ID, BR_HANDLE_ID):
            self.move_corner(handle_id, pos)
        else:
            raise RuntimeError(f'Invalid handle id {handle_id}')

    def move_corner(self, corner_id: str, corner_pos: QPointF, _=None) -> None:
        """Move one of the corners, leaving the position of the opposite corner unchanged. If Ctrl is held, also
           preserve aspect ratio."""
        initial_rect = self.rect()

        if self._mode == TRANSFORM_MODE_SCALE:
            # Move the dragged corner, keeping the opposite corner fixed:
            final_rect = QRectF(initial_rect)
            adjustment_params = {
                TL_HANDLE_ID: (final_rect.setTopLeft, final_rect.bottomRight),
                TR_HANDLE_ID: (final_rect.setTopRight, final_rect.bottomLeft),
                BL_HANDLE_ID: (final_rect.setBottomLeft, final_rect.topRight),
                BR_HANDLE_ID: (final_rect.setBottomRight, final_rect.topLeft)
            }
            assert corner_id in adjustment_params, f'Invalid corner ID {corner_id}'
            move_corner, get_fixed_corner = adjustment_params[corner_id]
            move_corner(corner_pos)

            if abs(final_rect.width()) < MIN_NONZERO:
                final_rect.setWidth(MIN_NONZERO)
            if abs(final_rect.height()) < MIN_NONZERO:
                final_rect.setHeight(MIN_NONZERO)
            x_scale = final_rect.width() / initial_rect.width()
            y_scale = final_rect.height() / initial_rect.height()
            current_x_scale, current_y_scale = self.transform_scale

            if self._fixed_scale:
                offset = final_rect.topLeft() - initial_rect.topLeft()
                self.setRect(final_rect.normalized())
                if offset != QPointF():
                    transform = self.transform() * QTransform.fromTranslate(offset.x(), offset.y())
                    self.setTransform(transform)
                else:
                    transformed_rect = QRectF(self.mapToScene(self._rect.topLeft()),
                                              QSizeF(abs(current_x_scale) * self._rect.width(),
                                                     abs(current_y_scale) * self._rect.height()))
                    self.transformed_rect_changed.emit(transformed_rect)
                return

            final_x_scale = x_scale * current_x_scale
            final_y_scale = y_scale * current_y_scale
            if self._preserve_aspect_ratio:
                if abs(final_x_scale) != abs(final_y_scale):
                    if abs(final_x_scale) < abs(final_y_scale):
                        x_scale = math.copysign(x_scale * final_y_scale / final_x_scale, x_scale)
                    else:
                        y_scale = math.copysign(y_scale * final_x_scale / final_y_scale, y_scale)
            origin = get_fixed_corner()

            def _scale_change_avoiding_minimums(scale_change: float, current_scale: float, final_scale: float) -> float:
                if abs(final_scale) >= MIN_NONZERO:
                    return scale_change
                return MIN_NONZERO / current_scale
            x_scale = _scale_change_avoiding_minimums(x_scale, current_x_scale, final_x_scale)
            y_scale = _scale_change_avoiding_minimums(y_scale, current_y_scale, final_y_scale)
            if x_scale != 1.0 or y_scale != 1.0:
                scale = self.transform()
                scale.translate(origin.x(), origin.y())
                scale.scale(x_scale, y_scale)
                scale.translate(-origin.x(), -origin.y())
                self.setTransform(scale)
        elif self._mode == TRANSFORM_MODE_ROTATE:
            # Rotate the rectangle so that the dragged corner is as close as possible to corner_pos:
            corners = {
                TL_HANDLE_ID: initial_rect.topLeft(),
                TR_HANDLE_ID: initial_rect.topRight(),
                BL_HANDLE_ID: initial_rect.bottomLeft(),
                BR_HANDLE_ID: initial_rect.bottomRight()
            }
            corner_start = corners[corner_id]
            origin = self.transformation_origin
            init_vector = corner_start - origin
            target_vector = corner_pos - origin
            init_angle = math.degrees(math.atan2(init_vector.y(), init_vector.x()))
            final_angle = math.degrees(math.atan2(target_vector.y(), target_vector.x()))
            angle_offset = final_angle - init_angle
            self.rotation_angle = self.rotation_angle + angle_offset

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draw a simple rectangle."""
        assert painter is not None
        painter.save()
        painter.setPen(self._pen)
        painter.drawRect(self._rect)
        painter.restore()

    def boundingRect(self) -> QRectF:
        """Set bounding rect to the scene item size, preserving minimums so that mouse input still works at small
           scales."""
        rect = get_view_bounds_of_scene_item_rect(self.rect(), self)
        if rect.width() < MIN_SCENE_DIM:
            rect.adjust(-(MIN_SCENE_DIM - rect.width()) / 2, 0.0, (MIN_SCENE_DIM - rect.width()) / 2, 0.0)
        if rect.height() < MIN_SCENE_DIM:
            rect.adjust(0.0, -(MIN_SCENE_DIM - rect.height()) / 2, 0.0, (MIN_SCENE_DIM - rect.height()) / 2)
        adjusted_rect = get_scene_item_bounds_of_view_rect(rect, self)
        return adjusted_rect

    def shape(self) -> QPainterPath:
        """Returns the outline's bounds as a shape."""
        path = QPainterPath()
        path.addRect(QRectF(self.boundingRect()))
        return path

    def rect(self) -> QRectF:
        """Return the transformed area's original bounds."""
        return self._rect

    def setRect(self, rect: QRectF) -> None:
        """Set the transformed area's original bounds."""
        self.prepareGeometryChange()
        rect.setWidth(avoiding_zero(rect.width()))
        rect.setHeight(avoiding_zero(rect.height()))
        self._rect = QRectF(rect)
        self._origin = QPointF(rect.x() + rect.width() * self._relative_origin.x(),
                               rect.y() + rect.height() * self._relative_origin.y())
        self._update_handles()

    def _corner_points_in_scene(self) -> Generator[QPointF | QPointF, Any, None]:
        bounds = self.rect()
        corners = (self.mapToScene(pt) for pt in (bounds.topLeft(), bounds.topRight(),
                                                  bounds.bottomLeft(), bounds.bottomRight()))
        return corners

    def _update_handles(self) -> None:
        """Keep the corners and origin positioned and sized correctly as the rectangle transforms."""
        bounds = self.rect()
        for handle_id, point in ((TL_HANDLE_ID, bounds.topLeft()), (TR_HANDLE_ID, bounds.topRight()),
                                 (BL_HANDLE_ID, bounds.bottomLeft()), (BR_HANDLE_ID, bounds.bottomRight())):
            self._handles[handle_id].move_rect_center(point)
        origin_x = bounds.x() + bounds.width() * self._relative_origin.x()
        origin_y = bounds.y() + bounds.height() * self._relative_origin.y()
        if ORIGIN_HANDLE_ID in self._handles:
            self._handles[ORIGIN_HANDLE_ID].move_rect_center(QPointF(origin_x, origin_y))


class _Handle(TransformHandle):
    """Small square the user can drag to adjust the item properties."""

    def __init__(self, parent: TransformOutline, handle_id: str) -> None:
        base_angle = 0
        if handle_id == TL_HANDLE_ID:
            base_angle = 225
        elif handle_id == TR_HANDLE_ID:
            base_angle = 315
        elif handle_id == BR_HANDLE_ID:
            base_angle = 45
        elif handle_id == BL_HANDLE_ID:
            base_angle = 135
        super().__init__(parent, handle_id, base_angle, handle_id != ORIGIN_HANDLE_ID)
        self.dragged.connect(parent.move_transformation_handle)

    def _get_parent_transform_params(self) -> Tuple[float, float, float]:
        parent = self.parentItem()
        assert isinstance(parent, TransformOutline)
        x_scale, y_scale = parent.transform_scale
        return x_scale, y_scale, parent.rotation_angle
