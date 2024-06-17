"""Provides controls for transforming a graphics item."""
import math
from typing import Optional, Dict, Tuple, List, Any, Generator

from PyQt5.QtCore import Qt, QRectF, QPointF, QSizeF, QPoint, QObject, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QTransform, QVector3D, QIcon
from PyQt5.QtWidgets import QWidget, QGraphicsItem, QStyleOptionGraphicsItem, \
    QGraphicsRectItem, QGraphicsSceneMouseEvent, QApplication, QGraphicsRotation, QGraphicsScale, QGraphicsTransform

from src.ui.widget.image_graphics_view import ImageGraphicsView

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

MIN_NONZERO = 0.001


class TransformOutline(QGraphicsRectItem):
    """Transform a graphics item by dragging corners"""

    def __init__(self, view: ImageGraphicsView) -> None:
        super().__init__()

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._handles: Dict[str, _Handle] = {}
        self._fractional_origin = QPointF(0.5, 0.5)
        self._view = view
        self._initial_aspect_ratio = 1.0
        self._drag_pt: Optional[QPointF] = None

        class _SignalBearer(QObject):
            transform_changed = pyqtSignal(QPointF, float, float, float)
        self._signal_bearer = _SignalBearer()
        self.transform_changed = self._signal_bearer.transform_changed

        pen = QPen(LINE_COLOR, LINE_WIDTH)
        pen.setCosmetic(True)
        self.setPen(pen)

        for handle_id in (ORIGIN_HANDLE_ID, TL_HANDLE_ID, TR_HANDLE_ID, BL_HANDLE_ID, BR_HANDLE_ID):
            self._handles[handle_id] = _Handle(self, handle_id)
        # put the origin point below the others in order to ensure the corner can be grabbed when points overlap:
        self._handles[BR_HANDLE_ID].setZValue(self.zValue() + 3)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        self.transformation_origin = self.rect().center()
        self._update_handles()

    @property
    def rotation(self) -> float:
        """Gets the rotation in degrees."""
        transform = self.sceneTransform()
        return 90 - math.degrees(math.atan2(transform.m11(), transform.m12()))

    @rotation.setter
    def rotation(self, angle: float) -> None:
        transformation = QGraphicsRotation()
        transformation.setOrigin(QVector3D(self.transformation_origin))
        transformation.setAngle(angle - self.rotation)
        self._add_transform(transformation)


    @property
    def x(self) -> float:
        """The minimum x-position within the scene, after all transformations are applied."""
        return min(pt.x() for pt in self._corner_points_in_scene())

    @x.setter
    def x(self, new_x: float) -> None:
        """Set the minimum x-position within the scene, without changing rotation or scale."""
        x_offset = new_x - self.x
        if x_offset != 0:
            offset = self.offset
            offset.setX(offset.x() + x_offset)
            self.offset = offset

    @property
    def y(self) -> float:
        """The minimum y-position within the scene, after all transformations are applied."""
        return min(pt.y() for pt in self._corner_points_in_scene())

    @y.setter
    def y(self, new_y: float) -> None:
        """Set the minimum x-position within the scene, without changing rotation or scale."""
        y_offset = new_y - self.y
        if y_offset != 0:
            offset = self.offset
            offset.setY(offset.y() + y_offset)
            self.offset = offset

    @property
    def width(self) -> float:
        """The full width within the scene, after all transformations are applied."""
        x_min = min(pt.x() for pt in self._corner_points_in_scene())
        x_max = max(pt.x() for pt in self._corner_points_in_scene())
        return abs(x_max - x_min)

    @width.setter
    def width(self, new_width) -> float:
        self.set_size(new_width, self.height)

    @property
    def height(self) -> float:
        """The full height within the scene, after all transformations are applied."""
        y_min = min(pt.y() for pt in self._corner_points_in_scene())
        y_max = max(pt.y() for pt in self._corner_points_in_scene())
        return abs(y_max - y_min)

    @height.setter
    def height(self, new_height: float) -> None:
        self.set_size(self.width, new_height)

    def set_size(self, new_width: float, new_height: float, preserve_aspect_ratio= False) -> None:
        """Set the full width within the scene, preserving rotation and angles"""
        prev_width = self.width
        prev_height= self.height
        prev_angle = self.rotation
        origin = self.transformation_origin
        x_scale_factor = new_width / prev_width
        y_scale_factor = new_height / prev_height

        # Update the transformation matrix to scale around the origin
        new_transform = QTransform()
        new_transform.translate(origin.x(), origin.y())
        new_transform.rotate(-prev_angle)
        if preserve_aspect_ratio:
            scale_factor = max(x_scale_factor, y_scale_factor)
            new_transform.scale(scale_factor, scale_factor)
        else:
            new_transform.scale(x_scale_factor, y_scale_factor)
        new_transform.rotate(prev_angle)
        new_transform.translate(-origin.x(), -origin.y())
        self.setTransform(new_transform, True)

    @property
    def offset(self) -> QPointF:
        """Gets the offset from the origin before rotation and scaling."""
        return self.mapToScene(QPointF())

    @offset.setter
    def offset(self, new_offset: QPointF) -> None:
        initial_offset = self.offset
        translation = QTransform.fromTranslate(new_offset.x() - initial_offset.x(), new_offset.y() - initial_offset.y())
        self.setTransform(translation, True)

    @property
    def scale(self) -> Tuple[float, float]:
        """Get the width and height scale factors."""
        transform = self.sceneTransform()
        scale_x = math.sqrt(transform.m11() ** 2 + transform.m21() ** 2)
        scale_y = math.sqrt(transform.m12() ** 2 + transform.m22() ** 2)
        scale_x, scale_y = (MIN_NONZERO if scale == 0 else scale for scale in (scale_x, scale_y))
        return scale_x, scale_y

    @scale.setter
    def scale(self, scale_factors: Tuple[float, float]) -> None:
        scale_x, scale_y = (MIN_NONZERO if scale == 0 else scale for scale in scale_factors)
        prev_x, prev_y = self.scale
        transform = QGraphicsScale()
        transform.setOrigin(QVector3D(self.transformation_origin))
        transform.setXScale(scale_x / prev_x)
        transform.setYScale(scale_y / prev_y)
        self._add_transform(transform)

    @property
    def transformation_origin(self) -> QPointF:
        """Return the transformation origin point."""
        bounds = self.rect()
        origin_x = bounds.x() + bounds.width() * self._fractional_origin.x()
        origin_y = bounds.y() + bounds.height() * self._fractional_origin.y()
        return QPointF(origin_x, origin_y)

    @transformation_origin.setter
    def transformation_origin(self, pos: QPointF) -> None:
        """Move the transformation origin to a new point within the outline bounds."""
        if ORIGIN_HANDLE_ID in self._handles:
            bounds = self.rect()
            pos.setX(max(min(bounds.right(), pos.x()), bounds.x()))
            pos.setY(max(min(bounds.bottom(), pos.y()), bounds.y()))
            origin = self._handles[ORIGIN_HANDLE_ID]
            origin.prepareGeometryChange()
            bounds = self.rect()
            origin.setRect(_get_handle_rect(pos))
            pos -= bounds.topLeft()
            self.setTransformOriginPoint(pos)
            if not bounds.isEmpty():
                self._fractional_origin = QPointF(pos.x() / bounds.width(), pos.y() / bounds.height())
                self._send_transform_signal()

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Start dragging the layer."""
        super().mousePressEvent(event)
        self.setSelected(True)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Translate the layer, following the cursor."""
        super().mouseMoveEvent(event)
        change = event.pos() - event.lastPos()
        offset = change + self.offset
        self.offset = offset

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
        final_rect = QRectF(initial_rect)

        def fix_width_keeping_x2(width: float) -> None:
            """Adjust the width without moving the right edge."""
            final_rect.setX(final_rect.x() + final_rect.width() - width)

        def fix_height_keeping_y2(height: float) -> None:
            """Adjust the height without moving the bottom edge."""
            final_rect.setY(final_rect.y() + final_rect.height() - height)

        adjustment_fns = {
            TL_HANDLE_ID: (final_rect.setTopLeft, final_rect.bottomRight, fix_width_keeping_x2, fix_height_keeping_y2),
            TR_HANDLE_ID: (final_rect.setTopRight, final_rect.bottomLeft, final_rect.setWidth, fix_height_keeping_y2),
            BL_HANDLE_ID: (final_rect.setBottomLeft, final_rect.topRight, fix_width_keeping_x2, final_rect.setHeight),
            BR_HANDLE_ID: (final_rect.setBottomRight, final_rect.topLeft, final_rect.setWidth, final_rect.setHeight)
        }
        assert corner_id in adjustment_fns, f'Invalid corner ID {corner_id}'
        move_corner, get_fixed_corner, set_width, set_height = adjustment_fns[corner_id]
        move_corner(corner_pos)
        if final_rect.width() == 0:
            set_width(MIN_NONZERO)
        if final_rect.height() == 0:
            set_height(MIN_NONZERO)
        if QApplication.keyboardModifiers() == Qt.KeyboardModifier.ControlModifier and not initial_rect.isEmpty():
            aspect_ratio = final_rect.width() / final_rect.height()
            # Adjust target ratio based on existing transformation:
            scene_ratio_pt = QPointF(self._initial_aspect_ratio, 1.0)
            scene_ratio_pt = self.mapFromScene(scene_ratio_pt)
            target_ratio = scene_ratio_pt.x() / scene_ratio_pt.y()
            if aspect_ratio > target_ratio:  # reduce width
                target_width = target_ratio * final_rect.height()
                set_width(target_width)
            elif aspect_ratio < target_ratio:  # reduce height
                target_height = final_rect.width() / target_ratio
                set_height(target_height)
        scale = QGraphicsScale()
        scale.setOrigin(QVector3D(get_fixed_corner()))
        scale.setYScale(final_rect.height() / initial_rect.height())
        scale.setXScale(final_rect.width() / initial_rect.width())
        self._add_transform(scale)

    def setRect(self, rect: QRectF) -> None:
        """Adjust the origin and corner handles when the outline bounds change."""
        super().setRect(rect)
        self._initial_aspect_ratio = 0 if rect.height() == 0 else rect.width() / rect.height()
        self._update_handles()
        self._send_transform_signal()

    def clearTransformations(self) -> None:
        """Remove all transformations."""
        super().setTransform(QTransform())
        super().setTransformations([])
        self._send_transform_signal()

    def setTransformations(self, transformations: List[QGraphicsTransform]) -> None:
        """Update listeners when transformations change."""
        super().setTransformations(transformations)
        self._send_transform_signal()

    def setTransform(self, matrix: QTransform, combine: bool = False) -> None:
        """Update listeners when transformations change."""
        super().setTransform(matrix, combine)
        self._send_transform_signal()
    def _corner_points_in_scene(self) -> Generator[QPointF | QPointF, Any, None]:
        bounds = self.rect()
        corners = (self.mapToScene(pt) for pt in (bounds.topLeft(), bounds.topRight(),
                                                  bounds.bottomLeft(), bounds.bottomRight()))
        return corners

    def _add_transform(self, transform: QGraphicsTransform) -> None:
        transformations = self.transformations()
        transformations.append(transform)
        self.setTransformations(transformations)

    def _update_handles(self) -> None:
        """Keep the corners and origin positioned and sized correctly as the rectangle transforms."""
        bounds = self.rect()
        for handle_id, point in ((TL_HANDLE_ID, bounds.topLeft()), (TR_HANDLE_ID, bounds.topRight()),
                                 (BL_HANDLE_ID, bounds.bottomLeft()), (BR_HANDLE_ID, bounds.bottomRight())):
            handle_rect = _get_handle_rect(point)
            self._handles[handle_id].prepareGeometryChange()
            self._handles[handle_id].setRect(handle_rect)
        origin_x = bounds.x() + bounds.width() * self._fractional_origin.x()
        origin_y = bounds.y() + bounds.height() * self._fractional_origin.y()
        self._handles[ORIGIN_HANDLE_ID].prepareGeometryChange()
        self._handles[ORIGIN_HANDLE_ID].setRect(_get_handle_rect(QPointF(origin_x, origin_y)))

    def _send_transform_signal(self) -> None:
        offset = self.offset
        scale_x, scale_y = self.scale
        rotation = self.rotation
        self.transform_changed.emit(offset, scale_x, scale_y, rotation)

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


    def boundingRect(self) -> QRectF:
        rect = self.mapRectToScene(super().rect())
        if rect.width() < 1:
            rect.adjust(-1.0, 0.0, 1.0, 0.0)
        if rect.height() < 1:
            rect.adjust(0.0, -1.0, 0.0, 1.0)
        return self.mapRectFromScene(rect)

    def setRect(self, rect: QRectF) -> None:
        """Adjust the origin and corner handles when the outline bounds change."""
        if rect.width() == 0:
            rect.setWidth(0.01)
        if rect.height() == 0:
            rect.setHeight(0.01)
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
            arrow_pixmap = self._arrow_icon.pixmap(rect.size().toSize())
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
        print(self._handle_id)
        self._update_and_send_pos(event.pos())
        self.setSelected(False)


def _get_handle_rect(pos: QPointF) -> QRectF:
    return QRectF(pos - QPointF(HANDLE_SIZE / 2, HANDLE_SIZE / 2), QSizeF(HANDLE_SIZE, HANDLE_SIZE))
