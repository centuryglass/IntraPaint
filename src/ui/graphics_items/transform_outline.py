"""Draws the transform tool's outline with corner, edge and origin handles, and turns drags on them into intents."""
from typing import Optional, Iterable

from PySide6.QtCore import Qt, QRectF, QPointF, QLineF, Signal
from PySide6.QtGui import QPainter, QPen, QTransform, QPainterPath
from PySide6.QtWidgets import QWidget, QGraphicsItem, QStyleOptionGraphicsItem, \
    QGraphicsSceneMouseEvent, QGraphicsTransform, \
    QGraphicsObject

from src.tools.layer_transform_state import TransformState
from src.ui.graphics_items.transform_handle import (TransformHandle, TRANSFORM_MODE_SCALE, TRANSFORM_MODE_ROTATE,
                                                   IMAGE_PATH_CORNER_SCALE_ARROW, IMAGE_PATH_CORNER_ROTATE_ARROW,
                                                   IMAGE_PATH_EDGE_SCALE_ARROW, IMAGE_PATH_EDGE_SKEW_ARROW)
from src.undo_stack import UndoStack, UndoStackRef
from src.util.math_utils import clamp
from src.util.visual.graphics_scene_utils import (get_view_bounds_of_scene_item_rect,
                                                  map_scene_item_point_to_view_point,
                                                  get_scene_item_bounds_of_view_rect, get_view)

MIN_SCENE_DIM = 5

ORIGIN_HANDLE_ID = 'transformation origin'
# Dragging the origin handle within this many view pixels of a corner, edge midpoint or the center snaps to it:
ORIGIN_SNAP_DISTANCE = 10
TL_HANDLE_ID = 'top left'
TR_HANDLE_ID = 'top right'
BL_HANDLE_ID = 'bottom left'
BR_HANDLE_ID = 'bottom right'
CORNER_HANDLE_IDS = (TL_HANDLE_ID, TR_HANDLE_ID, BL_HANDLE_ID, BR_HANDLE_ID)
TOP_HANDLE_ID = 'top'
BOTTOM_HANDLE_ID = 'bottom'
LEFT_HANDLE_ID = 'left'
RIGHT_HANDLE_ID = 'right'
EDGE_HANDLE_IDS = (TOP_HANDLE_ID, BOTTOM_HANDLE_ID, LEFT_HANDLE_ID, RIGHT_HANDLE_ID)

# The direction each handle's arrow points away from the rectangle, in degrees clockwise from the +x axis:
_ARROW_ANGLES = {
    TL_HANDLE_ID: 225, TR_HANDLE_ID: 315, BR_HANDLE_ID: 45, BL_HANDLE_ID: 135,
    TOP_HANDLE_ID: 270, RIGHT_HANDLE_ID: 0, BOTTOM_HANDLE_ID: 90, LEFT_HANDLE_ID: 180
}

LINE_COLOR = Qt.GlobalColor.black
LINE_WIDTH = 3


def corner_point(rect: QRectF, handle_id: str) -> QPointF:
    """Returns the corner of rect that a corner handle sits on."""
    corners = {
        TL_HANDLE_ID: rect.topLeft,
        TR_HANDLE_ID: rect.topRight,
        BL_HANDLE_ID: rect.bottomLeft,
        BR_HANDLE_ID: rect.bottomRight
    }
    assert handle_id in corners, f'Invalid corner ID {handle_id}'
    return corners[handle_id]()


def edge_point(rect: QRectF, handle_id: str) -> QPointF:
    """Returns the midpoint of the edge of rect that an edge handle sits on."""
    center = rect.center()
    edges = {
        TOP_HANDLE_ID: QPointF(center.x(), rect.top()),
        BOTTOM_HANDLE_ID: QPointF(center.x(), rect.bottom()),
        LEFT_HANDLE_ID: QPointF(rect.left(), center.y()),
        RIGHT_HANDLE_ID: QPointF(rect.right(), center.y())
    }
    assert handle_id in edges, f'Invalid edge ID {handle_id}'
    return edges[handle_id]


class TransformOutline(QGraphicsObject):
    """A view of the transform tool's `TransformState`: a rectangle with corner, edge midpoint and origin handles.

    The outline changes nothing itself. `set_state` draws a state, and mouse input becomes intents that its owner
    turns into a new state:
    - A drag anywhere off the handles sends `moved` with each step's scene delta.
    - A corner or edge handle drag sends `handle_dragged` with the cursor's scene position. The owner reads `mode`:
      corners scale or rotate, and edges scale one axis or skew.
    - An origin handle drag sends `origin_dragged` with the origin's new point in untransformed coordinates, snapped
      to the rectangle's corners, edge midpoints and center, and clamped to the rectangle.
    Double-clicking switches `mode` between scale and rotate. Presses, moves and releases on a handle reach the
    outline's own mouse handlers, which pass them to the handle, so every drag is one undo gesture between
    `drag_started` and `drag_finished`. A press near several handles goes to the nearest one.
    """

    moved = Signal(float, float)
    handle_dragged = Signal(str, QPointF)
    origin_dragged = Signal(QPointF)
    # Emitted when a mouse drag on the outline or its handles starts and ends. drag_finished is emitted before the
    # undo gesture closes, so changes made in response join the drag's undo entry.
    drag_started = Signal()
    drag_finished = Signal()

    def __init__(self, undo_stack: UndoStack) -> None:
        super().__init__()
        self._undo_stack = UndoStackRef(undo_stack)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._handles: dict[str, _Handle] = {}
        self._rect = QRectF()
        self._origin = QPointF()
        self._state: Optional[TransformState] = None
        self._pen = QPen(LINE_COLOR, LINE_WIDTH)
        self._pen.setCosmetic(True)
        self._mode = TRANSFORM_MODE_SCALE
        for handle_id in (*CORNER_HANDLE_IDS, *EDGE_HANDLE_IDS, ORIGIN_HANDLE_ID):
            self._handles[handle_id] = _Handle(self, handle_id)
        self._handles[ORIGIN_HANDLE_ID].drawn_angle = 45
        self._update_handles()

    @property
    def state(self) -> Optional[TransformState]:
        """The state last drawn, or None while the outline shows a transform the fields can't express."""
        return self._state

    @property
    def mode(self) -> str:
        """Whether handle drags scale (TRANSFORM_MODE_SCALE), or rotate and skew (TRANSFORM_MODE_ROTATE)."""
        return self._mode

    @mode.setter
    def mode(self, mode: str) -> None:
        self._mode = mode
        for handle in self._handles.values():
            handle.set_mode_icon(mode)

    @property
    def transformation_origin(self) -> QPointF:
        """The origin handle's position in untransformed coordinates."""
        return QPointF(self._origin)

    def set_state(self, state: TransformState) -> None:
        """Draws a state."""
        self._state = state
        self._show(state.rect, state.matrix(), state.origin_local)

    def show_uneditable(self, rect: QRectF, matrix: QTransform) -> None:
        """Draws a rectangle under a transform the fields can't express, such as perspective. The owner disables the
           outline, so it takes no input."""
        self._state = None
        self._show(rect, matrix, QRectF(rect).center())

    def _show(self, rect: QRectF, matrix: QTransform, origin: QPointF) -> None:
        if rect != self._rect:
            self.prepareGeometryChange()
            self._rect = QRectF(rect)
        self._origin = QPointF(origin)
        super().setTransform(matrix, False)
        self._update_handles()

    def setTransform(self, matrix: QTransform, combine: bool = False) -> None:
        """Block direct transform changes: `set_state` makes them."""
        raise RuntimeError('Use set_state to change the TransformOutline transform.')

    def setTransformations(self, transformations: Iterable[QGraphicsTransform]) -> None:
        """Block alternate graphics transformations, they aren't useful here, and they'll break other calculations."""
        raise RuntimeError('Do not use setTransformations with TransformOutline.')

    def setZValue(self, z: float) -> None:
        """Ensure handle z-values stay in sync with the outline."""
        super().setZValue(z)
        for handle in self._handles.values():
            handle.setZValue(z - 2)

    def mousePressEvent(self, event: Optional[QGraphicsSceneMouseEvent]) -> None:
        """Start dragging the layer on a left press, and ignore other buttons.

        The item becomes the mouse grabber only for presses it accepts, so drag_started is sent only for a press whose
        release will send drag_finished."""
        assert event is not None
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        self._undo_stack().begin_gesture('TransformOutline.drag')
        self.drag_started.emit()
        handle = self._handle_near(event)
        if handle is not None:
            handle.setSelected(True)
            handle.press(event)
            return
        super().mousePressEvent(event)
        self.setSelected(True)

    def _handle_near(self, event: QGraphicsSceneMouseEvent) -> Optional['_Handle']:
        """Returns the nearest enabled handle within twice its width of a press in view pixels, or None.

        The range keeps handles pickable on layers transformed down to a few pixels, where they overlap."""
        view = get_view(self)
        click_pos = QPointF(view.mapFromGlobal(event.screenPos()))
        nearest: Optional[_Handle] = None
        nearest_distance = 0.0
        for handle in self._handles.values():
            if not handle.isVisible():
                continue
            handle_pos = map_scene_item_point_to_view_point(handle.rect().center(), handle)
            distance = (click_pos - handle_pos).manhattanLength()
            if distance < handle.rect().width() * 2 and (nearest is None or distance < nearest_distance):
                nearest, nearest_distance = handle, distance
        return nearest

    def mouseDoubleClickEvent(self, event: Optional[QGraphicsSceneMouseEvent]) -> None:
        """Switch handle drags between scaling, and rotating and skewing."""
        assert event is not None
        self.mode = TRANSFORM_MODE_ROTATE if self._mode == TRANSFORM_MODE_SCALE else TRANSFORM_MODE_SCALE

    def mouseMoveEvent(self, event: Optional[QGraphicsSceneMouseEvent]) -> None:
        """Send a move intent following the cursor, or pass the event to a dragged handle."""
        assert event is not None
        super().mouseMoveEvent(event)
        for handle in self._handles.values():
            if handle.isSelected():
                handle.move(event)
                return
        change = QPointF(event.scenePos() - event.lastScenePos())
        if change != QPointF():
            self.moved.emit(change.x(), change.y())

    def mouseReleaseEvent(self, event: Optional[QGraphicsSceneMouseEvent]) -> None:
        """Stop dragging the layer."""
        assert event is not None
        super().mouseReleaseEvent(event)
        for handle in self._handles.values():
            if handle.isSelected():
                handle.release(event)
        self.setSelected(False)
        self.drag_finished.emit()
        self._undo_stack().end_gesture()

    def move_transformation_handle(self, handle_id: str, pos: QPointF) -> None:
        """Sends the intent for a handle dragged to a scene position."""
        assert handle_id in self._handles, str(self._handles)
        if handle_id == ORIGIN_HANDLE_ID:
            local_pos = self.mapFromScene(pos)
            assert isinstance(local_pos, QPointF)
            local_pos = self._snapped_origin(local_pos)
            rect = self._rect
            self.origin_dragged.emit(QPointF(clamp(local_pos.x(), rect.left(), rect.right()),
                                             clamp(local_pos.y(), rect.top(), rect.bottom())))
        elif handle_id in CORNER_HANDLE_IDS or handle_id in EDGE_HANDLE_IDS:
            self.handle_dragged.emit(handle_id, QPointF(pos))
        else:
            raise RuntimeError(f'Invalid handle id {handle_id}')

    def _snapped_origin(self, pos: QPointF) -> QPointF:
        """Returns the nearest of the four corners, four edge midpoints and the center if it is within
           ORIGIN_SNAP_DISTANCE view pixels of pos (in local coordinates), otherwise pos."""
        rect = self._rect
        cursor = map_scene_item_point_to_view_point(pos, self)
        best = pos
        best_distance = float(ORIGIN_SNAP_DISTANCE)
        for x in (rect.left(), rect.center().x(), rect.right()):
            for y in (rect.top(), rect.center().y(), rect.bottom()):
                target = QPointF(x, y)
                distance = QLineF(cursor, map_scene_item_point_to_view_point(target, self)).length()
                if distance <= best_distance:
                    best, best_distance = target, distance
        return best

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
        if self.scene() is None:
            return self.rect()
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
        return QRectF(self._rect)

    def _update_handles(self) -> None:
        """Keep the corners, edge midpoints and origin positioned on the rectangle."""
        for handle_id in CORNER_HANDLE_IDS:
            self._handles[handle_id].move_rect_center(corner_point(self._rect, handle_id))
        for handle_id in EDGE_HANDLE_IDS:
            self._handles[handle_id].move_rect_center(edge_point(self._rect, handle_id))
        self._handles[ORIGIN_HANDLE_ID].move_rect_center(self._origin)


class _Handle(TransformHandle):
    """Small square the user can drag to adjust the item properties."""

    def __init__(self, parent: TransformOutline, handle_id: str) -> None:
        if handle_id in EDGE_HANDLE_IDS:
            icons = (IMAGE_PATH_EDGE_SCALE_ARROW, IMAGE_PATH_EDGE_SKEW_ARROW)
        else:
            icons = (IMAGE_PATH_CORNER_SCALE_ARROW, IMAGE_PATH_CORNER_ROTATE_ARROW)
        super().__init__(parent, handle_id, _ARROW_ANGLES.get(handle_id, 0), handle_id != ORIGIN_HANDLE_ID, *icons)
        self.dragged.connect(parent.move_transformation_handle)

    def _outline(self) -> TransformOutline:
        parent = self.parentItem()
        assert isinstance(parent, TransformOutline)
        return parent

    def mousePressEvent(self, event: Optional[QGraphicsSceneMouseEvent]) -> None:
        """Passes the press to the outline, which starts the drag gesture and picks the handle to drag."""
        self._outline().mousePressEvent(event)

    def mouseMoveEvent(self, event: Optional[QGraphicsSceneMouseEvent]) -> None:
        """Passes the move to the outline, which drags the picked handle."""
        self._outline().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Optional[QGraphicsSceneMouseEvent]) -> None:
        """Passes the release to the outline, which ends the drag gesture."""
        self._outline().mouseReleaseEvent(event)

    def press(self, event: QGraphicsSceneMouseEvent) -> None:
        """Starts dragging this handle, for the outline."""
        super().mousePressEvent(event)

    def move(self, event: QGraphicsSceneMouseEvent) -> None:
        """Drags this handle, for the outline."""
        super().mouseMoveEvent(event)

    def release(self, event: QGraphicsSceneMouseEvent) -> None:
        """Finishes dragging this handle, for the outline."""
        super().mouseReleaseEvent(event)

    def _get_parent_transform_params(self) -> tuple[float, float, float]:
        parent = self._outline()
        state = parent.state
        if state is None:
            return 1.0, 1.0, 0.0
        return state.x_scale, state.y_scale, state.rotation
