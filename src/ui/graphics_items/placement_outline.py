"""Adjusts a rectangle's size and scale after transformations are applied."""
from typing import Optional, Dict, Iterable

from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QSizeF
from PySide6.QtGui import QPainter, QPen, QTransform, QPainterPath
from PySide6.QtWidgets import QWidget, QGraphicsItem, QStyleOptionGraphicsItem, \
    QGraphicsSceneMouseEvent, QGraphicsTransform, \
    QGraphicsObject

from src.ui.graphics_items.transform_handle import TransformHandle
from src.util.geometry_utils import combine_transform_parameters, closest_size_keeping_aspect_ratio
from src.util.graphics_scene_utils import get_view_bounds_of_scene_item_rect, map_scene_item_point_to_view_point, \
    get_scene_item_bounds_of_view_rect, get_view
from src.util.math_utils import clamp, avoiding_zero
from src.util.shared_constants import MIN_NONZERO, FLOAT_MIN, FLOAT_MAX

MIN_SCENE_DIM = 5

TL_HANDLE_ID = 'top left'
TR_HANDLE_ID = 'top right'
BL_HANDLE_ID = 'bottom left'
BR_HANDLE_ID = 'bottom right'

LINE_COLOR = Qt.GlobalColor.black
LINE_WIDTH = 3


class PlacementOutline(QGraphicsObject):
    """Adjusts a rectangle's size and position after transformations are applied."""

    placement_changed = Signal(QPointF, QSizeF)

    def __init__(self, offset: QPointF, size: QSizeF) -> None:
        super().__init__()

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._handles: Dict[str, _Handle] = {}
        self._size = QSizeF(avoiding_zero(size.width()), avoiding_zero(size.height()))
        self._aspect_ratio = 1.0
        self._preserve_aspect_ratio = False
        self._pen = QPen(LINE_COLOR, LINE_WIDTH)
        self._pen.setCosmetic(True)
        self._offset = offset
        super().setTransform(combine_transform_parameters(offset.x(), offset.y(), 1.0, 1.0, 0.0))

        for handle_id in (TL_HANDLE_ID, TR_HANDLE_ID, BL_HANDLE_ID, BR_HANDLE_ID):
            self._handles[handle_id] = _Handle(self, handle_id)

    def setTransform(self, matrix: QTransform, combine: bool = False) -> None:
        """Store the offset when updating the transform."""
        super().setTransform(matrix, combine)
        x_off = self.transform().dx()
        y_off = self.transform().dy()
        if x_off != self._offset.x() or y_off != self._offset.y():
            self._offset = QPointF(x_off, y_off)
        self._update_handles()

    def setTransformations(self, transformations: Iterable[QGraphicsTransform]) -> None:
        """Block alternate graphics transformations, they aren't useful here, and they'll break other calculations."""
        raise RuntimeError('Do not use setTransformations with TransformOutline.')

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

    @property
    def offset(self) -> QPointF:
        """Returns the offset from the transformation and rect position combined."""
        return QPointF(self._offset)

    @offset.setter
    def offset(self, new_offset: QPointF) -> None:
        self.setTransform(self.transform() * QTransform.fromTranslate(new_offset.x() - self._offset.x(),
                                                                      new_offset.y() - self._offset.y()))

    @property
    def outline_size(self) -> QSizeF:
        """Accesses the outline's size in local coordinates."""
        return QSizeF(self._size)

    @outline_size.setter
    def outline_size(self, new_size: QSizeF) -> None:
        new_size.setWidth(avoiding_zero(new_size.width()))
        new_size.setHeight(avoiding_zero(new_size.height()))
        if self.preserve_aspect_ratio:
            new_size = closest_size_keeping_aspect_ratio(new_size, self._aspect_ratio)
        else:
            self._aspect_ratio = new_size.width() / new_size.height()
        self._size = QSizeF(new_size)
        self._update_handles()

    def mousePressEvent(self, event: Optional[QGraphicsSceneMouseEvent]) -> None:
        """Start dragging the outline."""
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

    def mouseMoveEvent(self, event: Optional[QGraphicsSceneMouseEvent]) -> None:
        """Translate the outline, following the cursor."""
        assert event is not None
        super().mouseMoveEvent(event)
        for handle in self._handles.values():
            if handle.isSelected():
                handle.mouseMoveEvent(event)
                return
        if event.scenePos() != event.lastScenePos():
            self.offset = self.offset + QPointF(event.scenePos() - event.lastScenePos())
            self.placement_changed.emit(self.offset, self.outline_size)

    def mouseReleaseEvent(self, event: Optional[QGraphicsSceneMouseEvent]) -> None:
        """Stop dragging the outline."""
        assert event is not None
        super().mouseReleaseEvent(event)
        for handle in self._handles.values():
            if handle.isSelected():
                handle.mouseReleaseEvent(event)
        self.setSelected(False)

    def _get_local_rect(self) -> QRectF:
        return QRectF(QPointF(), self._size)

    def _set_local_rect(self, new_rect: QRectF) -> None:
        assert new_rect.width() > 0 and new_rect.height() > 0
        if new_rect.topLeft() == self._offset and new_rect.size() == self._size:
            return
        if new_rect.topLeft() != self._offset:
            self.offset = new_rect.topLeft()
        if new_rect.size() != self._size:
            self.outline_size = new_rect.size()
        self._update_handles()
        self.placement_changed.emit(self.offset, self.outline_size)

    def move_corner(self, corner_id: str, scene_pos: QPointF, _) -> None:
        """Move one of the corners, leaving the position of the opposite corner unchanged."""
        local_pos = self.mapFromScene(scene_pos)
        local_rect = self._get_local_rect()

        # update offset based on scene coordinates:
        offset_change_vector = scene_pos - self._handles[corner_id].scene_pos()
        transform_at_origin = self.transform() * QTransform.fromTranslate(-self._offset.x(), -self._offset.y())
        inverse_transform_at_origin = transform_at_origin.inverted()[0]

        scene_offset_change_vector = inverse_transform_at_origin.map(offset_change_vector)
        x_off_min = 0.0 if corner_id in (TR_HANDLE_ID, BR_HANDLE_ID) else FLOAT_MIN
        x_off_max = 0.0 if corner_id in (TR_HANDLE_ID, BR_HANDLE_ID) else (local_rect.width() - MIN_NONZERO)
        y_off_min = 0.0 if corner_id in (BL_HANDLE_ID, BR_HANDLE_ID) else FLOAT_MIN
        y_off_max = 0.0 if corner_id in (BL_HANDLE_ID, BR_HANDLE_ID) else (local_rect.height() - MIN_NONZERO)

        scene_offset_change_vector.setX(clamp(scene_offset_change_vector.x(), x_off_min, x_off_max))
        scene_offset_change_vector.setY(clamp(scene_offset_change_vector.y(), y_off_min, y_off_max))
        offset = self._offset + transform_at_origin.map(scene_offset_change_vector)

        # update size using local coordinates:
        x_min = MIN_NONZERO if corner_id in (TR_HANDLE_ID, BR_HANDLE_ID) else FLOAT_MIN
        x_max = FLOAT_MAX if corner_id in (TR_HANDLE_ID, BR_HANDLE_ID) else self._size.width() - MIN_NONZERO
        y_min = MIN_NONZERO if corner_id in (BL_HANDLE_ID, BR_HANDLE_ID) else FLOAT_MIN
        y_max = FLOAT_MAX if corner_id in (BL_HANDLE_ID, BR_HANDLE_ID) else self._size.height() - MIN_NONZERO
        local_pos.setX(clamp(local_pos.x(), x_min, x_max))
        local_pos.setY(clamp(local_pos.y(), y_min, y_max))
        if corner_id == TL_HANDLE_ID:
            local_rect.setTopLeft(local_pos)
        elif corner_id == TR_HANDLE_ID:
            local_rect.setTopRight(local_pos)
        elif corner_id == BL_HANDLE_ID:
            local_rect.setBottomLeft(local_pos)
        elif corner_id == BR_HANDLE_ID:
            local_rect.setBottomRight(local_pos)
        local_rect.moveTopLeft(offset)

        self._set_local_rect(local_rect)

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draw a simple rectangle."""
        assert painter is not None
        painter.save()
        painter.setPen(self._pen)
        painter.drawRect(QRectF(QPointF(), self._size))
        painter.restore()

    def boundingRect(self) -> QRectF:
        """Set bounding rect to the scene item size, preserving minimums so that mouse input still works at small
           scales."""
        if self.scene() is None:
            return self._get_local_rect()
        rect = get_view_bounds_of_scene_item_rect(QRectF(QPointF(), self._size), self)
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

    def _update_handles(self) -> None:
        """Keep the corners and origin positioned and sized correctly as the rectangle transforms."""
        bounds = self._get_local_rect()
        for handle_id, point in ((TL_HANDLE_ID, bounds.topLeft()), (TR_HANDLE_ID, bounds.topRight()),
                                 (BL_HANDLE_ID, bounds.bottomLeft()), (BR_HANDLE_ID, bounds.bottomRight())):
            handle_pos = self._handles[handle_id].mapFromScene(self.mapToScene(point))
            self._handles[handle_id].move_rect_center(handle_pos)


class _Handle(TransformHandle):
    """Small square the user can drag to adjust the item properties."""

    def __init__(self, parent: PlacementOutline, handle_id: str) -> None:
        base_angle = 0
        if handle_id == TL_HANDLE_ID:
            base_angle = 225
        elif handle_id == TR_HANDLE_ID:
            base_angle = 315
        elif handle_id == BR_HANDLE_ID:
            base_angle = 45
        elif handle_id == BL_HANDLE_ID:
            base_angle = 135
        super().__init__(parent, handle_id, base_angle, True)
        self.dragged.connect(parent.move_corner)

