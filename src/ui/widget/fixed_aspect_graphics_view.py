"""A QGraphicsView that maintains an aspect ratio and simplifies scene management."""
from typing import Optional, List
from PyQt5.QtWidgets import QWidget, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QTransform, QResizeEvent, QMouseEvent, QCursor
from PyQt5.QtCore import Qt, QObject, QPoint, QPointF, QRect, QRectF, QSize, QMarginsF, pyqtSignal, QEvent
from src.ui.util.geometry_utils import get_scaled_placement
from src.ui.util.contrast_color import contrast_color
from src.util.validation import assert_type

CURSOR_ITEM_Z_LEVEL = 9999


class FixedAspectGraphicsView(QGraphicsView):
    """A QGraphicsView that maintains an aspect ratio and simplifies scene management."""

    scale_changed = pyqtSignal(float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene()
        self._content_size: QSize = QSize(0, 0)
        self._content_rect: Optional[QRect] = None
        self._background: Optional[QPixmap] = None
        self._event_filters: List[QObject] = []
        self._last_cursor_pos: Optional[QPoint] = None
        self._cursor_pixmap: Optional[QPixmap] = None
        self._cursor_pixmap_item: Optional[QGraphicsPixmapItem] = None

        self._scale = 1.0
        self._scale_adjustment = 0.0
        self._offset = QPointF(0.0, 0.0)

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setCacheMode(QGraphicsView.CacheBackground)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setScene(self._scene)

    def set_cursor(self, new_cursor: QCursor | QPixmap | None):
        """Sets the cursor over the scene, optionally with custom rendering for large cursors.

        Parameters
        ----------
        new_cursor: QCursor or QPixmap or None
            If a QCursor is given, the cursor will be applied normally.  If None is given, the default cursor will be
            applied. If a QPixmap is given, a cross cursor will be used, and the pixmap will be drawn over the
            last mouse coordinates, centered on the mouse pointer. This allows extra large cursors to be used, which
            can cause problems with some windowing systems if applied normally.
        """
        if isinstance(new_cursor, QPixmap):
            if self._cursor_pixmap_item is None:
                self._cursor_pixmap_item = QGraphicsPixmapItem(new_cursor)
                self._cursor_pixmap_item.setZValue(CURSOR_ITEM_Z_LEVEL)
            else:
                self._cursor_pixmap_item.setPixmap(new_cursor)
            if self._cursor_pixmap_item.scene() is None and self._last_cursor_pos is not None:
                self.scene().addItem(self._cursor_pixmap_item)
            self._cursor_pixmap_item.setScale(1 / self.scene_scale)
            self.set_cursor_pos(self._last_cursor_pos)
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        else:
            if self._cursor_pixmap_item is not None and self._cursor_pixmap_item.scene() is not None:
                self.scene().removeItem(self._cursor_pixmap_item)
                self._cursor_pixmap_item.setVisible(False)
            if new_cursor is None:
                new_cursor = QCursor()
            self.setCursor(new_cursor)
        self.update()

    def set_cursor_pos(self, cursor_pos: QPoint) -> None:
        """Updates the last cursor position within the widget so that pixmap cursor rendering stays active."""
        self._last_cursor_pos = cursor_pos
        if self._cursor_pixmap_item is not None and self._cursor_pixmap_item.scene() is not None:
            self._cursor_pixmap_item.setVisible(cursor_pos is not None)
            if cursor_pos is None:
                return
            scene_pos = self.mapToScene(cursor_pos)
            self._cursor_pixmap_item.setPos(scene_pos.x() - self._cursor_pixmap_item.pixmap().width()
                                            * self._cursor_pixmap_item.scale() / 2,
                                            scene_pos.y() - self._cursor_pixmap_item.pixmap().height()
                                            * self._cursor_pixmap_item.scale() / 2)

    def reset_scale(self) -> None:
        """Resets the scale to fit content in the view and re-centers the scene."""
        scale_will_change = self._scale_adjustment != 0.0
        self._scale_adjustment = 0.0
        self.offset = QPoint(0, 0)
        self.resizeEvent(None)
        self.centerOn(QPoint(int(self._content_size.width() / 2), int(self._content_size.height() / 2)))
        if scale_will_change:
            self.scale_changed.emit(self.scene_scale)

    @property
    def is_at_default_view(self) -> bool:
        """Returns whether the scale and offsets are both at default values."""
        return self._scale_adjustment == 0.0 and self._offset == QPointF(0.0, 0.0)

    @property
    def content_size(self) -> Optional[QSize]:
        """Gets the actual (not displayed) size of the viewed content."""
        return QSize(self._content_size.width(), self._content_size.height())

    @content_size.setter
    def content_size(self, new_size: QSize) -> None:
        """Updates the actual (not displayed) size of the viewed content."""
        assert_type(new_size, QSize)
        if new_size == self._content_size:
            return
        self._content_size.setWidth(new_size.width())
        self._content_size.setHeight(new_size.height())
        self.resizeEvent(None)
        self.resetCachedContent()
        self.update()

    @property
    def displayed_content_size(self) -> Optional[QSize]:
        """Gets the not displayed size of the viewed content."""
        if self._content_rect is None:
            return None
        return self._content_rect.size()

    @property
    def scene_scale(self) -> float:
        """Returns the image content scale."""
        return self._scale + self._scale_adjustment

    @scene_scale.setter
    def scene_scale(self, new_scale: float) -> None:
        """Updates the image content scale, limiting minimum scale to 0.01."""
        new_scale = max(new_scale, 0.001)
        self._scale_adjustment = new_scale - self._scale
        self.resizeEvent(None)
        self.centerOn(QPoint(int(self._content_size.width() / 2 + self._offset.x()),
                             int(self._content_size.height() / 2 + self._offset.y())))
        self.scale_changed.emit(new_scale)

    @property
    def offset(self) -> QPointF:
        """Gets the image offset in pixels."""
        return QPointF(self._offset)

    @offset.setter
    def offset(self, new_offset: QPoint | QPointF) -> None:
        """Updates the image offset."""
        self._offset.setX(float(new_offset.x()))
        self._offset.setY(float(new_offset.y()))
        self.resizeEvent(None)

    @property
    def background(self) -> QPixmap | None:
        """Returns the background image content."""
        return self._background

    @background.setter
    def background(self, new_background: Optional[QImage | QPixmap]) -> None:
        """Updates the background image content."""
        assert_type(new_background, (QImage, QPixmap, None))
        if isinstance(new_background, QImage):
            self._background = QPixmap.fromImage(new_background)
        else:
            self._background = new_background
        self.resetCachedContent()

    def widget_to_scene_coordinates(self, point: QPoint) -> QPointF:
        """Returns a point within the scene content corresponding to some point within the widget bounds."""
        assert_type(point, QPoint)
        return self.mapToScene(point)

    def scene_to_widget_coordinates(self, point: QPoint) -> QPointF:
        """Returns a point within the widget bounds corresponding to some point within the scene content."""
        assert_type(point, QPoint)
        return self.mapFromScene(point)

    def drawBackground(self, painter: Optional[QPainter], rect: QRectF) -> None:
        """Renders any background image behind all scene contents."""
        if painter is None or self._background is None or self._content_rect is None:
            return
        content_rect = self.mapToScene(self._content_rect).boundingRect()
        if self._background is not None:
            painter.drawPixmap(content_rect, self._background, QRectF(self._background.rect()))
        border_size = float(self._border_size())
        margins = QMarginsF(border_size, border_size, border_size, border_size)
        border_rect = content_rect.marginsAdded(margins)
        painter.setPen(QPen(contrast_color(self), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        painter.drawRect(border_rect)

    def drawForeground(self, painter: Optional[QPainter], rect: QRectF) -> None:
        """Draws cursor pixmap over the scene if one is installed."""
        if painter is None or self._cursor_pixmap is None or self._last_cursor_pos is None:
            return
        center_point = self.mapToScene(self._last_cursor_pos)
        scale = self.scene_scale
        pixmap_rect = QRectF(0.0, 0.0, self._cursor_pixmap.width() / scale,
                             self._cursor_pixmap.height() / scale).toRect()
        pixmap_rect.moveCenter(center_point.toPoint())
        painter.drawPixmap(pixmap_rect, self._cursor_pixmap)

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Recalculate content size when the widget is resized."""
        super().resizeEvent(event)
        if self.content_size is None:
            raise RuntimeError('FixedAspectGraphicsView implementations must set content_size in __init__ before the ' +
                               'first resizeEvent is triggered')

        # Handle scale adjustments when the widget size changes:
        border_size = self._border_size()
        self._content_rect = get_scaled_placement(QRect(QPoint(0, 0), self.size()), self.content_size, border_size)
        new_scale = self.displayed_content_size.width() / self.content_size.width()
        scale_changed = new_scale != self._scale
        self._scale = new_scale
        adjusted_scale = self._scale + self._scale_adjustment

        # Adjust the scene viewpoint/scrolling based on scale and offset:
        content_rect_f = QRectF(self._offset.x(), self._offset.y(), float(self.content_size.width()),
                                float(self.content_size.height()))
        if content_rect_f != self._scene.sceneRect():
            self._scene.setSceneRect(content_rect_f)
            self.centerOn(QPoint(int(self._content_size.width() / 2 + self._offset.x()),
                                 int(self._content_size.height() / 2 + self._offset.y())))

        transformation = QTransform()
        transformation.translate(self._offset.x(), self._offset.y())
        transformation.scale(adjusted_scale, adjusted_scale)
        self.setTransform(transformation)
        if scale_changed:
            self.scale_changed.emit(adjusted_scale)
        self.update()

    def _border_size(self) -> int:
        return (min(self.width(), self.height()) // 40) + 1

    def installEventFilter(self, event_filter: QObject) -> None:
        """Extend default event filter management to deal with QGraphicsView mouse event oddities."""
        if event_filter not in self._event_filters:
            self._event_filters.append(event_filter)
        super().installEventFilter(event_filter)

    def removeEventFilter(self, event_filter: QObject) -> None:
        """Extend default event filter management to deal with QGraphicsView mouse event oddities."""
        if event_filter in self._event_filters:
            self._event_filters.remove(event_filter)
        super().removeEventFilter(event_filter)

    def _pixmap_cursor_update(self, cursor_point: QPoint) -> None:
        """If a pixmap cursor is in use, keep last cursor point updated and force a redraw when the mouse moves."""
        if cursor_point != self._last_cursor_pos:
            self._last_cursor_pos = cursor_point
        if self._cursor_pixmap is not None:
            self.update()

    def mousePressEvent(self, event: Optional[QMouseEvent], get_result=False) -> bool:
        """Custom mousePress handler to deal with QGraphicsView oddities. Child classes must call this implementation
           first with get_result=True, then exit without further action if it returns true."""
        self.set_cursor_pos(event.pos())
        for event_filter in self._event_filters:
            if event_filter.eventFilter(self, event):
                return True if get_result else None
        return False if get_result else None

    def mouseMoveEvent(self, event: Optional[QMouseEvent], get_result=False) -> None:
        """Custom mouseMove handler to deal with QGraphicsView oddities. Child classes must call this implementation
           first with get_result=True, then exit without further action if it returns true."""
        self.set_cursor_pos(event.pos())
        for event_filter in self._event_filters:
            if event_filter.eventFilter(self, event):
                return True if get_result else None
        return False if get_result else None

    def mouseReleaseEvent(self, event: Optional[QMouseEvent], get_result=False) -> None:
        """Custom mouseRelease handler to deal with QGraphicsView oddities. Child classes must call this implementation
           first with get_result=True, then exit without further action if it returns true."""
        self.set_cursor_pos(event.pos())
        for event_filter in self._event_filters:
            if event_filter.eventFilter(self, event):
                return True if get_result else None
        return False if get_result else None

    def leaveEvent(self, event: Optional[QEvent]):
        """Clear the pixmap mouse cursor on leave."""
        self._last_cursor_pos = None
        super().leaveEvent(event)
