"""Editable path item used to create a polygon."""
from typing import List, Optional

from PySide6.QtCore import QPointF, QRectF, QLineF, Signal
from PySide6.QtGui import QPainterPath, QPolygonF, QPainter
from PySide6.QtWidgets import QGraphicsScene, QStyleOptionGraphicsItem, QWidget

from src.ui.graphics_items.animated_dash_item import AnimatedDashItem
from src.ui.graphics_items.transform_handle import TransformHandle
from src.undo_stack import UndoStack

PEN_WIDTH = 4


class PathCreationItem(AnimatedDashItem):
    """Editable path item used to create a polygon."""

    first_handle_clicked = Signal()

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__()
        self._points: List[QPointF] = []
        self._handles: List[TransformHandle] = []
        scene.addItem(self)
        self.animated = True

    @property
    def count(self) -> int:
        """Returns the number of points in the polygon."""
        return len(self._points)

    def _create_handle(self, point: QPointF) -> TransformHandle:
        handle = TransformHandle(self, str(len(self._handles)), draw_arrows=False)
        handle.setZValue(self.zValue() + 1)
        handle.move_rect_center(point)
        handle.drawn_angle = 45
        return handle

    def _add_handle(self, point: QPointF, handle: Optional[TransformHandle] = None) -> None:
        if handle is None:
            handle = self._create_handle(point)
        scene = self.scene()
        assert scene is not None
        self.prepareGeometryChange()
        self._points.append(point)
        self._handles.append(handle)
        if len(self._handles) == 1:
            handle.clicked.connect(lambda id_str, pt: self.first_handle_clicked.emit())
        handle.dragged.connect(self._move_handle_on_drag)
        if handle.scene() is None:
            scene.addItem(handle)
        handle.setVisible(True)
        self.update()

    def _remove_handle(self, idx: int) -> None:
        assert 0 <= idx < len(self._handles)
        handle = self._handles[idx]
        point = self._points[idx]
        handle.dragged.disconnect(self._move_handle_on_drag)
        self.prepareGeometryChange()
        self._handles.remove(handle)
        self._points.remove(point)
        scene = self.scene()
        assert scene is not None
        scene.removeItem(handle)
        handle.setVisible(False)
        self.update()

    def add_point(self, point: QPointF) -> None:
        """Adds a new point to the path, saving the change to the undo history."""
        added_point = QPointF(point)
        added_handle = self._create_handle(added_point)

        def _add_handle(handle=added_handle, pt=added_point) -> None:
            self._add_handle(pt, handle)

        def _remove_handle() -> None:
            if len(self._handles) > 0:
                idx = self.count - 1
                self._remove_handle(idx)
        UndoStack().commit_action(_add_handle, _remove_handle, 'PathCreationItem.add_point')

    def clear_points(self) -> None:
        """Removes all points, saving the change to the undo history."""
        point_list = [QPointF(pt) for pt in self._points]
        scene = self.scene()
        assert scene is not None

        def _clear() -> None:
            while self.count > 0:
                self._remove_handle(self.count - 1)

        def _restore() -> None:
            for point in point_list:
                self._add_handle(point)
        UndoStack().commit_action(_clear, _restore, 'PathCreationItem.clear_points')

    def last_point(self) -> Optional[QPointF]:
        """Returns the last point in the list"""
        if len(self._points) == 0:
            return None
        return QPointF(self._points[-1])

    def get_point_index(self, pos: QPointF) -> Optional[int]:
        """Return the index of the point at pos, or None if no point is at that location."""
        for i, handle in enumerate(self._handles):
            if handle.boundingRect().contains(pos):
                return i
        return None

    def _move_handle_on_drag(self, handle_id: str, drag_pos: QPointF, _) -> None:
        self.prepareGeometryChange()
        idx = int(handle_id)
        self._points[idx] = QPointF(drag_pos)
        self._handles[idx].move_rect_center(drag_pos)
        self.update()

    def get_path(self) -> Optional[QPolygonF]:
        """Returns the path formed by all handles."""
        if len(self._points) < 3:
            return None
        return QPolygonF(self._points)

    def boundingRect(self) -> QRectF:
        """Sse the union of all handle bounds as the bounding rect."""
        bounds = QRectF()
        for handle in self._handles:
            bounds = bounds.united(handle.boundingRect())
        return bounds

    def shape(self) -> QPainterPath:
        """Returns the outline's bounds as a shape."""
        path = QPainterPath()
        last_handle: Optional[TransformHandle] = None
        for handle in self._handles:
            if last_handle is not None:
                p1 = last_handle.boundingRect().center()
                p2 = handle.boundingRect().center()
                line = QLineF(p1, p2)
                perpendicular = QPointF(line.dx(), line.dy())
                length = (perpendicular.x() ** 2 + perpendicular.y() ** 2) ** 0.5
                perpendicular /= length
                offset = perpendicular * (PEN_WIDTH / 2)
                path.addPolygon(QPolygonF([p1 + offset, p1 - offset, p2 - offset, p2 + offset]))
            path.addRect(handle.boundingRect())
            last_handle = handle
        return path

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """Draw animated dotted lines between all handles."""
        assert painter is not None
        painter.save()
        pen = self.get_pen()
        pen.setWidth(PEN_WIDTH)
        painter.setPen(pen)
        last_point: Optional[QPointF] = None
        for point in self._points:
            if last_point is not None:
                painter.drawLine(last_point, point)
            last_point = point
        painter.restore()
