"""Various utility functions for working with QGraphicsScene and QGraphicsView."""
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPolygonF
from PySide6.QtWidgets import QGraphicsItem, QGraphicsView


def get_view(item: QGraphicsItem) -> QGraphicsView:
    """Returns the first view associated with a graphics item, throwing an assertion error if the item isn't in a
       view."""
    scene = item.scene()
    assert scene is not None
    views = scene.views()
    assert len(views) > 0
    return views[0]


def map_scene_item_point_to_view_point(local_pt: QPointF, item: QGraphicsItem) -> QPointF:
    """Maps a point from scene item coordinates to view coordinates."""
    scene_pt = item.mapToScene(local_pt)
    view = get_view(item)
    return QPointF(view.mapFromScene(scene_pt))


def map_view_point_to_scene_item_point(view_pt: QPointF, item: QGraphicsItem) -> QPointF:
    """Map a point in view coordinates to the same point in a scene item's local coordinates."""
    view = get_view(item)
    scene_pt = QPointF(view.mapToScene(view_pt.toPoint()))
    return item.mapFromScene(scene_pt)


def get_view_bounds_of_scene_item_rect(local_rect: QRectF, item: QGraphicsItem) -> QRectF:
    """Returns a scene item rectangle's bounds in the view."""
    poly = QPolygonF()
    for corner in (map_scene_item_point_to_view_point(pt, item) for pt in (local_rect.topLeft(),
                                                                           local_rect.bottomLeft(),
                                                                           local_rect.topRight(),
                                                                           local_rect.bottomRight())):
        poly.append(corner)
    return poly.boundingRect()


def get_scene_item_bounds_of_view_rect(view_rect: QRectF, item: QGraphicsItem) -> QRectF:
    """Returns a view rectangle's bounds in a graphics scene item's coordinate."""
    poly = QPolygonF()
    for corner in (map_view_point_to_scene_item_point(pt, item) for pt in (view_rect.topLeft(),
                                                                           view_rect.bottomLeft(),
                                                                           view_rect.topRight(),
                                                                           view_rect.bottomRight())):
        poly.append(corner)
    return poly.boundingRect()


def get_scene_bounds_of_scene_item_rect(local_rect: QRectF, item: QGraphicsItem) -> QRectF:
    """Returns a scene item rectangle's bounds in the scene."""
    poly = QPolygonF()
    for corner in (item.mapToScene(pt) for pt in (local_rect.topLeft(), local_rect.bottomLeft(),
                                                  local_rect.topRight(), local_rect.bottomRight())):
        poly.append(corner)
    return poly.boundingRect()
