"""Draggable GraphicsItem used to reposition scene elements."""
import math
from typing import Optional, Tuple

from PySide6.QtGui import QIcon, QPainterPath, QPainter
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget, QGraphicsSceneMouseEvent, \
    QGraphicsObject
from PySide6.QtCore import QRectF, Qt, QPointF, QSizeF, QLineF, Signal

from src.util.geometry_utils import extract_transform_parameters
from src.util.graphics_scene_utils import map_scene_item_point_to_view_point, get_scene_item_bounds_of_view_rect
from src.util.shared_constants import MIN_NONZERO, PROJECT_DIR

CORNER_SCALE_ARROW_FILE = f'{PROJECT_DIR}/resources/arrow_corner.svg'
CORNER_ROTATE_ARROW_FILE = f'{PROJECT_DIR}/resources/arrow_corner_rot.svg'

TRANSFORM_MODE_SCALE = 'scale'
TRANSFORM_MODE_ROTATE = 'rotate'
HANDLE_SIZE = 20
MIN_SCENE_DIM = 5


class TransformHandle(QGraphicsObject):
    """Small square the user can drag to adjust the item properties."""

    dragged = Signal(str, QPointF)

    def __init__(self, parent: QGraphicsItem, handle_id: str, base_angle: int = 0, draw_arrows: bool = True) -> None:
        super().__init__(parent)
        self.setZValue(parent.zValue() + 2)
        self._draw_arrows = draw_arrows
        self._base_angle = base_angle
        self._handle_id = handle_id
        self.setToolTip(handle_id)
        self._last_pos = None
        self._parent = parent
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._brush = Qt.GlobalColor.black
        self._pen = Qt.GlobalColor.white
        self._rect = QRectF()
        self._arrow_icon = QIcon(CORNER_SCALE_ARROW_FILE)
        self._rot_arrow_icon = QIcon(CORNER_ROTATE_ARROW_FILE)
        self._saved_bounds = None
        self._saved_arrow_bounds = None
        self._icon = self._arrow_icon

    def rect(self) -> QRectF:
        """Gets the handle's rough placement in local coordinates"""
        return self._rect

    def setRect(self, rect: QRectF) -> None:
        """Sets the handle's rough placement in local coordinates"""
        self.prepareGeometryChange()
        if rect.width() < MIN_NONZERO:
            rect.setWidth(MIN_NONZERO)
        if rect.height() < MIN_NONZERO:
            rect.setHeight(MIN_NONZERO)
        self._rect = rect

    def move_rect_center(self, center: QPointF) -> None:
        """Moves the handle rectangle so that it is centered on a given point in local coordinates."""
        self.setRect(_get_handle_rect(center))

    def set_mode_icon(self, mode: str) -> None:
        """Sets the appropriate icon for the given mode."""
        if mode == TRANSFORM_MODE_ROTATE:
            self._icon = self._rot_arrow_icon
        elif mode == TRANSFORM_MODE_SCALE:
            self._icon = self._arrow_icon
        else:
            raise ValueError(f'Invalid mode {mode}')
        self.update()

    def boundingRect(self) -> QRectF:
        """Ensure handle bounds within the scene are large enough for the handle to remain clickable within extreme
           transforms."""
        bounds = self._adjusted_bounds()
        return bounds.united(self._arrow_bounds(bounds))

    def shape(self) -> QPainterPath:
        """Returns the outline's bounds as a shape."""
        path = QPainterPath()
        bounds = self._adjusted_bounds()
        path.addRect(QRectF(bounds))
        path.addRect(QRectF(self._arrow_bounds(bounds)))
        return path

    def _get_parent_transform_params(self) -> Tuple[float, float, float]:
        _, _, scale_x, scale_y, angle = extract_transform_parameters(self._parent.transform(),
                                                                     self._parent.boundingRect().center())
        return scale_x, scale_y, angle

    def paint(self,
              painter: Optional[QPainter],
              unused_option: Optional[QStyleOptionGraphicsItem],
              unused_widget: Optional[QWidget] = None) -> None:
        """When painting, ignore all transformations besides center point translation."""
        assert painter is not None
        painter.save()
        transform = painter.transform()
        inverse = transform.inverted()[0]
        painter.setTransform(inverse, True)
        pos = transform.map(self.rect().center())
        painter.translate(pos)
        rect = _get_handle_rect(QPointF())
        painter.fillRect(rect, self._brush)
        painter.setPen(self._pen)
        painter.drawRect(rect)

        if self._draw_arrows and self.parentItem() is not None:
            arrow_pixmap = self._icon.pixmap(rect.size().toSize())
            arrow_bounds = QRectF(rect.topLeft() - QPointF(rect.width(), rect.height()), rect.size())
            # get base rotation:

            scale_x, scale_y, angle = self._get_parent_transform_params()
            if scale_x < 0 or scale_y < 0:
                angle *= -1
                angle += -(self._base_angle + 135) + (90 if scale_x < 0 else 270)
            else:
                angle += 135 + self._base_angle
            painter.rotate(angle)
            painter.drawPixmap(arrow_bounds.toAlignedRect(), arrow_pixmap)
        painter.restore()

    def _adjusted_bounds(self) -> QRectF:
        """Ensure that bounds within the scene don't go beneath a given size, regardless of the transformation."""
        view_pos = map_scene_item_point_to_view_point(self._rect.center(), self)
        view_rect = _get_handle_rect(view_pos)
        if view_rect.width() < MIN_SCENE_DIM:
            view_rect.adjust(-(MIN_SCENE_DIM - view_rect.width()) / 2, 0.0, (MIN_SCENE_DIM - view_rect.width()) / 2,
                             0.0)
        if view_rect.height() < MIN_SCENE_DIM:
            view_rect.adjust(0.0, -(MIN_SCENE_DIM - view_rect.height()) / 2, 0.0,
                             (MIN_SCENE_DIM - view_rect.height()) / 2)
        adjusted_rect = get_scene_item_bounds_of_view_rect(view_rect, self)
        return adjusted_rect

    def _arrow_bounds(self, adjusted_bounds: Optional[QRectF] = None) -> QRectF:
        if adjusted_bounds is None:
            adjusted_bounds = self._adjusted_bounds()
        radius = math.sqrt(adjusted_bounds.width()**2 + adjusted_bounds.height()**2)
        offset_vector = QLineF(0, 0, radius, 0)
        offset_vector.setAngle(-self._base_angle)
        return adjusted_bounds.translated(offset_vector.p2().x(), offset_vector.p2().y())

    def _update_and_send_pos(self, pos: QPointF) -> None:
        self.dragged.emit(self._handle_id, pos)

    def mousePressEvent(self, event: Optional[QGraphicsSceneMouseEvent]) -> None:
        """Select the clicked handle, start sending handle position changes."""
        assert event is not None
        super().mousePressEvent(event)
        self.setSelected(True)
        self._update_and_send_pos(event.pos())

    def mouseMoveEvent(self, event: Optional[QGraphicsSceneMouseEvent]) -> None:
        """Continue sending handle position changes."""
        assert event is not None
        self._update_and_send_pos(event.pos())

    def mouseReleaseEvent(self, event: Optional[QGraphicsSceneMouseEvent]) -> None:
        """Send the final handle position change to the transformation outline, and de-select the handle."""
        assert event is not None
        self._update_and_send_pos(event.pos())
        self.setSelected(False)


def _get_handle_rect(pos: QPointF) -> QRectF:
    return QRectF(pos - QPointF(HANDLE_SIZE / 2, HANDLE_SIZE / 2), QSizeF(HANDLE_SIZE, HANDLE_SIZE))


