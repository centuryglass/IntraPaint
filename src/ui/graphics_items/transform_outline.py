"""Provides controls for transforming a graphics item."""
import math
from typing import Optional, Dict, Tuple, Any, Generator

from PyQt5.QtCore import Qt, QRectF, QPointF, QSizeF, pyqtSignal, QLineF
from PyQt5.QtGui import QPainter, QPen, QTransform, QIcon, QPainterPath
from PyQt5.QtWidgets import QWidget, QGraphicsItem, QStyleOptionGraphicsItem, \
    QGraphicsRectItem, QGraphicsSceneMouseEvent, QGraphicsTransform, \
    QGraphicsObject

from src.util.shared_constants import MIN_NONZERO

MIN_SCENE_DIM = 5

HANDLE_SIZE = 20
ORIGIN_HANDLE_ID = 'transformation origin'
TL_HANDLE_ID = 'top left'
TR_HANDLE_ID = 'top right'
BL_HANDLE_ID = 'bottom left'
BR_HANDLE_ID = 'bottom right'

LINE_COLOR = Qt.black
LINE_WIDTH = 3

CORNER_SCALE_ARROW_FILE = 'resources/arrow_corner.svg'
CORNER_ROTATE_ARROW_FILE = 'resources/arrow_corner_rot.svg'

MODE_SCALE = 'scale'
MODE_ROTATE = 'rotate'


class TransformOutline(QGraphicsObject):
    """Transform a graphics item by dragging corners"""

    # Emits offset, x-scale, y-scale, rotation
    transform_changed = pyqtSignal(QPointF, float, float, float)

    def __init__(self) -> None:
        super().__init__()

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._handles: Dict[str, _Handle] = {}
        self._relative_origin = QPointF(0.5, 0.5)
        self._scene_origin = QPointF()
        self._rect = QRectF()
        self._pen = QPen(LINE_COLOR, LINE_WIDTH)
        self._preserve_aspect_ratio = False
        self._mode = MODE_SCALE

        for handle_id in (ORIGIN_HANDLE_ID, TL_HANDLE_ID, TR_HANDLE_ID, BL_HANDLE_ID, BR_HANDLE_ID):
            self._handles[handle_id] = _Handle(self, handle_id)
        self.transformation_origin = self.rect().center()
        self._update_handles()

    @property
    def preserve_aspect_ratio(self) -> bool:
        """Returns whether all transformations preserve the original aspect ratio provided through setRect."""
        return self._preserve_aspect_ratio

    @preserve_aspect_ratio.setter
    def preserve_aspect_ratio(self, should_preserve: bool) -> None:
        self._preserve_aspect_ratio = should_preserve
        if should_preserve:
            x_scale, y_scale = self.scale
            scale = max(abs(x_scale), abs(y_scale))
            x_scale = math.copysign(scale, x_scale)
            y_scale = math.copysign(scale, y_scale)
            self.scale = (x_scale, y_scale)

    @property
    def x(self) -> float:
        """The minimum x-position within the scene, after all transformations are applied."""
        return min(pt.x() for pt in self._corner_points_in_scene())

    @x.setter
    def x(self, new_x: float) -> None:
        """Set the minimum x-position within the scene, without changing rotation or scale."""
        self._move_to(new_x, self.y)
        self._send_transform_signal()

    @property
    def y(self) -> float:
        """The minimum y-position within the scene, after all transformations are applied."""
        return min(pt.y() for pt in self._corner_points_in_scene())

    @y.setter
    def y(self, new_y: float) -> None:
        """Set the minimum x-position within the scene, without changing rotation or scale."""
        self._move_to(self.x, new_y)
        self._send_transform_signal()

    @property
    def width(self) -> float:
        """The full width within the scene, ignoring rotations."""
        x_scale, _ = self.scale
        return abs(self.rect().width() * x_scale)

    @width.setter
    def width(self, new_width) -> None:
        _, y_scale = self.scale
        x_scale = new_width / self.rect().width()
        if self._preserve_aspect_ratio:
            y_scale = math.copysign(x_scale, y_scale)
        self._set_scale(x_scale, y_scale)
        self._send_transform_signal()

    @property
    def height(self) -> float:
        """The full height within the scene, ignoring rotations."""
        _, y_scale = self.scale
        return abs(self.rect().height() * y_scale)

    @height.setter
    def height(self, new_height: float) -> None:
        x_scale, _ = self.scale
        y_scale = new_height / self.rect().height()
        if self._preserve_aspect_ratio:
            x_scale = math.copysign(y_scale, x_scale)
        self._set_scale(x_scale, y_scale)
        self._send_transform_signal()

    @property
    def offset(self) -> QPointF:
        """Gets the offset from the origin before rotation and scaling."""
        transform = self.transform()
        return QPointF(transform.m31(), transform.m32())

    @offset.setter
    def offset(self, new_offset: QPointF) -> None:
        self._set_offset(new_offset)
        self._send_transform_signal()

    @property
    def scale(self) -> Tuple[float, float]:
        """Get the width and height scale factors."""
        if self.rect().isEmpty():
            return 1.0, 1.0
        width_init = self.rect().width()
        height_init = self.rect().height()
        top_left = self.mapToScene(self.rect().topLeft())
        top_right = self.mapToScene(self.rect().topRight())
        bottom_left = self.mapToScene(self.rect().bottomLeft())
        transform = self.sceneTransform()
        width_final = math.copysign(QLineF(top_left, top_right).length(), transform.m11())
        height_final = math.copysign(QLineF(top_left, bottom_left).length(), transform.m22())
        scale_x = width_final / width_init
        scale_y = height_final / height_init
        angle = self.rotation
        if 90 <= angle <= 270:
            scale_x *= -1
            scale_y *= -1
        scale_x, scale_y = (MIN_NONZERO if scale == 0 else scale for scale in (scale_x, scale_y))
        return scale_x, scale_y

    @scale.setter
    def scale(self, scale_factors: Tuple[float, float]) -> None:
        scale_x, scale_y = scale_factors
        if self._preserve_aspect_ratio:
            prev_x, prev_y = self.scale
            x_change = scale_x - prev_x
            y_change = scale_y - prev_y
            if abs(x_change) > abs(y_change):
                scale_y = math.copysign(scale_x, scale_y)
            elif abs(y_change) > abs(x_change):
                scale_x = math.copysign(scale_y, scale_x)
            else:
                scale = max(scale_x, scale_y)
                scale_x = math.copysign(scale, scale_x)
                scale_y = math.copysign(scale, scale_y)
        self._set_scale(scale_x, scale_y)
        self._send_transform_signal()

    @property
    def rotation(self) -> float:
        """Gets the rotation in degrees."""
        rotation_pt = self.mapToScene(QPointF(1.0, 0.0)) - self.mapToScene(QPointF(0.0, 0.0))
        angle = math.degrees(math.atan2(rotation_pt.y(), rotation_pt.x()))
        while angle < 0:
            angle += 360.0
        return angle

    @rotation.setter
    def rotation(self, angle: float) -> None:
        self._set_rotation(angle)
        self._send_transform_signal()

    @property
    def transformation_origin(self) -> QPointF:
        """Return the transformation origin point."""
        bounds = self.rect()
        origin_x = bounds.x() + bounds.width() * self._relative_origin.x()
        origin_y = bounds.y() + bounds.height() * self._relative_origin.y()
        return QPointF(origin_x, origin_y)

    @transformation_origin.setter
    def transformation_origin(self, pos: QPointF) -> None:
        """Move the transformation origin to a new point within the outline bounds."""
        bounds = self.rect()
        pos.setX(max(min(bounds.right(), pos.x()), bounds.x()))
        pos.setY(max(min(bounds.bottom(), pos.y()), bounds.y()))
        if ORIGIN_HANDLE_ID in self._handles:
            origin = self._handles[ORIGIN_HANDLE_ID]
            origin.prepareGeometryChange()
            bounds = self.rect()
            origin.setRect(_get_handle_rect(pos))
            pos -= bounds.topLeft()
        self.setTransformOriginPoint(pos)
        if not bounds.isEmpty():
            self._relative_origin = QPointF(pos.x() / bounds.width(), pos.y() / bounds.height())
            self._scene_origin = self.mapToScene(pos)
            self._send_transform_signal()
        assert self.transformation_origin == pos, f'Tried to set transformation_origin to {pos}, got {self.transformation_origin}'

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Start dragging the layer."""
        for handle in self._handles.values():
            # Ensure handles can still be selected during extreme transformations by passing off input to any handle
            # within approx. 10px of the click event:
            handle_pos = handle.mapToScene(handle.rect().center())
            distance = (event.scenePos() - handle_pos).manhattanLength()
            if distance < 10:
                handle.mousePressEvent(event)
                return
        super().mousePressEvent(event)
        self.setSelected(True)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Change drag mode on double-click."""
        if self._mode == MODE_SCALE:
            self._mode = MODE_ROTATE
        else:
            self._mode = MODE_SCALE
        for handle in self._handles.values():
            handle.set_mode_icon(self._mode)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Translate the layer, following the cursor."""
        super().mouseMoveEvent(event)
        change = event.scenePos() - event.lastScenePos()
        self.offset = change + self.offset

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Stop dragging the layer."""
        super().mouseReleaseEvent(event)
        self.setSelected(False)

    def move_transformation_handle(self, handle_id: str, pos: QPointF) -> None:
        """Perform required changes whenever one of the handles moves."""
        assert handle_id in self._handles, str(self._handles)
        if handle_id == ORIGIN_HANDLE_ID:
            self.transformation_origin = pos
        elif handle_id in (TL_HANDLE_ID, TR_HANDLE_ID, BL_HANDLE_ID, BR_HANDLE_ID):
            self.move_corner(handle_id, pos)
        else:
            raise RuntimeError(f'Invalid handle id {handle_id}')

    def move_corner(self, corner_id: str, corner_pos) -> None:
        """Move one of the corners, leaving the position of the opposite corner unchanged. If Ctrl is held, also
           preserve aspect ratio."""
        initial_rect = self.rect()

        if self._mode == MODE_SCALE:
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
            if final_rect.width() == 0:
                final_rect.setWidth(MIN_NONZERO)
            if final_rect.height() == 0:
                final_rect.setHeight(MIN_NONZERO)
            x_scale = final_rect.width() / initial_rect.width()
            y_scale = final_rect.height() / initial_rect.height()
            if self._preserve_aspect_ratio:
                current_x_scale, current_y_scale = self.scale
                final_x_scale = x_scale * current_x_scale
                final_y_scale = y_scale * current_y_scale
                if abs(final_x_scale) != abs(final_y_scale):
                    if abs(final_x_scale) < abs(final_y_scale):
                        x_scale = math.copysign(x_scale * final_y_scale / final_x_scale, x_scale)
                    else:
                        y_scale = math.copysign(y_scale * final_x_scale / final_y_scale, y_scale)
            origin = get_fixed_corner()
            scale = self.sceneTransform()
            scale.translate(origin.x(), origin.y())
            scale.scale(x_scale, y_scale)
            scale.translate(-origin.x(), -origin.y())
            self._set_transform(scale, False)
        elif self._mode == MODE_ROTATE:
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
            self._set_rotation(self.rotation + angle_offset)
        self._send_transform_signal()

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draw a simple rectangle."""
        painter.save()
        painter.setPen(self._pen)
        painter.drawRect(self._rect)
        painter.restore()

    def boundingRect(self) -> QRectF:
        """Set bounding rect to the scene item size, preserving minimums so that mouse input still works at small
           scales."""
        rect = self.mapRectToScene(self.rect()).normalized()
        if rect.width() < MIN_SCENE_DIM:
            rect.adjust(-(MIN_SCENE_DIM - rect.width()) / 2, 0.0, (MIN_SCENE_DIM - rect.width()) / 2, 0.0)
        if rect.height() < MIN_SCENE_DIM:
            rect.adjust(0.0, -(MIN_SCENE_DIM - rect.height()) / 2, 0.0, -(MIN_SCENE_DIM - rect.height()) / 2)
        return self.mapRectFromScene(rect)

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
        self._rect = QRectF(rect)
        self._scene_origin = self.mapToScene(QPointF(rect.x() + rect.width() * self._relative_origin.x(),
                                                     rect.y() + rect.height() * self._relative_origin.y()))
        self._update_handles()
        self._send_transform_signal()

    def clearTransformations(self, send_transformation_signal: bool = True) -> None:
        """Remove all transformations."""
        super().setTransform(QTransform())
        super().setTransformations([])
        if send_transformation_signal:
            self._send_transform_signal()

    def setTransform(self, matrix: QTransform, combine: bool = False) -> None:
        """Update listeners when transformations change."""
        self._set_transform(matrix, combine)
        self._send_transform_signal()

    def _set_transform(self, matrix: QTransform, combine: bool = False) -> None:
        """Update transformations without immediately notifying listeners.."""
        if combine is False:
            super().setTransformations([])
            self.resetTransform()
        super().setTransform(matrix, combine)

    def _corner_points_in_scene(self) -> Generator[QPointF | QPointF, Any, None]:
        bounds = self.rect()
        corners = (self.mapToScene(pt) for pt in (bounds.topLeft(), bounds.topRight(),
                                                  bounds.bottomLeft(), bounds.bottomRight()))
        return corners

    def _add_transform(self, transform: QGraphicsTransform, send_signal: bool = True) -> None:
        transformations = self.transformations()
        transformations.append(transform)
        if send_signal:
            self.setTransformations(transformations)
        else:
            super().setTransformations(transformations)

    def _update_handles(self) -> None:
        """Keep the corners and origin positioned and sized correctly as the rectangle transforms."""
        bounds = self.rect()
        for handle_id, point in ((TL_HANDLE_ID, bounds.topLeft()), (TR_HANDLE_ID, bounds.topRight()),
                                 (BL_HANDLE_ID, bounds.bottomLeft()), (BR_HANDLE_ID, bounds.bottomRight())):
            handle_rect = _get_handle_rect(point)
            self._handles[handle_id].prepareGeometryChange()
            self._handles[handle_id].setRect(handle_rect)
        origin_x = bounds.x() + bounds.width() * self._relative_origin.x()
        origin_y = bounds.y() + bounds.height() * self._relative_origin.y()
        self._handles[ORIGIN_HANDLE_ID].prepareGeometryChange()
        self._handles[ORIGIN_HANDLE_ID].setRect(_get_handle_rect(QPointF(origin_x, origin_y)))

    def _send_transform_signal(self) -> None:
        offset = self.offset
        scale_x, scale_y = self.scale
        rotation = self.rotation
        self.transform_changed.emit(offset, scale_x, scale_y, rotation)

    def _move_to(self, x: float, y: float) -> None:
        x_off = x - self.x
        y_off = y - self.y
        if x_off != 0 or y_off != 0:
            offset = self.offset + QPointF(x_off, y_off)
            self._set_offset(offset)

    def _set_offset(self, offset: QPointF) -> None:
        transform = QTransform(self.sceneTransform())
        transform.setMatrix(transform.m11(), transform.m12(), transform.m13(),
                            transform.m21(), transform.m22(), transform.m23(),
                            offset.x(), offset.y(), transform.m33())
        self._set_transform(transform, False)
        self._scene_origin += self.mapToScene(offset)

    def _set_scale(self, x_scale: float, y_scale: float) -> None:
        scale_x, scale_y = (MIN_NONZERO if scale == 0 else scale for scale in (x_scale, y_scale))
        prev_x, prev_y = self.scale
        origin = self.transformation_origin
        scale = QTransform()
        scale.translate(origin.x(), origin.y())
        scale.scale(scale_x / prev_x, scale_y / prev_y)
        scale.translate(-origin.x(), -origin.y())
        self._set_transform(scale, True)

    def _set_rotation(self, angle: float) -> None:
        while angle < 0:
            angle += 360.0
        while angle >= 360.0:
            angle -= 360.0
        origin = self.mapToScene(self.transformation_origin)
        prev_transform = self.sceneTransform()
        rotation = QTransform()
        rotation.translate(origin.x(), origin.y())
        rotation.rotate(angle - self.rotation)
        rotation.translate(-origin.x(), -origin.y())
        self._set_transform(rotation, False)
        self._set_transform(prev_transform, True)


class _Handle(QGraphicsRectItem):
    """Small square the user can drag to adjust the item properties."""

    def __init__(self, parent: TransformOutline, handle_id: str) -> None:
        super().__init__(parent)
        self.setZValue(parent.zValue() + 2)
        self._handle_id = handle_id
        self.setToolTip(handle_id)
        self._last_pos = None
        self._parent = parent
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setBrush(Qt.black)
        self.setPen(Qt.white)
        self._arrow_icon = QIcon(CORNER_SCALE_ARROW_FILE)
        self._rot_arrow_icon = QIcon(CORNER_ROTATE_ARROW_FILE)
        self._icon = self._arrow_icon

    def set_mode_icon(self, mode: str) -> None:
        """Sets the appropriate icon for the given mode."""
        if mode == MODE_ROTATE:
            self._icon = self._rot_arrow_icon
        elif mode == MODE_SCALE:
            self._icon = self._arrow_icon
        else:
            raise ValueError(f'Invalid mode {mode}')
        self.update()

    def boundingRect(self) -> QRectF:
        """Ensure handle bounds within the scene are large enough for the handle to remain clickable within extreme
           transforms."""
        rect = self.mapRectToScene(super().rect()).normalized()
        if rect.width() < MIN_SCENE_DIM:
            rect.adjust(-(MIN_SCENE_DIM - rect.width()) / 2, 0.0, (MIN_SCENE_DIM - rect.width()) / 2, 0.0)
        if rect.height() < MIN_SCENE_DIM:
            rect.adjust(0.0, -(MIN_SCENE_DIM - rect.height()) / 2, 0.0, -(MIN_SCENE_DIM - rect.height()) / 2)
        return self.mapRectFromScene(rect)

    def setRect(self, rect: QRectF) -> None:
        """Adjust the origin and corner handles when the outline bounds change, ensuring bounds remain non-empty"""
        if rect.width() == 0:
            rect.setWidth(MIN_NONZERO)
        if rect.height() == 0:
            rect.setHeight(MIN_NONZERO)
        super().setRect(rect)

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """When painting, apply all transformations to the center position, but leave scale unchanged."""
        painter.save()
        transform = painter.transform()
        inverse = transform.inverted()[0]
        painter.setTransform(inverse, True)
        pos = transform.map(self.rect().center())
        painter.translate(pos)
        rect = _get_handle_rect(QPointF())
        painter.fillRect(rect, self.brush())
        painter.setPen(self.pen())
        painter.drawRect(rect)

        if self._handle_id != ORIGIN_HANDLE_ID:
            arrow_pixmap = self._icon.pixmap(rect.size().toSize())
            arrow_bounds = QRectF(rect.topLeft() - QPointF(rect.width(), rect.height()), rect.size())
            # get base rotation:
            angle = self._parent.rotation

            scale_x, scale_y = self._parent.scale
            mirrored = (scale_y < 0 < scale_x) or (scale_x < 0 < scale_y)

            if mirrored:
                angles = {
                    TL_HANDLE_ID: 270.0,
                    TR_HANDLE_ID: 180.0,
                    BR_HANDLE_ID: 90.0,
                    BL_HANDLE_ID: 0.0
                }
            else:
                angles = {
                    TL_HANDLE_ID: 0.0,
                    TR_HANDLE_ID: 90.0,
                    BR_HANDLE_ID: 180.0,
                    BL_HANDLE_ID: 270.0
                }

            painter.rotate(angle + angles[self._handle_id])
            painter.drawPixmap(arrow_bounds.toAlignedRect(), arrow_pixmap)
        painter.restore()

    def _update_and_send_pos(self, pos: QPointF) -> None:
        self._parent.move_transformation_handle(self._handle_id, pos)
        self._last_pos = QPointF(pos)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Select the clicked handle, start sending handle position changes back to the transformation outline."""
        super().mousePressEvent(event)
        self.setSelected(True)
        self._update_and_send_pos(event.pos())

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Continue sending handle position changes to the transformation outline."""
        self._update_and_send_pos(event.pos())

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Send the final handle position change to the transformation outline, and de-select the handle."""
        self._update_and_send_pos(event.pos())
        self.setSelected(False)


def _get_handle_rect(pos: QPointF) -> QRectF:
    return QRectF(pos - QPointF(HANDLE_SIZE / 2, HANDLE_SIZE / 2), QSizeF(HANDLE_SIZE, HANDLE_SIZE))
