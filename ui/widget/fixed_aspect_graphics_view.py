"""A QGraphicsView that maintains an aspect ratio and simplifies scene management."""
from typing import Optional
from PyQt5.QtWidgets import QWidget, QGraphicsView, QGraphicsScene
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QTransform, QResizeEvent
from PyQt5.QtCore import Qt, QPoint, QPointF, QRect, QRectF, QSize, QMarginsF
from ui.util.get_scaled_placement import get_scaled_placement
from ui.util.contrast_color import contrast_color
from util.validation import assert_type


class FixedAspectGraphicsView(QGraphicsView):
    """A QGraphicsView that maintains an aspect ratio and simplifies scene management."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene()
        self._content_size: QSize = QSize(0, 0)
        self._content_rect: Optional[QRect] = None
        self._background: Optional[QPixmap] = None

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setCacheMode(QGraphicsView.CacheBackground)
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setScene(self._scene)

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

    def widget_to_scene_coords(self, point: QPoint) -> QPointF:
        """Returns a point within the scene content corresponding to some point within the widget bounds."""
        assert_type(point, QPoint)
        return self.mapToScene(point)

    def scene_to_widget_coords(self, point: QPoint) -> QPointF:
        """Returns a point within the widget bounds corresponding to some point within the scene content."""
        assert_type(point, QPoint)
        assert self._content_rect is not None and self.content_size is not None
        x_scale = self._content_rect.width() / self.content_size.width()
        y_scale = self._content_rect.height() / self.content_size.height()
        x0 = self._content_rect.x()
        y0 = self._content_rect.y()
        return QPointF(x0 + point.x() * x_scale, y0 + point.y() * y_scale)

    def widget_to_painter_coords(self, point: QPoint | QPointF, painter_bounds: QRectF) -> QPointF:
        """Converts a point from widget coordinates to painter coordinates."""
        assert_type(point, (QPoint, QPointF))
        assert_type(painter_bounds, QRectF)
        x_scale = painter_bounds.width() / self.size().width()
        y_scale = painter_bounds.height() / self.size().height()
        x0 = painter_bounds.x()
        y0 = painter_bounds.y()
        return QPointF(x0 + point.x() * x_scale, y0 + point.y() * y_scale)

    def scene_point_to_painter_coords(self, point: QPoint, painter_rect: QRectF) -> QPointF:
        """Converts a point from scene coordinates to painter coordinates."""
        widget_point = self.scene_to_widget_coords(point)
        return self.widget_to_painter_coords(widget_point, painter_rect)

    def _content_rect_to_painter_coords(self, painter_rect: QRectF) -> QRectF:
        """Converts a rectangle from scene coordinates to painter coordinates."""
        assert self._content_rect is not None
        top_left = QPoint(self._content_rect.x(), self._content_rect.y())
        bottom_right = QPoint(top_left.x() + self._content_rect.width(), top_left.y() + self._content_rect.height())
        top_left = self.widget_to_painter_coords(top_left, painter_rect)
        bottom_right = self.widget_to_painter_coords(bottom_right, painter_rect)
        return QRectF(top_left.x(), top_left.y(), bottom_right.x() - top_left.x(), bottom_right.y() - top_left.y())

    def drawBackground(self, painter: Optional[QPainter], rect: QRectF) -> None:
        """Renders any background image behind all scene contents."""
        if painter is None or self._background is None or self._content_rect is None:
            return
        content_rect = self._content_rect_to_painter_coords(rect)
        if self._background is not None:
            painter.drawPixmap(content_rect, self._background, QRectF(self._background.rect()))
        border_size = float(self._border_size())
        margins = QMarginsF(border_size, border_size, border_size, border_size)
        border_rect = content_rect.marginsAdded(margins)
        painter.setPen(QPen(contrast_color(self), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        painter.drawRect(border_rect)

    def drawForeground(self, painter: Optional[QPainter], rect: QRectF) -> None:
        """Draws a border around the scene area and blocks out any out-of-bounds content."""
        if painter is None:
            return
        content_rect = self._content_rect_to_painter_coords(rect)
        border_rect = content_rect.adjusted(-5.0, -5.0, 5.0, 5.0)

        # QGraphicsView fails to clip content sometimes, so fill everything outside of the scene with the
        # background color, then draw the border:
        fill_color = self.palette().color(self.backgroundRole())
        border_left = int(border_rect.x())
        border_right = border_left + int(border_rect.width())
        border_top = int(border_rect.y())
        border_bottom = border_top + int(border_rect.height())

        max_size = 200000000  # Larger than the viewport can ever possibly be, small enough to avoid overflow issues
        painter.fillRect(border_left, -(max_size // 2), -max_size, max_size, fill_color)
        painter.fillRect(border_right, -(max_size // 2), max_size, max_size, fill_color)
        painter.fillRect(-(max_size // 2), border_top, max_size, -max_size, fill_color)
        painter.fillRect(-(max_size // 2), border_bottom, max_size, max_size, fill_color)

        painter.setPen(QPen(contrast_color(self), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        painter.drawRect(border_rect)
        super().drawForeground(painter, rect)

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Recalculate content size when the widget is resized."""
        super().resizeEvent(event)
        if self.content_size is None:
            raise RuntimeError('FixedAspectGraphicsView implementations must set content_size in __init__ before the ' +
                               'first resizeEvent is triggered')
        content_rect_f = QRectF(0.0, 0.0, float(self.content_size.width()), float(self.content_size.height()))
        if content_rect_f != self._scene.sceneRect():
            self._scene.setSceneRect(content_rect_f)

        border_size = self._border_size()
        self._content_rect = get_scaled_placement(QRect(QPoint(0, 0), self.size()), self.content_size, border_size)
        x_scale = self._content_rect.width() / self.content_size.width()
        y_scale = self._content_rect.height() / self.content_size.height()
        transformation = QTransform()
        transformation.scale(x_scale, y_scale)
        transformation.translate(float(self._content_rect.x()), float(self._content_rect.y()))
        self.setTransform(transformation)
        self.update()

    def _border_size(self) -> int:
        return (min(self.width(), self.height()) // 40) + 1
