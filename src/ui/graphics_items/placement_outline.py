"""Adjusts a rectangle's size and scale after transformations are applied."""
from typing import Optional, Dict, Iterable

from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QSizeF
from PySide6.QtGui import QPainter, QPen, QTransform, QPainterPath
from PySide6.QtWidgets import QWidget, QGraphicsItem, QStyleOptionGraphicsItem, \
    QGraphicsSceneMouseEvent, QGraphicsTransform, \
    QGraphicsObject

from src.ui.graphics_items.transform_handle import TransformHandle
from src.util.geometry_utils import extract_transform_parameters, combine_transform_parameters
from src.util.graphics_scene_utils import get_view_bounds_of_scene_item_rect, map_scene_item_point_to_view_point, \
    get_scene_item_bounds_of_view_rect, get_view

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
        self._size = QSizeF(size)
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
        x_off, y_off, _, _, _, = extract_transform_parameters(self.transform())
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
        _, _, x_scale, y_scale, angle = extract_transform_parameters(self.transform())
        self.setTransform(combine_transform_parameters(new_offset.x(), new_offset.y(), x_scale, y_scale, angle))

    @property
    def outline_size(self) -> QSizeF:
        """Accesses the outline's size in local coordinates."""
        return QSizeF(self._size)

    @outline_size.setter
    def outline_size(self, new_size: QSizeF) -> None:
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

    def move_corner(self, corner_id: str, scene_pos: QPointF, last_scene_pos: QPointF) -> None:
        """Move one of the corners, leaving the position of the opposite corner unchanged."""
        print('TODO: fix corners')

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
        bounds = QRectF(QPointF(), self._size)
        for handle_id, point in ((TL_HANDLE_ID, bounds.topLeft()), (TR_HANDLE_ID, bounds.topRight()),
                                 (BL_HANDLE_ID, bounds.bottomLeft()), (BR_HANDLE_ID, bounds.bottomRight())):
            self._handles[handle_id].move_rect_center(point)


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

